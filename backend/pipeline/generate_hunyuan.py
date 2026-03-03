"""
HunyuanWorld 1.0 — Full Pipeline Integration
=============================================
Replaces the old TripoSR-based generator with HunyuanWorld's two-step pipeline:
  Step 1: Image → 360° Panorama  (FLUX.1-Fill-dev + HunyuanWorld LoRA)
  Step 2: Panorama → 3D World    (LayerDecomposition + WorldComposer)

Output: .glb file (converted from .ply via trimesh) for Unity consumption.
"""

import os
import sys
import torch
import numpy as np
import trimesh
from PIL import Image
from argparse import Namespace

# Add HunyuanWorld to Python path
HUNYUAN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "HunyuanWorld-1.0")
if HUNYUAN_DIR not in sys.path:
    sys.path.insert(0, HUNYUAN_DIR)

# HunyuanWorld imports (lazy — only imported when class is instantiated)
# These come from hy3dworld package inside HunyuanWorld-1.0/
_hy3d_imported = False


def _ensure_hy3d_imports():
    """Lazy import HunyuanWorld modules to avoid import errors at startup."""
    global _hy3d_imported
    if _hy3d_imported:
        return
    
    global Image2PanoramaPipelines, Perspective
    global LayerDecomposition, WorldComposer, process_file
    global FluxFp8GeMMProcessor, FluxFp8AttnProcessor2_0

    from hy3dworld import Image2PanoramaPipelines, Perspective
    from hy3dworld import LayerDecomposition, WorldComposer, process_file
    from hy3dworld.AngelSlim.gemm_quantization_processor import FluxFp8GeMMProcessor
    from hy3dworld.AngelSlim.attention_quantization_processor import FluxFp8AttnProcessor2_0
    
    _hy3d_imported = True


class HunyuanGenerator:
    """
    Encapsulates the full HunyuanWorld pipeline:
      1. Image → Panorama (using FLUX.1-Fill-dev + LoRA)
      2. Panorama → Layered 3D World (LayerDecomposition + WorldComposer)
      3. Export merged .glb for Unity

    VRAM Optimizations (enabled by default for consumer GPUs):
      - FP8 attention quantization
      - FP8 GEMM quantization
      - Model CPU offloading
      - VAE tiling
    """

    def __init__(self, fp8_attention: bool = True, fp8_gemm: bool = True):
        _ensure_hy3d_imports()

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.fp8_attention = fp8_attention
        self.fp8_gemm = fp8_gemm

        print(f"[HunyuanGenerator] Initializing on device: {self.device}")
        print(f"[HunyuanGenerator] FP8 Attention: {fp8_attention}, FP8 GEMM: {fp8_gemm}")

        # --- Panorama Generator (Image → 360° Panorama) ---
        self._init_panorama_pipeline()

        # --- Scene Generator (Panorama → 3D World) ---
        self._init_scene_pipeline()

        print("[HunyuanGenerator] All models loaded successfully.")

    def _init_panorama_pipeline(self):
        """Initialize the Image-to-Panorama pipeline with VRAM optimizations."""
        print("[HunyuanGenerator] Loading Image2Panorama pipeline (FLUX.1-Fill-dev + LoRA)...")

        # Panorama generation parameters
        self.pano_height = 960
        self.pano_width = 1920
        self.guidance_scale = 30
        self.num_inference_steps = 50
        self.true_cfg_scale = 2.0
        self.blend_extend = 6
        self.shifting_extend = 0
        self.fov = 80
        self.theta = 0
        self.phi = 0

        # Load the pipeline with bfloat16 to save VRAM
        model_path = "black-forest-labs/FLUX.1-Fill-dev"
        lora_path = "tencent/HunyuanWorld-1"

        self.pano_pipe = Image2PanoramaPipelines.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16
        )

        # Load and fuse LoRA weights
        self.pano_pipe.load_lora_weights(
            lora_path,
            subfolder="HunyuanWorld-PanoDiT-Image",
            weight_name="lora.safetensors",
            torch_dtype=torch.bfloat16
        )
        self.pano_pipe.fuse_lora()
        self.pano_pipe.unload_lora_weights()

        # VRAM optimizations
        self.pano_pipe.enable_model_cpu_offload()
        self.pano_pipe.enable_vae_tiling()

        # FP8 quantization
        if self.fp8_attention:
            self.pano_pipe.transformer.set_attn_processor(FluxFp8AttnProcessor2_0())
            print("[HunyuanGenerator] Panorama: FP8 Attention enabled")
        if self.fp8_gemm:
            FluxFp8GeMMProcessor(self.pano_pipe.transformer)
            print("[HunyuanGenerator] Panorama: FP8 GEMM enabled")

        # Quality prompts
        self.positive_suffix = "high-quality, high-resolution, sharp, clear, 8k"
        self.negative_prompt = "human, person, people, messy, low-quality, blur, noise, low-resolution"

    def _init_scene_pipeline(self):
        """Initialize LayerDecomposition + WorldComposer for scene generation."""
        print("[HunyuanGenerator] Loading Scene Generation pipeline...")

        # Build args namespace that HunyuanWorld expects
        self.scene_args = Namespace(
            fp8_attention=self.fp8_attention,
            fp8_gemm=self.fp8_gemm,
            cache=False,
        )

        # Layer decomposition (inpainting foreground/sky)
        self.layer_decomposer = LayerDecomposition(self.scene_args)

        # World composer (layered 3D reconstruction)
        target_size = 3840
        kernel_scale = max(1, int(target_size / 1920))
        self.world_composer = WorldComposer(
            device=self.device,
            resolution=(target_size, target_size // 2),
            seed=42,
            filter_mask=True,
            kernel_scale=kernel_scale,
        )

        # Apply FP8 to scene pipeline
        if self.fp8_attention:
            self.layer_decomposer.inpaint_fg_model.transformer.set_attn_processor(FluxFp8AttnProcessor2_0())
            self.layer_decomposer.inpaint_sky_model.transformer.set_attn_processor(FluxFp8AttnProcessor2_0())
        if self.fp8_gemm:
            FluxFp8GeMMProcessor(self.layer_decomposer.inpaint_fg_model.transformer)
            FluxFp8GeMMProcessor(self.layer_decomposer.inpaint_sky_model.transformer)

    def generate_panorama(self, image_path: str, caption: str, output_dir: str, seed: int = 42) -> str:
        """
        Step 1: Convert a perspective image into a 360° panorama.
        
        Args:
            image_path: Path to the uploaded image
            caption: BLIP-generated caption (used as the generation prompt)
            output_dir: Directory to save the panorama
            seed: Random seed for reproducibility
            
        Returns:
            Path to the generated panorama image
        """
        import cv2

        print(f"[HunyuanGenerator] Generating panorama from: {image_path}")
        print(f"[HunyuanGenerator] Using prompt: {caption}")

        # Enhance prompt with quality suffixes
        prompt = f"{caption}, {self.positive_suffix}"

        # Read and resize the perspective image
        perspective_img = cv2.imread(image_path)
        height_fov, width_fov = perspective_img.shape[:2]

        if width_fov > height_fov:
            ratio = width_fov / height_fov
            w = int((self.fov / 360) * self.pano_width)
            h = int(w / ratio)
        else:
            ratio = height_fov / width_fov
            h = int((self.fov / 180) * self.pano_height)
            w = int(h / ratio)

        perspective_img = cv2.resize(perspective_img, (w, h), interpolation=cv2.INTER_AREA)

        # Project to equirectangular
        equ = Perspective(perspective_img, self.fov, self.theta, self.phi, crop_bound=False)
        img, mask = equ.GetEquirec(self.pano_height, self.pano_width)

        # Erode mask
        mask = cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=5)
        img = img * mask
        mask = (255 - mask.astype(np.uint8) * 255)

        mask_pil = Image.fromarray(mask[:, :, 0])
        img_rgb = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)

        # Run the panorama generation pipeline
        panorama = self.pano_pipe(
            prompt=prompt,
            image=img_pil,
            mask_image=mask_pil,
            height=self.pano_height,
            width=self.pano_width,
            negative_prompt=self.negative_prompt,
            guidance_scale=self.guidance_scale,
            num_inference_steps=self.num_inference_steps,
            generator=torch.Generator("cpu").manual_seed(seed),
            blend_extend=self.blend_extend,
            shifting_extend=self.shifting_extend,
            true_cfg_scale=self.true_cfg_scale,
        ).images[0]

        # Save panorama
        os.makedirs(output_dir, exist_ok=True)
        pano_path = os.path.join(output_dir, "panorama.png")
        panorama.save(pano_path)
        print(f"[HunyuanGenerator] Panorama saved to: {pano_path}")

        return pano_path

    def generate_world(
        self,
        panorama_path: str,
        output_dir: str,
        labels_fg1: list = None,
        labels_fg2: list = None,
        scene_class: str = "outdoor",
    ) -> str:
        """
        Step 2: Convert a 360° panorama into a layered 3D world mesh.
        
        Args:
            panorama_path: Path to the panorama image
            output_dir: Directory to save meshes
            labels_fg1: Foreground object labels for layer 1 (e.g., ["stones", "cars"])
            labels_fg2: Foreground object labels for layer 2 (e.g., ["trees", "buildings"])
            scene_class: Scene type - "outdoor" or "indoor"
            
        Returns:
            Path to the final merged .glb file
        """
        import open3d as o3d

        labels_fg1 = labels_fg1 or []
        labels_fg2 = labels_fg2 or []

        print(f"[HunyuanGenerator] Generating 3D world from panorama: {panorama_path}")
        print(f"[HunyuanGenerator] FG1 labels: {labels_fg1}, FG2 labels: {labels_fg2}")

        os.makedirs(output_dir, exist_ok=True)

        # Layer decomposition
        fg1_infos = [{
            "image_path": panorama_path,
            "output_path": output_dir,
            "labels": labels_fg1,
            "class": scene_class,
        }]
        fg2_infos = [{
            "image_path": os.path.join(output_dir, "remove_fg1_image.png"),
            "output_path": output_dir,
            "labels": labels_fg2,
            "class": scene_class,
        }]

        self.layer_decomposer(fg1_infos, layer=0)
        self.layer_decomposer(fg2_infos, layer=1)
        self.layer_decomposer(fg2_infos, layer=2)

        # Load separated panorama layers
        separate_pano, fg_bboxes = self.world_composer._load_separate_pano_from_dir(
            output_dir, sr=True
        )

        # Generate the layered world mesh
        layered_world_mesh = self.world_composer.generate_world(
            separate_pano=separate_pano, fg_bboxes=fg_bboxes, world_type="mesh"
        )

        # Save individual layer PLY files and collect meshes for merging
        all_trimeshes = []
        for layer_idx, layer_info in enumerate(layered_world_mesh):
            ply_path = os.path.join(output_dir, f"mesh_layer{layer_idx}.ply")
            o3d.io.write_triangle_mesh(ply_path, layer_info["mesh"])
            print(f"[HunyuanGenerator] Saved layer {layer_idx} to: {ply_path}")

            # Convert Open3D mesh to trimesh for GLB export
            o3d_mesh = layer_info["mesh"]
            vertices = np.asarray(o3d_mesh.vertices)
            triangles = np.asarray(o3d_mesh.triangles)
            
            t_mesh = trimesh.Trimesh(vertices=vertices, faces=triangles)
            
            # Transfer vertex colors if available
            if o3d_mesh.has_vertex_colors():
                vertex_colors = (np.asarray(o3d_mesh.vertex_colors) * 255).astype(np.uint8)
                # Add alpha channel
                alpha = np.full((vertex_colors.shape[0], 1), 255, dtype=np.uint8)
                vertex_colors = np.hstack([vertex_colors, alpha])
                t_mesh.visual.vertex_colors = vertex_colors

            all_trimeshes.append(t_mesh)

        # Merge all layers into a single mesh and export as .glb
        glb_path = os.path.join(output_dir, "scene.glb")
        if all_trimeshes:
            merged = trimesh.util.concatenate(all_trimeshes)
            merged.export(glb_path, file_type="glb")
            print(f"[HunyuanGenerator] Merged GLB saved to: {glb_path}")
        else:
            print("[HunyuanGenerator] WARNING: No meshes were generated!")
            raise RuntimeError("World generation produced no meshes")

        return glb_path

    def run_full_pipeline(
        self,
        image_path: str,
        caption: str,
        output_dir: str,
        labels_fg1: list = None,
        labels_fg2: list = None,
        scene_class: str = "outdoor",
        seed: int = 42,
        progress_callback=None,
    ) -> str:
        """
        End-to-end pipeline: Image → Panorama → 3D World → scene.glb
        
        Args:
            image_path: Path to the uploaded image
            caption: BLIP-generated caption
            output_dir: Directory for all outputs
            labels_fg1: Foreground labels for layer 1
            labels_fg2: Foreground labels for layer 2
            scene_class: "outdoor" or "indoor"
            seed: Random seed
            progress_callback: Optional callable(progress_pct, message)
            
        Returns:
            Path to the final .glb file
        """
        def _progress(pct, msg):
            if progress_callback:
                progress_callback(pct, msg)
            print(f"[HunyuanGenerator] [{pct}%] {msg}")

        _progress(10, "Starting panorama generation...")

        # Step 1: Image → Panorama
        pano_path = self.generate_panorama(image_path, caption, output_dir, seed=seed)
        _progress(40, "Panorama complete. Starting world generation...")

        # Step 2: Panorama → 3D World
        glb_path = self.generate_world(
            pano_path, output_dir,
            labels_fg1=labels_fg1,
            labels_fg2=labels_fg2,
            scene_class=scene_class,
        )
        _progress(95, "World generation complete. Finalizing...")

        _progress(100, "Pipeline complete!")
        return glb_path

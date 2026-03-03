"""
GPU Queue Manager
=================
Manages sequential GPU-bound jobs using an asyncio lock.
Integrates BLIP vision + HunyuanWorld generation pipeline.
"""

import asyncio
import os
from pipeline.vision import VisionModelManager
from pipeline.generate_hunyuan import HunyuanGenerator
from core.state import jobs_db

# Global Singletons (lazy-loaded)
vision_manager = None
hunyuan_generator = None

# Single worker lock to prevent GPU OOM
gpu_lock = asyncio.Lock()


async def process_job(job_id: str, image_path: str, output_dir: str):
    """
    Process a single generation job inside the GPU lock.
    Pipeline: Image → BLIP Caption → Panorama → 3D World → .glb
    """
    global vision_manager, hunyuan_generator

    # Allow FastAPI to flush pending responses before we block
    await asyncio.sleep(0.1)

    async with gpu_lock:
        try:
            # ----------------------------------
            # Lazy-load models on first job
            # ----------------------------------
            if vision_manager is None:
                _update_job(job_id, message="Loading Vision AI (BLIP)...", progress=5)
                vision_manager = VisionModelManager()

            if hunyuan_generator is None:
                _update_job(job_id, message="Loading HunyuanWorld 3D AI...", progress=10)
                hunyuan_generator = HunyuanGenerator(
                    fp8_attention=True,
                    fp8_gemm=True,
                )

            # ----------------------------------
            # Step 1: Generate caption with BLIP
            # ----------------------------------
            _update_job(job_id, message="Analyzing image (BLIP)...", progress=15)
            caption = vision_manager.generate_caption(image_path)
            _update_job(job_id, caption=caption, progress=20)

            # ----------------------------------
            # Step 2: Full HunyuanWorld pipeline
            # ----------------------------------
            def progress_callback(pct, msg):
                """Map HunyuanWorld's 10-100% to our 20-95% range."""
                mapped_pct = 20 + int((pct / 100) * 75)
                _update_job(job_id, message=msg, progress=min(mapped_pct, 95))

            _update_job(job_id, message="Starting HunyuanWorld pipeline...", progress=20, state="running")

            glb_path = hunyuan_generator.run_full_pipeline(
                image_path=image_path,
                caption=caption,
                output_dir=output_dir,
                progress_callback=progress_callback,
            )

            # ----------------------------------
            # Done
            # ----------------------------------
            _update_job(job_id, state="done", progress=100, message="Generation complete.")
            print(f"[{job_id}] Job completed successfully. Output: {glb_path}")

        except Exception as e:
            print(f"[{job_id}] Generation failed: {repr(e)}")
            _update_job(job_id, state="failed", progress=0, message=f"Error: {str(e)}")


def _update_job(job_id: str, **fields):
    """Helper to update job fields in jobs_db."""
    if job_id in jobs_db:
        jobs_db[job_id].update(fields)

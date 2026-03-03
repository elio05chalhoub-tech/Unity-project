import torch
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

class VisionModelManager:
    def __init__(self):
        # Determine the device. Prioritize CUDA.
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Initializing VisionModelManager on device: {self.device}")
        
        caption_model_id = "Salesforce/blip-image-captioning-large"
        self.processor = BlipProcessor.from_pretrained(caption_model_id)
        self.model = BlipForConditionalGeneration.from_pretrained(caption_model_id).to(self.device)

    def generate_caption(self, image_path: str) -> str:
        raw_image = Image.open(image_path).convert('RGB')
        
        # A specific prefix helps BLIP format for scene generation
        text = "A detailed 3D scene consisting of"
        
        inputs = self.processor(images=raw_image, text=text, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=50)
            
        caption = self.processor.decode(out[0], skip_special_tokens=True)
        return caption

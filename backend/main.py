import os
import uuid
import httpx
from typing import Optional
from google import genai

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Request, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# We use a simple in-memory dictionary for Phase 2 Blockade Labs API Bridge.
# SQLite was used for Phase 1 local execution, but the schema doesn't match Blockade Labs fields.
jobs_db = {}

env_path = r"C:\Users\HP\OneDrive\Desktop\AIWorldProject\backend\.env"
load_dotenv(dotenv_path=env_path, override=True)

# Re-evaluate API Key per request to ensure it's picked up
def get_api_key():
    load_dotenv(dotenv_path=env_path, override=True)
    return os.getenv("BLOCKADE_LABS_API_KEY")

def get_gemini_key():
    load_dotenv(dotenv_path=env_path, override=True)
    return os.getenv("GEMINI_API_KEY")

app = FastAPI(title="AI World Backend Upgrade - Phase 2", description="Blockade Labs Skybox AI Bridge with Remix")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BLOCKADE_LABS_API_KEY = os.getenv("BLOCKADE_LABS_API_KEY")

# Hardcoded style ID for "Digital Painting" (Style ID 4)
STYLE_ID_DIGITAL_PAINTING = 4

@app.get("/health")
async def health_check():
    return {"ok": True, "phase": 2}

@app.post("/generate")
async def generate_skybox(
    image: UploadFile = File(...),
    prompt: str = Form("A completely accurate 360 environment based on the uploaded image. Must have a seamless, solid ground floor at the bottom of the spherical panorama.")
):
    """
    Phase 2: Remix Image to 3D World Concept with Vision AI
    """
    api_key = get_api_key()
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        # MOCK MODE FOR TESTING
        content = await image.read()
        job_id = str(uuid.uuid4())
        blockade_id = "mock_blockade_" + str(uuid.uuid4())
        jobs_db[job_id] = {
            "state": "processing",
            "progress": 10,
            "message": "[MOCK] Sent to Blockade Labs...",
            "blockade_id": blockade_id
        }
        return {"jobId": job_id, "blockadeId": blockade_id, "mock": True}

    # Read the uploaded image
    content = await image.read()
    
    # --- PHASE 5: VISION AI CAPTIONING ---
    final_prompt = prompt
    gemini_key = get_gemini_key()
    
    if gemini_key:
        try:
            print("[Vision AI] Querying Gemini for intelligent prompt generation...")
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tf:
                tf.write(content)
                tmp_path = tf.name
                
            client = genai.Client(api_key=gemini_key)
            image_file = client.files.upload(file=tmp_path)
            
            vision_instruction = "You are a literal image describer used to generate 360 Skybox prompts. Write a highly detailed, photorealistic 1-paragraph description of exactly what is in this sketch. Do not hallucinate elements that are not there (like sunsets or blue skies) unless explicitly drawn. Assume the landscape has a solid, continuous floor matching the environment shown. Output only the prompt paragraph."
            
            vision_response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[image_file, vision_instruction]
            )
            
            try:
                os.remove(tmp_path)
            except Exception:
                pass
                
            if vision_response.text:
                final_prompt = vision_response.text
                print(f"\n=========================================")
                print(f"[Vision AI] Success! Generated Prompt:")
                print(f"{final_prompt}")
                print(f"=========================================\n")
        except Exception as e:
            print(f"\n=========================================")
            print(f"[Vision AI] ERROR querying Gemini: {e}")
            print(f"=========================================\n")
            pass
    # --------------------------------------

    # 1. Send to Blockade Labs API for Remix
    url = "https://backend.blockadelabs.com/api/v1/skybox"
    headers = {
        "x-api-key": api_key,
        "Accept": "application/json"
    }

    # Prepare form data
    files = {
        "control_image": (image.filename or "upload.png", content, "image/png")
    }
    data = {
        "prompt": final_prompt,
        "negative_text": "floating islands, floating trees, missing floor, unrealistic",
        "skybox_style_id": "9",
        "control_model": "remix",
        "enhance_prompt": "true"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, data=data, files=files)
            response.raise_for_status()
            result = response.json()
            
            # The API returns an id (integer) which we must use to poll
            blockade_id = result.get("id")
            if not blockade_id:
                raise HTTPException(status_code=500, detail=f"Did not receive an ID. Raw response: {result}")

            # Create our own job_id
            job_id = str(uuid.uuid4())
            
            # Store it in our DB
            jobs_db[job_id] = {
                "state": "processing",
                "progress": 10,
                "message": "Sent to Blockade Labs...",
                "blockade_id": str(blockade_id)
            }
            
            return {"jobId": job_id, "blockadeId": str(blockade_id)}
            
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Blockade API Error: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Phase 2: Poll Status. We check the Blockade Labs API on-demand.
    """
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job ID not found in local DB")

    job_info = jobs_db[job_id]
    blockade_id = job_info.get("blockade_id")
    current_state = job_info.get("state")

    if current_state in ["done", "failed"] or not blockade_id:
        return {
            "jobId": job_id,
            "state": job_info.get("state", "unknown"),
            "progress": job_info.get("progress", 0),
            "message": job_info.get("message", ""),
            "download_url": job_info.get("download_url", "")
        }

    api_key = get_api_key()
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        # MOCK MODE FOR TESTING
        current_prog = jobs_db[job_id].get("progress", 10)
        if current_prog < 100:
            new_prog = current_prog + 30
            if new_prog >= 100:
                jobs_db[job_id]["state"] = "done"
                jobs_db[job_id]["progress"] = 100
                jobs_db[job_id]["message"] = "[MOCK] World generation complete!"
                jobs_db[job_id]["download_url"] = "https://example.com/mock_skybox.jpg"
            else:
                jobs_db[job_id]["progress"] = new_prog
                jobs_db[job_id]["message"] = f"[MOCK] Rendering... {new_prog}%"
                
        updated_info = jobs_db[job_id]
        return {
            "jobId": job_id,
            "state": updated_info.get("state", "unknown"),
            "progress": updated_info.get("progress", 0),
            "message": updated_info.get("message", ""),
            "download_url": updated_info.get("download_url", ""),
            "mock": True
        }

    # Poll Blockade Labs
    url = f"https://backend.blockadelabs.com/api/v1/imagine/requests/{blockade_id}"
    headers = {
        "x-api-key": api_key
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.get(url, headers=headers)
            res.raise_for_status()
            raw_data = res.json()
            
            # The Blockade API wraps the actual status inside a "request" object!
            data = raw_data.get("request", raw_data)

            req_status = data.get("status")
            error_message = data.get("error_message", "Unknown error")
            file_url = data.get("file_url")

            # Note: We update the job state dictionary. 
            # If using core.state shim, it intercepts and writes to SQLite!
            if req_status == "complete":
                jobs_db[job_id]["state"] = "done"
                jobs_db[job_id]["progress"] = 100
                jobs_db[job_id]["message"] = "World generation complete!"
                jobs_db[job_id]["download_url"] = file_url
            elif req_status in ["error", "abort"]:
                jobs_db[job_id]["state"] = "failed"
                jobs_db[job_id]["progress"] = 0
                jobs_db[job_id]["message"] = f"Blockade Labs failed: {error_message}"
            elif req_status == "processing":
                jobs_db[job_id]["progress"] = 50
                jobs_db[job_id]["message"] = "Rendering Skybox Remaster in the Cloud..."
            elif req_status == "pending":
                jobs_db[job_id]["progress"] = 20
                jobs_db[job_id]["message"] = "Queued at Blockade Labs..."

        except httpx.HTTPStatusError as e:
            print(f"Error checking status for {job_id}: {e}")
            print(f"Blockade Labs Response Body: {e.response.text}")
            jobs_db[job_id]["state"] = "failed"
            jobs_db[job_id]["message"] = f"API Error: {e.response.text}"
        except Exception as e:
            print(f"Error checking status for {job_id}: {e}")
            # Keep the old status on temporary network errors

    # Re-fetch from DB in case it was updated
    updated_info = jobs_db[job_id]

    return {
        "jobId": job_id,
        "state": updated_info.get("state", "unknown"),
        "progress": updated_info.get("progress", 0),
        "message": updated_info.get("message", ""),
        "download_url": updated_info.get("download_url", "")
    }

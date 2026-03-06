# AI World Project

## Overview
AI World Project is a full-stack application that enables users to generate immersive 3D worlds simply by uploading a 2D image. It bridges the gap between 2D concept art and 3D environments using advanced AI models.

## Architecture
The system consists of several integrated components:
- **Unity Frontend (`unity/`):** The primary client application where users upload images and explore the resulting generated 3D worlds. Key scripts include `AppManager`, `BackendClient`, and `WorldImporter`.
- **FastAPI Backend (`backend/`):** A robust Python server that handles the heavy lifting, including routing requests, processing data, and orchestrating the AI pipelines.
- **Vision AI Prompt Generation:** Integrates with Google Gemini Vision AI to automatically analyze user-uploaded images and generate highly descriptive, optimized text prompts for world generation.
- **3D World Generation:** Utilizes external APIs (like Blockade Labs) and local, heavy-weight models (like HunyuanWorld) to translate the AI-generated text prompts into fully realized 3D environments.
- **Web Frontend (`frontend-web/`):** An alternative web-based client for interacting with the service.

## How it Works
1. **Upload:** The user uploads an image via the Unity client.
2. **Analysis:** The FastAPI backend receives the image and passes it to the Vision AI model.
3. **Prompting:** The Vision AI generates a detailed text prompt describing the scene in the image.
4. **Generation:** The prompt is sent to the 3D generation pipeline (HunyuanWorld/Blockade Labs).
5. **Import:** Once generation is complete, the backend sends the 3D assets back to the Unity client, which dynamically imports and displays the new world.

## Setup & Run Instructions

### 1. Backend Server
- Navigate to the `backend/` directory.
- Ensure you have a working Python environment. Install dependencies (e.g., FastAPI, Uvicorn, and model requirements).
- Set any necessary Environment Variables (API keys for Gemini, Blockade Labs, HuggingFace login).
- *Note:* If running HunyuanWorld locally, ensure the required model weights (approx. 33GB) are fully downloaded and located in the correct directory.
- Start the server (typically using Uvicorn or a custom run script depending on the exact project structure).

### 2. Unity Client
- Open the `unity/` folder in the Unity Editor.
- Ensure the API endpoint in your C# scripts (`BackendClient`) matches the local URL where your FastAPI backend is running (usually `http://127.0.0.1:8000`).
- Press **Play** in the editor to test the image upload and world generation flow.

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import subprocess
import asyncio
import os
import signal
from typing import Optional
import httpx

app = FastAPI()

# Configuration from environment variables
MODEL_PATH = os.getenv("MODEL_PATH", "/app/models/model.gguf")
MAX_THREADS = int(os.getenv("MAX_THREADS", "4"))
CONTEXT_SIZE = int(os.getenv("CONTEXT_SIZE", "2048"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))
LLAMA_SERVER_PORT = 8080

# Global process handle
llama_process: Optional[subprocess.Popen] = None
server_ready = False

class InferenceRequest(BaseModel):
    prompt: str = Field(..., max_length=4000)
    max_tokens: Optional[int] = Field(default=MAX_TOKENS, le=MAX_TOKENS)
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    stop: Optional[list[str]] = None

class InferenceResponse(BaseModel):
    content: str
    tokens_used: int

async def start_llama_server():
    """Start llama-server subprocess at startup"""
    global llama_process, server_ready
    
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(f"Model file not found at {MODEL_PATH}")
    
    cmd = [
        "llama-server",
        "-m", MODEL_PATH,
        "--host", "127.0.0.1",
        "--port", str(LLAMA_SERVER_PORT),
        "-t", str(MAX_THREADS),
        "-c", str(CONTEXT_SIZE),
        "--log-disable",
        "-np", "1"  # Single slot
    ]
    
    llama_process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid if os.name != 'nt' else None
    )
    
    # Wait for server to be ready
    async with httpx.AsyncClient() as client:
        for _ in range(30):
            try:
                response = await client.get(f"http://127.0.0.1:{LLAMA_SERVER_PORT}/health", timeout=1.0)
                if response.status_code == 200:
                    server_ready = True
                    return
            except:
                await asyncio.sleep(1)
    
    raise RuntimeError("llama-server failed to start")

async def stop_llama_server():
    """Stop llama-server subprocess"""
    global llama_process, server_ready
    if llama_process:
        if os.name != 'nt':
            os.killpg(os.getpgid(llama_process.pid), signal.SIGTERM)
        else:
            llama_process.terminate()
        llama_process.wait(timeout=5)
        llama_process = None
        server_ready = False

@app.on_event("startup")
async def startup_event():
    await start_llama_server()

@app.on_event("shutdown")
async def shutdown_event():
    await stop_llama_server()

@app.get("/")
def read_root():
    return {"message": "yo"}

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model_loaded": server_ready,
        "model_path": MODEL_PATH
    }

@app.post("/infer", response_model=InferenceResponse)
async def infer(request: InferenceRequest):
    if not server_ready:
        raise HTTPException(status_code=503, detail="Model server not ready")
    
    payload = {
        "prompt": request.prompt,
        "n_predict": request.max_tokens or MAX_TOKENS,
        "temperature": request.temperature,
        "stop": request.stop or [],
        "cache_prompt": False,
        "stream": False
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"http://127.0.0.1:{LLAMA_SERVER_PORT}/completion",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            return InferenceResponse(
                content=result.get("content", ""),
                tokens_used=result.get("tokens_predicted", 0)
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Inference timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
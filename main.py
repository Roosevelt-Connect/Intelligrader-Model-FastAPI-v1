from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from llama_cpp import Llama
import os

app = FastAPI()

# Load the GGUF model
model_path = "./models/SmolLM2-Rethink-360M.F32.gguf"
llm = None

@app.on_event("startup")
async def startup_event():
    global llm
    if os.path.exists(model_path):
        llm = Llama(
            model_path=model_path,
            n_ctx=2048,  # Context window
            n_threads=4,  # Number of CPU threads
            n_gpu_layers=0  # CPU only
        )
        print(f"Model loaded successfully from {model_path}")
    else:
        print(f"Warning: Model not found at {model_path}")

class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 128
    temperature: float = 0.7
    top_p: float = 0.9

@app.get("/")
def read_root():
    return {"message": "yo"}

@app.get("/health")
def health():
    model_status = "loaded" if llm is not None else "not loaded"
    return {"status": "healthy", "model": model_status}

@app.get("/add")
def add_parameters(parameter1: float, parameter2: float):
    try:
        result = parameter1 + parameter2
        return {"result": result}
    except (TypeError, ValueError) as e:
        # HTTP 400 (bad request) with error details.
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")

@app.post("/generate")
def generate_text(request: GenerateRequest):
    if llm is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        output = llm(
            request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            echo=False
        )
        
        return {
            "prompt": request.prompt,
            "generated_text": output["choices"][0]["text"],
            "tokens_used": output["usage"]["total_tokens"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")
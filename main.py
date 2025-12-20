from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Tuple
import httpx
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AP FRQ Grading Service",
    description="Production-grade service for grading AP Free Response Questions using Ollama",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")  # or smollm:latest
TIMEOUT = 300  # 5 minutes for grading
MAX_RETRIES = 3


class GradingRequest(BaseModel):
    """Request model for grading an FRQ."""
    student_response: str = Field(..., description="The student's response to grade")
    rubric: str = Field(..., description="The rubric/answer key for grading")
    question_prompt: str = Field(..., description="The original question prompt")
    max_points: int = Field(default=10, ge=1, le=100, description="Maximum points for this question")
    question_number: Optional[str] = Field(None, description="Optional question identifier")


class GradingResponse(BaseModel):
    """Response model for grading results."""
    score: float = Field(..., description="Numerical score awarded")
    max_points: float = Field(..., description="Maximum possible points")
    percentage: float = Field(..., description="Score as percentage")
    feedback: str = Field(..., description="Detailed feedback for the student")
    rubric_alignment: Dict[str, float] = Field(..., description="Alignment scores for each rubric criterion")
    timestamp: str = Field(..., description="When the grading was performed")
    question_number: Optional[str] = Field(None, description="Question identifier if provided")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    ollama_available: bool
    model: str


async def call_ollama(prompt: str, system_prompt: str = None) -> str:
    """
    Call Ollama API with deterministic settings.
    Uses low temperature and CPU-only inference.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,  # Low temperature for deterministic outputs
            "top_p": 0.9,
            "top_k": 40,
            "num_predict": 2000,  # Limit response length
            "repeat_penalty": 1.1,
            "seed": 42,  # Deterministic seed
            "num_thread": 4,  # CPU threads
            "num_gpu": 0,  # CPU-only
        }
    }
    
    if system_prompt:
        payload["system"] = system_prompt
    
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
        except httpx.TimeoutException:
            logger.warning(f"Ollama request timeout (attempt {attempt + 1}/{MAX_RETRIES})")
            if attempt == MAX_RETRIES - 1:
                raise HTTPException(status_code=504, detail="Ollama service timeout")
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e}")
            if attempt == MAX_RETRIES - 1:
                raise HTTPException(status_code=502, detail=f"Ollama service error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error calling Ollama: {e}")
            if attempt == MAX_RETRIES - 1:
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Failed to call Ollama after retries")


def create_grading_prompt(student_response: str, rubric: str, question_prompt: str, max_points: int) -> Tuple[str, str]:
    """
    Create the grading prompt with rubric anchoring.
    Returns (system_prompt, user_prompt) tuple.
    """
    system_prompt = """You are an expert AP exam grader. Your task is to grade student responses against a detailed rubric. 
You must be precise, fair, and consistent. Always provide:
1. A numerical score (0 to max_points)
2. Detailed feedback explaining what the student did well and what needs improvement
3. Specific references to rubric criteria and how the response aligns with each criterion

Be deterministic and consistent. Similar responses should receive similar scores."""
    
    user_prompt = f"""Grade the following AP Free Response Question response.

QUESTION PROMPT:
{question_prompt}

RUBRIC/ANSWER KEY:
{rubric}

STUDENT RESPONSE:
{student_response}

MAXIMUM POINTS: {max_points}

Please provide your grading in the following JSON format:
{{
    "score": <numerical_score>,
    "max_points": {max_points},
    "feedback": "<detailed_feedback_explaining_the_score>",
    "rubric_alignment": {{
        "criterion_1": <score_0_to_1>,
        "criterion_2": <score_0_to_1>,
        ...
    }}
}}

The rubric_alignment should break down how well the response meets each key criterion from the rubric. Each value should be between 0.0 and 1.0.

IMPORTANT: 
- Be strict but fair
- Reference specific parts of the student response
- Explain how the response aligns with the rubric
- Provide actionable feedback"""
    
    return system_prompt, user_prompt


def parse_grading_response(llm_response: str, max_points: float, question_number: Optional[str] = None) -> GradingResponse:
    """
    Parse the LLM response and extract grading information.
    Handles both JSON and text responses.
    """
    import json
    import re
    
    # Try to extract JSON from the response
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', llm_response, re.DOTALL)
    
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            score = float(data.get("score", 0))
            feedback = data.get("feedback", llm_response)
            rubric_alignment = data.get("rubric_alignment", {})
            
            # Ensure score is within bounds
            score = max(0, min(score, max_points))
            percentage = (score / max_points) * 100 if max_points > 0 else 0
            
            return GradingResponse(
                score=score,
                max_points=max_points,
                percentage=round(percentage, 2),
                feedback=feedback,
                rubric_alignment=rubric_alignment,
                timestamp=datetime.utcnow().isoformat(),
                question_number=question_number
            )
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from LLM response, using fallback parsing")
    
    # Fallback: extract score from text
    score_match = re.search(r'score[:\s]+(\d+\.?\d*)', llm_response, re.IGNORECASE)
    score = float(score_match.group(1)) if score_match else 0.0
    score = max(0, min(score, max_points))
    percentage = (score / max_points) * 100 if max_points > 0 else 0
    
    return GradingResponse(
        score=score,
        max_points=max_points,
        percentage=round(percentage, 2),
        feedback=llm_response,
        rubric_alignment={"overall": score / max_points if max_points > 0 else 0},
        timestamp=datetime.utcnow().isoformat(),
        question_number=question_number
    )


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with health check."""
    ollama_available = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            ollama_available = response.status_code == 200
    except Exception as e:
        logger.warning(f"Ollama health check failed: {e}")
    
    return HealthResponse(
        status="healthy",
        ollama_available=ollama_available,
        model=OLLAMA_MODEL
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return await root()


@app.post("/grade", response_model=GradingResponse)
async def grade_frq(request: GradingRequest):
    """
    Grade an AP FRQ response using the rubric.
    
    This endpoint uses Ollama to perform rubric-anchored grading with:
    - Low temperature (0.1) for deterministic outputs
    - CPU-only inference
    - Detailed feedback and rubric alignment scores
    """
    try:
        logger.info(f"Grading request received for question: {request.question_number or 'N/A'}")
        
        # Create grading prompt with rubric anchoring
        system_prompt, user_prompt = create_grading_prompt(
            request.student_response,
            request.rubric,
            request.question_prompt,
            request.max_points
        )
        
        # Call Ollama
        llm_response = await call_ollama(user_prompt, system_prompt)
        
        # Parse and return response
        grading_result = parse_grading_response(
            llm_response,
            request.max_points,
            request.question_number
        )
        
        logger.info(f"Grading completed: {grading_result.score}/{grading_result.max_points}")
        
        return grading_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error grading FRQ: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Grading failed: {str(e)}")


@app.post("/grade/batch", response_model=List[GradingResponse])
async def grade_batch(requests: List[GradingRequest]):
    """
    Grade multiple FRQ responses in batch.
    Processes sequentially to manage memory usage.
    """
    results = []
    for req in requests:
        try:
            result = await grade_frq(req)
            results.append(result)
        except Exception as e:
            logger.error(f"Error grading batch item: {e}")
            # Create error response
            results.append(GradingResponse(
                score=0.0,
                max_points=req.max_points,
                percentage=0.0,
                feedback=f"Error during grading: {str(e)}",
                rubric_alignment={},
                timestamp=datetime.utcnow().isoformat(),
                question_number=req.question_number
            ))
    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

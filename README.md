# Intelligrader - AP FRQ Grading Service

Production-grade FastAPI service for grading AP Free Response Questions (FRQs) using small local LLMs via Ollama. Optimized for 4GB RAM systems with deterministic outputs and CPU-only inference.

## Features

- **Rubric-Anchored Grading**: Uses detailed rubrics to provide consistent, fair grading
- **Deterministic Outputs**: Low temperature (0.1) and fixed seed for reproducible results
- **CPU-Only Inference**: No GPU required, optimized for CPU execution
- **Memory Optimized**: Designed for 4GB RAM systems with strict memory limits
- **Production Ready**: Includes Docker, Nginx reverse proxy, and CI/CD deployment
- **Batch Processing**: Support for grading multiple responses sequentially

## Architecture

```
┌─────────────┐
│   Nginx     │ (Port 80/443)
│  Reverse    │
│    Proxy    │
└──────┬──────┘
       │
┌──────▼──────┐
│  FastAPI    │ (Port 8000)
│   Service   │
└──────┬──────┘
       │
┌──────▼──────┐
│   Ollama    │ (Port 11434)
│   LLM API   │
└─────────────┘
```

## Prerequisites

- Docker and Docker Compose
- 4GB+ RAM available
- Linux server (tested on Ubuntu)
- For deployment: AWS Lightsail instance with SSH access

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd Intelligrader-Model-FastAPI-v1
   ```

2. **Start services**
   ```bash
   docker compose up -d
   ```

3. **Pull the Ollama model** (first time only)
   ```bash
   docker compose exec ollama ollama pull phi3:mini
   # or
   docker compose exec ollama ollama pull smollm:latest
   ```

4. **Verify health**
   ```bash
   curl http://localhost:8000/health
   ```

### Configuration

Set environment variables in `docker-compose.yml` or via `.env` file:

- `OLLAMA_MODEL`: Model to use (default: `phi3:mini`)
  - Options: `phi3:mini`, `smollm:latest`, `phi-2`, etc.

## API Endpoints

### Health Check
```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "ollama_available": true,
  "model": "phi3:mini"
}
```

### Grade Single FRQ
```bash
POST /grade
Content-Type: application/json

{
  "student_response": "The student's answer here...",
  "rubric": "Detailed rubric with scoring criteria...",
  "question_prompt": "The original question...",
  "max_points": 10,
  "question_number": "Q1"
}
```

Response:
```json
{
  "score": 8.5,
  "max_points": 10.0,
  "percentage": 85.0,
  "feedback": "Detailed feedback explaining the score...",
  "rubric_alignment": {
    "criterion_1": 0.9,
    "criterion_2": 0.8
  },
  "timestamp": "2024-01-01T12:00:00",
  "question_number": "Q1"
}
```

### Grade Batch
```bash
POST /grade/batch
Content-Type: application/json

[
  {
    "student_response": "...",
    "rubric": "...",
    "question_prompt": "...",
    "max_points": 10
  },
  ...
]
```

## Deployment to AWS Lightsail

### Setup

1. **Create Lightsail instance**
   - Ubuntu 22.04 LTS
   - At least 4GB RAM
   - Install Docker and Docker Compose

2. **Configure GitHub Secrets**
   - `HOST_IP`: Your Lightsail instance IP
   - `SSH_USERNAME`: Usually `ubuntu`
   - `SSH_PRIVATE_KEY`: Your SSH private key
   - `REPO_URL`: (Optional) Your repository URL

3. **Initial Server Setup**
   ```bash
   ssh ubuntu@<your-ip>
   mkdir -p ~/intelligrader
   cd ~/intelligrader
   git clone <your-repo-url> .
   docker compose up -d
   ```

4. **Automatic Deployment**
   - Push to `main` branch
   - GitHub Actions will automatically deploy

### Manual Deployment

```bash
cd ~/intelligrader
git pull origin main
docker compose up -d --build
```

## Memory Optimization

The service is configured with strict memory limits:

- **Ollama**: 2.5GB limit, 1.5GB reservation
- **FastAPI**: 1GB limit, 512MB reservation
- **Nginx**: 128MB limit

Total: ~4GB RAM usage

## Model Selection

Recommended models for 4GB RAM:

1. **phi3:mini** (Recommended)
   - ~2.3GB RAM
   - Good performance for grading tasks
   - Fast inference

2. **smollm:latest**
   - Very small footprint
   - Good for constrained environments

3. **phi-2**
   - Microsoft's 2.7B parameter model
   - May require more RAM

Pull models with:
```bash
docker compose exec ollama ollama pull <model-name>
```

## Monitoring

### Check Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f fastapi-app
docker compose logs -f ollama
docker compose logs -f nginx
```

### Check Status
```bash
docker compose ps
```

### Resource Usage
```bash
docker stats
```

## Troubleshooting

### Ollama Not Available
- Check if Ollama container is running: `docker compose ps`
- Check Ollama logs: `docker compose logs ollama`
- Verify model is pulled: `docker compose exec ollama ollama list`

### Out of Memory
- Reduce `OLLAMA_MAX_LOADED_MODELS` in docker-compose.yml
- Use a smaller model
- Reduce `num_thread` in Ollama settings

### Slow Grading
- Ensure model is loaded: `docker compose exec ollama ollama list`
- Check CPU usage: `docker stats`
- Consider using a smaller/faster model

## Development

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires Ollama running separately)
export OLLAMA_BASE_URL=http://localhost:11434
uvicorn main:app --reload
```

### Code Structure
- `main.py`: FastAPI application with grading logic
- `Dockerfile`: Multi-stage build for production
- `docker-compose.yml`: Service orchestration
- `nginx.conf`: Reverse proxy configuration
- `.github/workflows/deploy.yml`: CI/CD pipeline

## License

[Your License Here]

## Support

For issues and questions, please open an issue on GitHub.

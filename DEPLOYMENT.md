# Deployment Steps

## 1. Place GGUF Model
```bash
# On your Lightsail instance
mkdir -p /opt/models
# Upload your model file (e.g., via scp)
scp model.gguf user@instance:/opt/models/model.gguf
```

## 2. Update docker-compose.yml
Edit the volume mount path to your actual model location:
```yaml
volumes:
  - /opt/models/model.gguf:/app/models/model.gguf:ro
```

## 3. Build and Deploy
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 4. Test Inference
```bash
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain FastAPI in one sentence.", "max_tokens": 100}'
```

## 5. Monitor
```bash
docker-compose logs -f intelligrader-api
```

## Configuration Limits
- `MAX_THREADS`: CPU threads (default: 4)
- `CONTEXT_SIZE`: Max context window (default: 2048)
- `MAX_TOKENS`: Max generation tokens (default: 512)

Adjust in docker-compose.yml environment section based on your instance CPU/RAM.

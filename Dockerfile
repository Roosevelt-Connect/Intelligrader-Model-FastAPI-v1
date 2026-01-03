FROM python:3.11-slim AS builder

# Install build dependencies for llama.cpp
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Clone and build llama.cpp (CPU-only)
WORKDIR /build
RUN git clone https://github.com/ggerganov/llama.cpp.git && \
    cd llama.cpp && \
    cmake -B build -DLLAMA_CURL=OFF -DLLAMA_METAL=OFF -DLLAMA_CUDA=OFF -DLLAMA_BLAS=OFF && \
    cmake --build build --config Release -j$(nproc) && \
    cp build/bin/llama-server /build/llama-server && \
    chmod +x /build/llama-server

# Final runtime image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy llama-server binary from builder
COPY --from=builder /build/llama-server /usr/local/bin/llama-server

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

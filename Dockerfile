FROM python:3.11-slim

LABEL org.opencontainers.image.title="medagent-core"
LABEL org.opencontainers.image.description="Auditable biomedical AI decision support agent — RESEARCH USE ONLY"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching)
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install ".[dev]" --no-deps && \
    pip install .

# Copy source after deps are installed
COPY src/ ./src/
COPY data/ ./data/
COPY scripts/ ./scripts/

# Create required directories
RUN mkdir -p /app/data/kb_index /app/results

# Build the sample KB index at image build time
RUN python scripts/ingest_kb.py --sample --output /app/data/kb_index/

EXPOSE 8000

# Run as non-root user for security
RUN useradd -m -u 1000 medagent && chown -R medagent:medagent /app
USER medagent

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "medagent.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]

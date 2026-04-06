# Stage 1: Builder
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv "setuptools<81"
ENV NLTK_DATA=/usr/local/share/nltk_data

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN uv venv && uv pip install --python .venv/bin/python "setuptools<81" && uv sync --frozen --no-dev --no-build-isolation-package grpcio
COPY scripts/download_nltk_data.py ./scripts/download_nltk_data.py
RUN .venv/bin/python scripts/download_nltk_data.py

# Stage 2: Runtime
FROM python:3.12-slim AS runtime
ENV NLTK_DATA=/usr/local/share/nltk_data
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /usr/local/share/nltk_data /usr/local/share/nltk_data

# Copy application code only. Runtime data is mounted via docker-compose.
COPY src/ ./src/
RUN mkdir -p /app/data/chroma /app/data/evals /app/data/evals_comprehensive_ablation /app/data/processed /app/data/raw

EXPOSE 8000

# Use production entrypoint
CMD ["python", "-m", "src.cli.serve_production"]

# Stage 1: Builder
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
RUN pip install uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY scripts/ ./scripts/

RUN uv sync --frozen --no-dev
RUN .venv/bin/python scripts/download_nltk_data.py

# Stage 2: Runtime
FROM python:3.13-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ ./src/
COPY data/ ./data/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

EXPOSE 8000

# Use production entrypoint
CMD ["python", "-m", "src.cli.serve_production"]

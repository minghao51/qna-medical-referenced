# Stage 1: Builder
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
ENV NLTK_DATA=/usr/local/share/nltk_data

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev
COPY scripts/download_nltk_data.py ./scripts/download_nltk_data.py
RUN .venv/bin/python scripts/download_nltk_data.py

# Stage 2: Runtime
FROM python:3.13-slim AS runtime
ENV NLTK_DATA=/usr/local/share/nltk_data

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /usr/local/share/nltk_data /usr/local/share/nltk_data

# Copy application code and only the runtime data that must ship with the image.
COPY src/ ./src/
COPY data/vectors/ ./data/vectors/
RUN mkdir -p /app/data/evals /app/data/processed /app/data/raw

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

EXPOSE 8000

# Use production entrypoint
CMD ["python", "-m", "src.cli.serve_production"]

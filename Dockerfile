FROM python:3.13-slim

RUN pip install uv

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY data/ ./data/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "src.main"]

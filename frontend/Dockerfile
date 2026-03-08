# Stage 1: Builder
FROM oven/bun:1-alpine AS builder

WORKDIR /app

COPY frontend/package.json ./package.json
COPY frontend/bun.lock ./bun.lock
RUN bun install --frozen-lockfile

COPY frontend/ ./
RUN bun run build

# Stage 2: Runtime
FROM oven/bun:1-alpine AS runtime

WORKDIR /app

COPY --from=builder /app /app

EXPOSE 5173

# Production preview server
CMD ["bun", "run", "preview", "--host", "0.0.0.0", "--port", "5173"]

# Stage 1: Builder
FROM oven/bun:1.2.5-alpine AS builder

WORKDIR /app

COPY frontend/package.json ./package.json
COPY frontend/bun.lock ./bun.lock
RUN bun install --frozen-lockfile

COPY frontend/ ./
RUN bun run build

# Stage 2: Runtime
FROM node:20-alpine AS runtime

WORKDIR /app

ENV HOST=0.0.0.0
ENV PORT=5173
ENV NODE_ENV=production

COPY --from=builder /app/build ./build

EXPOSE 5173

CMD ["node", "build"]

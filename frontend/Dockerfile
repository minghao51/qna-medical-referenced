# Stage 1: Builder
FROM oven/bun:1.3.9-alpine AS builder

WORKDIR /app

ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

# Copy lockfile and install deps first (better layer caching)
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# Copy source and build
COPY . .
RUN bun run build

# Stage 2: Runtime
FROM oven/bun:1.3.9-alpine AS runtime

WORKDIR /app

ENV HOST=0.0.0.0
ENV PORT=5173
ENV NODE_ENV=production

# Only production deps needed at runtime
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production

COPY --from=builder /app/build ./build

EXPOSE 5173

CMD ["bun", "run", "start"]

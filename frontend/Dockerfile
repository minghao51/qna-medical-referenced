# Stage 1: Builder
FROM oven/bun:1.2.5-alpine AS builder

WORKDIR /app

# Accept build-time arguments
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

COPY package.json ./package.json
COPY bun.lock ./bun.lock
RUN bun install --frozen-lockfile

COPY . ./
RUN bun run build

# Stage 2: Runtime
FROM oven/bun:1.2.5-alpine AS runtime

WORKDIR /app

ENV HOST=0.0.0.0
ENV PORT=5173
ENV NODE_ENV=production

COPY package.json ./package.json
COPY bun.lock ./bun.lock
RUN bun install --frozen-lockfile --production
COPY --from=builder /app/build ./build

EXPOSE 5173

CMD ["bun", "run", "start"]

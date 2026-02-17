FROM oven/bun:1-alpine

WORKDIR /app

COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

COPY frontend/ ./

EXPOSE 5173

CMD ["bun", "run", "dev", "--host"]

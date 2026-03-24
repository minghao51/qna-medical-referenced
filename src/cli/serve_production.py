#!/usr/bin/env python3
"""Production API server entrypoint (no hot-reload)."""

import uvicorn


def main() -> None:
    uvicorn.run(
        "src.app.factory:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,  # Single worker (vector store in-memory)
        limit_concurrency=20,  # Prevent memory exhaustion
        timeout_keep_alive=30,
        log_level="info",
    )


if __name__ == "__main__":
    main()

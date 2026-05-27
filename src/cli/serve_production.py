#!/usr/bin/env python3
"""Production API server entrypoint (no hot-reload)."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the production API server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")  # nosec B104
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers (default: 1)")
    args = parser.parse_args()
    uvicorn.run(
        "src.app.factory:app",
        host=args.host,  # nosec B104
        port=args.port,
        reload=False,
        workers=args.workers,
        limit_concurrency=20,
        timeout_keep_alive=30,
        log_level="info",
    )


if __name__ == "__main__":
    main()

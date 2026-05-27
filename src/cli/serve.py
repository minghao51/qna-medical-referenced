"""Canonical API server entrypoint."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the development API server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")  # nosec B104
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    args = parser.parse_args()
    uvicorn.run("src.app.factory:app", host=args.host, port=args.port, reload=True)  # nosec B104


if __name__ == "__main__":
    main()

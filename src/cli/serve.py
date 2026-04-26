"""Canonical API server entrypoint."""

import uvicorn


def main() -> None:
    uvicorn.run("src.app.factory:app", host="0.0.0.0", port=8000, reload=True)  # nosec B104


if __name__ == "__main__":
    main()

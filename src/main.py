"""Deprecated compatibility module for the API app entrypoint."""

import warnings

from src.app.factory import app, create_app

__all__ = ["app", "create_app"]

warnings.warn(
    "src.main is deprecated; use 'src.app.factory' (or run 'python -m src.cli.serve').",
    DeprecationWarning,
    stacklevel=2,
)


if __name__ == "__main__":
    from src.cli.serve import main

    main()

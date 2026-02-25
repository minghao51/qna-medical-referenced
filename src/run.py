#!/usr/bin/env python
"""Deprecated server runner wrapper."""

import warnings

from src.cli.serve import main

if __name__ == "__main__":
    warnings.warn(
        "src.run is deprecated; use 'python -m src.cli.serve'.",
        DeprecationWarning,
        stacklevel=2,
    )
    main()

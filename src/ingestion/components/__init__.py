"""Hamilton components for data ingestion pipeline."""

from __future__ import annotations

import importlib

_module_names = [
    "01_download",
    "02_parse",
    "03_chunk",
    "04_enrich",
    "05_reference",
    "06_embedding",
]

_modules = [importlib.import_module(f"src.ingestion.components.{name}") for name in _module_names]

__all__ = list(_module_names)

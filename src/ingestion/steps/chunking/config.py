"""Chunking configuration and runtime overrides."""

from __future__ import annotations

import copy

DEFAULT_SOURCE_CHUNK_CONFIGS = {
    "pdf": {
        "chunk_size": 650,
        "chunk_overlap": 80,
        "strategy": "recursive",
        "min_chunk_size": 140,
    },
    "markdown": {
        "chunk_size": 600,
        "chunk_overlap": 80,
        "strategy": "recursive",
        "min_chunk_size": 80,
    },
    "default": {
        "chunk_size": 650,
        "chunk_overlap": 80,
        "strategy": "recursive",
        "min_chunk_size": 120,
    },
}
STRUCTURED_CHUNKING_ENABLED = True
SOURCE_CHUNK_CONFIGS_OVERRIDE: dict | None = None


def is_structured_chunking_enabled() -> bool:
    return STRUCTURED_CHUNKING_ENABLED


def set_structured_chunking_enabled(enabled: bool) -> None:
    global STRUCTURED_CHUNKING_ENABLED
    STRUCTURED_CHUNKING_ENABLED = bool(enabled)


def set_source_chunk_configs(configs: dict | None) -> None:
    global SOURCE_CHUNK_CONFIGS_OVERRIDE
    SOURCE_CHUNK_CONFIGS_OVERRIDE = copy.deepcopy(configs) if configs is not None else None


def get_source_chunk_configs() -> dict:
    cfg = copy.deepcopy(DEFAULT_SOURCE_CHUNK_CONFIGS)
    if SOURCE_CHUNK_CONFIGS_OVERRIDE:
        for key, value in SOURCE_CHUNK_CONFIGS_OVERRIDE.items():
            if key in cfg and isinstance(value, dict):
                cfg[key].update(value)
            else:
                cfg[key] = copy.deepcopy(value)
    return cfg

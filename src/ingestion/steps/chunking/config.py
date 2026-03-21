"""Chunking configuration and runtime overrides."""

from __future__ import annotations

import copy

DEFAULT_SOURCE_CHUNK_CONFIGS = {
    "pdf": {
        "chunk_size": 512,
        "chunk_overlap": 64,
        "strategy": "custom_recursive",
        "min_chunk_size": 100,
        "embedding_model": "text-embedding-v4",
    },
    "markdown": {
        "chunk_size": 512,
        "chunk_overlap": 64,
        "strategy": "custom_recursive",
        "min_chunk_size": 80,
        "embedding_model": "text-embedding-v4",
    },
    "default": {
        "chunk_size": 512,
        "chunk_overlap": 64,
        "strategy": "custom_recursive",
        "min_chunk_size": 100,
        "embedding_model": "text-embedding-v4",
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

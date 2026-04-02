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
    "html": {
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

RECOMMENDED_STRATEGIES = {
    "pdf": "chonkie_semantic",
    "markdown": "chonkie_recursive",
    "html": "chonkie_recursive",
    "clinical_notes": "chonkie_late",
    "research_paper": "chonkie_semantic",
    "guideline": "chonkie_semantic",
}

STRUCTURED_CHUNKING_ENABLED = True
SOURCE_CHUNK_CONFIGS_OVERRIDE: dict | None = None
AUTO_SELECT_STRATEGY = False


def is_structured_chunking_enabled() -> bool:
    return STRUCTURED_CHUNKING_ENABLED


def set_structured_chunking_enabled(enabled: bool) -> None:
    global STRUCTURED_CHUNKING_ENABLED
    STRUCTURED_CHUNKING_ENABLED = bool(enabled)


def set_auto_select_strategy(enabled: bool) -> None:
    global AUTO_SELECT_STRATEGY
    AUTO_SELECT_STRATEGY = bool(enabled)


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
    if AUTO_SELECT_STRATEGY:
        for source_type, base_cfg in cfg.items():
            if isinstance(base_cfg, dict) and "strategy" in base_cfg:
                recommended = RECOMMENDED_STRATEGIES.get(source_type)
                if recommended:
                    base_cfg["strategy"] = recommended
    return cfg

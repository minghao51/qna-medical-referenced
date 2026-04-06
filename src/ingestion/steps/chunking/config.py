"""Chunking configuration and runtime overrides."""

from __future__ import annotations

import copy

from src.config.context import get_runtime_state

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


def is_structured_chunking_enabled() -> bool:
    return get_runtime_state().structured_chunking_enabled


def set_structured_chunking_enabled(enabled: bool) -> None:
    get_runtime_state().structured_chunking_enabled = bool(enabled)


def set_auto_select_strategy(enabled: bool) -> None:
    get_runtime_state().auto_select_strategy = bool(enabled)


def set_source_chunk_configs(configs: dict | None) -> None:
    get_runtime_state().source_chunk_configs_override = (
        copy.deepcopy(configs) if configs is not None else None
    )


def get_source_chunk_configs() -> dict:
    state = get_runtime_state()
    cfg = copy.deepcopy(DEFAULT_SOURCE_CHUNK_CONFIGS)
    override = state.source_chunk_configs_override
    if override:
        for key, value in override.items():
            if key in cfg and isinstance(value, dict):
                cfg[key].update(value)
            else:
                cfg[key] = copy.deepcopy(value)
    if state.auto_select_strategy:
        for source_type, base_cfg in cfg.items():
            if isinstance(base_cfg, dict) and "strategy" in base_cfg:
                recommended = RECOMMENDED_STRATEGIES.get(source_type)
                if recommended:
                    base_cfg["strategy"] = recommended
    return cfg

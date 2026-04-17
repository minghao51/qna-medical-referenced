"""Chunking configuration and runtime overrides."""

from __future__ import annotations

import copy
import logging

from src.config.context import get_runtime_state

logger = logging.getLogger(__name__)

_VALID_STRATEGIES = {
    "custom_recursive",
    "chonkie_semantic",
    "chonkie_recursive",
    "chonkie_late",
    "medical_semantic",
}

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
    "clinical_notes": "medical_semantic",
    "research_paper": "chonkie_semantic",
    "guideline": "medical_semantic",
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


def get_source_chunk_configs(strict_validation: bool = False) -> dict:
    """Get source chunking configurations with optional validation.

    Args:
        strict_validation: If True, raises ValueError for invalid configs.
            If False (default), logs warnings and resets to defaults.

    Returns:
        Dictionary of source type to chunking configuration.

    Raises:
        ValueError: If strict_validation=True and any config is invalid.
    """
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

    errors = []
    for source_type, chunk_cfg in cfg.items():
        if not isinstance(chunk_cfg, dict):
            continue
        chunk_size = chunk_cfg.get("chunk_size", 0)
        if not isinstance(chunk_size, int) or chunk_size < 64 or chunk_size > 8192:
            msg = f"Invalid chunk_size={chunk_size} for {source_type}. Must be int between 64 and 8192."
            if strict_validation:
                errors.append(msg)
            else:
                logger.warning("%s Resetting to 512.", msg)
                chunk_cfg["chunk_size"] = 512
        min_size = chunk_cfg.get("min_chunk_size", 0)
        if not isinstance(min_size, int) or min_size < 10:
            msg = f"Invalid min_chunk_size={min_size} for {source_type}. Must be int >= 10."
            if strict_validation:
                errors.append(msg)
            else:
                logger.warning("%s Resetting to 50.", msg)
                chunk_cfg["min_chunk_size"] = 50
        strategy = chunk_cfg.get("strategy", "")
        if strategy and strategy not in _VALID_STRATEGIES:
            msg = f"Unknown strategy={strategy!r} for {source_type}. Must be one of: {_VALID_STRATEGIES}."
            if strict_validation:
                errors.append(msg)
            else:
                logger.warning("%s Falling back to custom_recursive.", msg)
                chunk_cfg["strategy"] = "custom_recursive"

    if errors:
        raise ValueError(
            "Chunking configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )
    return cfg

"""Shared logging helpers for backend request handling."""

from __future__ import annotations

import json
import logging
from logging.config import dictConfig
from typing import Any


def configure_logging(level: str = "INFO") -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "level": level.upper(),
                }
            },
            "root": {"handlers": ["default"], "level": level.upper()},
        }
    )


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload = {"event": event, **{k: v for k, v in fields.items() if v is not None}}
    logger.log(level, json.dumps(payload, sort_keys=True, default=str))

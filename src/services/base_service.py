"""Base service class with common functionality."""

from __future__ import annotations

import logging


class BaseService:
    """Base class for all services.

    Provides common functionality like logging and configuration access.
    Subclasses should accept dependencies via constructor injection.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
    def logger(self) -> logging.Logger:
        """Return logger for this service."""
        return self._logger

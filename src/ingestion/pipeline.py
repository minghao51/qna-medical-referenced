"""Compatibility shim for the offline pipeline orchestration module."""

from src.usecases.pipeline import main, run_pipeline

__all__ = ["main", "run_pipeline"]

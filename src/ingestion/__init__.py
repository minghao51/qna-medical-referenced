"""Offline ingestion package exports."""

__all__ = ["run_pipeline"]


def __getattr__(name: str):
    if name == "run_pipeline":
        from src.usecases.pipeline import run_pipeline

        return run_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

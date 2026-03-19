"""Pipeline quality assessment utilities."""

__all__ = ["run_assessment"]


def run_assessment(*args, **kwargs):
    """Import the heavy assessment pipeline only when explicitly invoked."""
    from src.evals.pipeline_assessment import run_assessment as _run_assessment

    return _run_assessment(*args, **kwargs)

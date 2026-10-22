"""Pipeline quality assessment utilities."""

import os

# DeepEval analytics are a separate hosted destination, never authorized by the
# application allowlisted Logfire export modes. Set the public opt-out before
# any lazy DeepEval import; do not inspect credentials or analytics files.
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"

__all__ = ["run_assessment"]


def run_assessment(*args, **kwargs):
    """Import the heavy assessment pipeline only when explicitly invoked."""
    from src.evals.assessment.orchestrator import run_assessment as _run_assessment

    return _run_assessment(*args, **kwargs)

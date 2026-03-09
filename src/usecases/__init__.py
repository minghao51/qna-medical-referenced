"""Use-case layer exports."""

__all__ = ["process_chat_message", "run_pipeline"]


def __getattr__(name: str):
    if name == "process_chat_message":
        from src.usecases.chat import process_chat_message

        return process_chat_message
    if name == "run_pipeline":
        from src.usecases.pipeline import run_pipeline

        return run_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

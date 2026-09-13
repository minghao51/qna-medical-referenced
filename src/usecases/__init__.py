"""Use-case layer exports."""

__all__ = ["process_chat_message"]


def __getattr__(name: str):
    if name == "process_chat_message":
        from src.usecases.chat import process_chat_message

        return process_chat_message
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

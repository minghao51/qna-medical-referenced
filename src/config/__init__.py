from src.config.paths import (
    CHAT_HISTORY_FILE,
    CHROMA_PERSIST_DIRECTORY,
    DATA_DIR,
    DATA_PROCESSED_DIR,
    DATA_RAW_DIR,
    RATE_LIMIT_DB,
)
from src.config.settings import settings as settings

VECTOR_DIR = CHROMA_PERSIST_DIRECTORY

__all__ = [
    "settings",
    "VECTOR_DIR",
    "CHROMA_PERSIST_DIRECTORY",
    "DATA_DIR",
    "DATA_PROCESSED_DIR",
    "DATA_RAW_DIR",
    "CHAT_HISTORY_FILE",
    "RATE_LIMIT_DB",
]

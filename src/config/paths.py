"""Canonical filesystem paths used by the backend."""

from pathlib import Path

from src.config.settings import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW_DIR = PROJECT_ROOT / settings.storage.data_dir
DATA_PROCESSED_DIR = DATA_DIR / "processed"
CHROMA_PERSIST_DIRECTORY = PROJECT_ROOT / settings.storage.chroma_persist_directory
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"
RATE_LIMIT_DB = DATA_DIR / "rate_limits.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_PERSIST_DIRECTORY.mkdir(parents=True, exist_ok=True)

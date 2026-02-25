"""Canonical filesystem paths used by the backend."""

from pathlib import Path

from src.config.settings import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW_DIR = PROJECT_ROOT / settings.data_dir
VECTOR_DIR = PROJECT_ROOT / settings.vector_dir
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"
RATE_LIMIT_DB = DATA_DIR / "rate_limits.db"

# Ensure commonly used parent dirs exist for runtime writes.
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_DIR.mkdir(parents=True, exist_ok=True)


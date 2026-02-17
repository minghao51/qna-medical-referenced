from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    gemini_api_key: str = ""
    api_keys: Optional[str] = None
    model_name: str = "gemini-2.0-flash"
    embedding_model: str = "gemini-embedding-001"
    collection_name: str = "medical_docs"
    data_dir: str = "data/raw"
    vector_dir: str = "data/vectors"
    max_message_length: int = 2000
    rate_limit_per_minute: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0


settings = Settings()

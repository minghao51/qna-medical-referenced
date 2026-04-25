"""Storage configuration."""

from pydantic import BaseModel


class StorageConfig(BaseModel):
    collection_name: str = "medical_docs"
    data_dir: str = "data/raw"
    chroma_persist_directory: str = "data/chroma"
    chroma_server_host: str = ""
    chroma_server_port: int = 8000

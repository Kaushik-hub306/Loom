"""Loom configuration from environment variables."""

import os
from dataclasses import dataclass


@dataclass
class StorageConfig:
    backend: str = "json"          # "json" or "postgres"
    project_root: str = ""         # project directory (for JSON mode)
    database_url: str = ""         # postgresql://user:pass@host:5432/db
    db_pool_min: int = 2
    db_pool_max: int = 20


def get_config() -> StorageConfig:
    return StorageConfig(
        backend=os.getenv("LOOM_STORAGE_BACKEND", "json"),
        project_root=os.getenv("LOOM_PROJECT_ROOT", os.getcwd()),
        database_url=os.getenv("LOOM_DATABASE_URL", ""),
        db_pool_min=int(os.getenv("LOOM_DB_POOL_MIN", "2")),
        db_pool_max=int(os.getenv("LOOM_DB_POOL_MAX", "20")),
    )

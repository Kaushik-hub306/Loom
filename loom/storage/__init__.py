"""Storage backends for the Loom observation store.

Provides a pluggable abstraction so the same engine can run in:
- Git-native / self-hosted mode (JSON file backend — single org)
- Cloud / SaaS mode (SQLite backend — multi-org)
"""

from __future__ import annotations

from .backend import StorageBackend
from .file_backend import JSONFileBackend

__all__ = [
    "StorageBackend",
    "JSONFileBackend",
]

# SQLite backend is available only when sqlite3 is importable (always
# available in CPython stdlib), but we guard the import for clarity.
try:
    from .sqlite_backend import SQLiteBackend

    __all__.append("SQLiteBackend")
except ImportError:
    pass

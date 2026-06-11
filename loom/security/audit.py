"""AuditLog — records all operations for accountability."""

import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLog:
    """Append-only audit log of all Loom operations."""

    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)

    def record(self, action: str, details: dict | None = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "details": details or {},
        }
        line = json.dumps(entry)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a") as f:
            f.write(line + "\n")

    def read(self, limit: int = 100) -> list[dict]:
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path) as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries[-limit:]

    def count(self) -> int:
        if not self.log_path.exists():
            return 0
        return sum(1 for _ in open(self.log_path))

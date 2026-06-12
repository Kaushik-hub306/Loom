"""AuditLog — records all operations for accountability."""

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class AuditAction(str, Enum):
    RULE_CREATED = "rule_created"
    RULE_PROMOTED = "rule_promoted"
    RULE_DEMOTED = "rule_demoted"
    RULE_ARCHIVED = "rule_archived"
    OBSERVATION_CREATED = "observation_created"
    OBSERVATION_PROMOTED = "observation_promoted"
    OBSERVATION_DEMOTED = "observation_demoted"
    OBSERVATION_DELETED = "observation_deleted"
    INTEGRITY_CHECK_PASSED = "integrity_check_passed"
    INTEGRITY_CHECK_FAILED = "integrity_check_failed"


def _audit_log_path() -> Path:
    return Path(os.environ["LOOM_STORE_DIR"]) / "audit.jsonl"


def log(action: AuditAction, agent: str, details: dict) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action.value if isinstance(action, AuditAction) else action,
        "agent": agent,
        "details": details,
    }
    p = _audit_log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(entry) + "\n")


def verify_audit_invariants() -> tuple[bool, str]:
    p = _audit_log_path()
    if not p.exists():
        return True, "No audit log — nothing to verify"

    entries = []
    with open(p) as f:
        for line in f:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    archived_ids = set()
    for e in entries:
        rid = e.get("details", {}).get("rule_id", "")
        action = e.get("action", "")
        if action == "rule_archived":
            archived_ids.add(rid)
        if action == "rule_created" and rid in archived_ids:
            return False, f"Invariant violation: {rid} created after archival"

    return True, "All audit invariants hold"


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

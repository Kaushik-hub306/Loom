"""Append-only mutation log for the memory store."""

import enum
import json
import os
from datetime import datetime, timezone
from pathlib import Path


AUDIT_FILE = "audit.jsonl"


class AuditAction(enum.Enum):
    RULE_CREATED = "rule_created"
    RULE_PROMOTED = "rule_promoted"
    RULE_DEMOTED = "rule_demoted"
    RULE_ARCHIVED = "rule_archived"
    SECRETS_REDACTED = "secrets_redacted"


def _audit_path() -> Path:
    store_dir = Path(os.environ.get("LOOM_STORE_DIR", Path.cwd() / ".loom"))
    return store_dir / AUDIT_FILE


def log(action: AuditAction, actor: str, metadata: dict | None = None) -> None:
    """Append one audit entry to the append-only log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action.value,
        "actor": actor,
        "metadata": metadata or {},
    }
    path = _audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(entry) + "\n")


def verify_audit_invariants(store_path: Path | None = None) -> tuple[bool, str]:
    """Check hard invariants across the audit log.

    Invariant: a rule must not be 'created' after it has been 'archived'.
    Returns (valid, message).
    """
    path = _audit_path() if store_path is None else store_path / AUDIT_FILE
    if not path.exists():
        return True, "No audit log — nothing to verify."

    archived: set[str] = set()
    created: set[str] = set()

    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        action = entry.get("action", "")
        meta = entry.get("metadata", {})
        rule_id = meta.get("rule_id") or meta.get("rule", "")

        if action == AuditAction.RULE_ARCHIVED.value and rule_id:
            archived.add(rule_id)

        if action == AuditAction.RULE_CREATED.value and rule_id:
            if rule_id in archived:
                return False, (
                    f"Audit invariant violated: rule '{rule_id}' was created "
                    f"at {entry['timestamp']} after it was already archived."
                )
            created.add(rule_id)

    return True, "Audit invariants hold."

"""Private session gate — suppress shared-memory writes when privacy is requested."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


_PRIVATE_MODE_ENV = "LOOM_PRIVATE_MODE"
_PRIVATE_LOG = "private.jsonl"


def should_skip_write() -> bool:
    """Return True when private mode is active — writes must be suppressed."""
    return os.environ.get(_PRIVATE_MODE_ENV) == "1"


def record_private_outcome(
    *,
    domain: str,
    outcome: str,
    feedback: str,
    source_url: str = "",
    reason: str = "",
) -> None:
    """Log an outcome that was *not* persisted to shared memory because private mode was on."""
    store_dir = Path(os.environ.get("LOOM_STORE_DIR", Path.cwd() / ".loom"))
    log_path = store_dir / _PRIVATE_LOG

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domain": domain,
        "outcome": outcome,
        "feedback": feedback,
        "source_url": source_url,
        "reason": reason,
    }

    store_dir.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as fh:
        fh.write(json.dumps(entry) + "\n")

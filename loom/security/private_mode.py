"""PrivateMode — controls whether rules store source-specific data."""

import json
import os
import re
from pathlib import Path


def should_skip_write() -> bool:
    return os.getenv("LOOM_PRIVATE_MODE", "0") == "1"


def record_private_outcome(
    domain: str,
    outcome: str,
    feedback: str,
    source_url: str,
    reason: str,
) -> None:
    store_dir = Path(os.environ["LOOM_STORE_DIR"])
    log_path = store_dir / "private.jsonl"
    entry = {
        "domain": domain,
        "outcome": outcome,
        "feedback": feedback,
        "source_url": source_url,
        "reason": reason,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


class PrivateMode:
    """Controls privacy settings for Loom."""

    def __init__(self, enabled: bool | None = None):
        if enabled is None:
            enabled = os.getenv("LOOM_PRIVATE_MODE", "0") == "1"
        self.enabled = enabled

    def sanitize_feedback(self, feedback: str) -> str:
        if not self.enabled:
            return feedback
        feedback = re.sub(r"https?://\S+", "[URL]", feedback)
        feedback = re.sub(r"/home/\S+", "[PATH]", feedback)
        feedback = re.sub(r"/Users/\S+", "[PATH]", feedback)
        return feedback

    def should_store_source_url(self) -> bool:
        return not self.enabled

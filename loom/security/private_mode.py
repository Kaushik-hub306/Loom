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
    """Controls privacy settings for Loom.

    Private mode can be toggled by either the environment variable
    ``LOOM_PRIVATE_MODE=1`` or by calling ``set_mode()`` at runtime.
    If either mechanism is active, private mode is enabled.
    """

    def __init__(self, enabled: bool | None = None):
        if enabled is None:
            enabled = os.getenv("LOOM_PRIVATE_MODE", "0") == "1"
        self.enabled = enabled
        self._session_enabled: bool = False

    def set_mode(self, enabled: bool) -> None:
        """Enable or disable private mode for the current session.

        This toggles the in-memory flag only; it takes precedence
        alongside the environment variable in ``should_skip_write``.
        """
        self._session_enabled = enabled

    @property
    def is_active(self) -> bool:
        """Return *True* if private mode is active via any mechanism."""
        return self.enabled or self._session_enabled

    def sanitize_feedback(self, feedback: str) -> str:
        if not self.is_active:
            return feedback
        feedback = re.sub(r"https?://\S+", "[URL]", feedback)
        feedback = re.sub(r"/home/\S+", "[PATH]", feedback)
        feedback = re.sub(r"/Users/\S+", "[PATH]", feedback)
        return feedback

    def should_skip_write(self) -> bool:
        """Return *True* if writes should be skipped (private mode active).

        Checks both the environment variable and the per-session toggle.
        """
        return os.getenv("LOOM_PRIVATE_MODE", "0") == "1" or self._session_enabled

    def should_store_source_url(self) -> bool:
        return not self.is_active

"""PrivateMode — controls whether rules store source-specific data."""

import os


class PrivateMode:
    """Controls privacy settings for Loom."""

    def __init__(self, enabled: bool | None = None):
        if enabled is None:
            enabled = os.getenv("LOOM_PRIVATE_MODE", "0") == "1"
        self.enabled = enabled

    def sanitize_feedback(self, feedback: str) -> str:
        if not self.enabled:
            return feedback
        # Strip identifying info: URLs, paths, names
        import re
        feedback = re.sub(r"https?://\S+", "[URL]", feedback)
        feedback = re.sub(r"/home/\S+", "[PATH]", feedback)
        feedback = re.sub(r"/Users/\S+", "[PATH]", feedback)
        return feedback

    def should_store_source_url(self) -> bool:
        return not self.enabled

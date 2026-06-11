"""Redactor — scrubs sensitive data from feedback before storage."""

import re


class Redactor:
    """Redacts sensitive information from text."""

    PATTERNS = [
        (r"-----BEGIN [A-Z ]+-----[\s\S]*?-----END [A-Z ]+-----", "[REDACTED KEY]"),
        (r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}", "[REDACTED TOKEN]"),
        (r"(?:sk|pk|rk)-[A-Za-z0-9]{20,}", "[REDACTED API KEY]"),
        (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED EMAIL]"),
        (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED IP]"),
    ]

    def redact(self, text: str) -> str:
        for pattern, replacement in self.PATTERNS:
            text = re.sub(pattern, replacement, text)
        return text

    def is_clean(self, text: str) -> bool:
        return self.redact(text) == text

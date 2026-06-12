"""Redactor — scrubs sensitive data from feedback before storage."""

import re
from dataclasses import dataclass


@dataclass
class RedactResult:
    text: str
    secrets_found: int = 0


PATTERNS = [
    (r"AKIA[A-Z0-9]{16}", "[REDACTED:aws-access-key]"),
    (r"-----BEGIN [A-Z ]+-----[\s\S]*?-----END [A-Z ]+-----", "[REDACTED KEY]"),
    (r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}", "[REDACTED TOKEN]"),
    (r"(?:sk|pk|rk)-[A-Za-z0-9]{20,}", "[REDACTED API KEY]"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED EMAIL]"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED IP]"),
]


def redact_text(text: str) -> RedactResult:
    secrets_found = 0
    for pattern, replacement in PATTERNS:
        matches = re.findall(pattern, text)
        secrets_found += len(matches)
        text = re.sub(pattern, replacement, text)
    return RedactResult(text=text, secrets_found=secrets_found)


def redact_feedback(text: str) -> str:
    return redact_text(text).text


class Redactor:
    """Redacts sensitive information from text."""

    def redact(self, text: str) -> str:
        return redact_feedback(text)

    def is_clean(self, text: str) -> bool:
        return self.redact(text) == text

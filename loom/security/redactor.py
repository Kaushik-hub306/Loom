"""Secrets detection and redaction — 10 patterns covering common credential formats."""

import re
from dataclasses import dataclass, field


@dataclass
class RedactResult:
    text: str
    secrets_found: int = 0
    redacted_types: list[str] = field(default_factory=list)


# Ordered list of (label, compiled-regex, replacement-tag).
# Order matters: run BEGIN/END private-key blocks first so we catch
# multiline secrets before single-line patterns split them.
_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # 1. Private key blocks (multiline)
    (
        "private-key",
        re.compile(r"-----BEGIN[ A-Z]+PRIVATE KEY-----[ \t]*\n.*?\n[ \t]*-----END[ A-Z]+PRIVATE KEY-----", re.DOTALL),
        "[REDACTED:private-key]",
    ),
    # 2. AWS Access Key ID
    (
        "aws-access-key",
        re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED:aws-access-key]",
    ),
    # 3. AWS Secret Access Key
    (
        "aws-secret-key",
        re.compile(r"\b(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])"),
        "[REDACTED:aws-secret-key]",
    ),
    # 4. GitHub personal access tokens
    (
        "github-token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,255}\b"),
        "[REDACTED:github-token]",
    ),
    # 5. Google API key
    (
        "google-api-key",
        re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
        "[REDACTED:google-api-key]",
    ),
    # 6. Stripe secret / restricted keys
    (
        "stripe-key",
        re.compile(r"\b[rs]k_(?:live|test)_[0-9a-zA-Z]{24,99}\b"),
        "[REDACTED:stripe-key]",
    ),
    # 7. OpenAI API keys
    (
        "openai-key",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9\-_]{32,}\b"),
        "[REDACTED:openai-key]",
    ),
    # 8. Anthropic API keys
    (
        "anthropic-key",
        re.compile(r"\bsk-ant-(?:api|admin)[0-9]{2}-[A-Za-z0-9\-_]{32,}\b"),
        "[REDACTED:anthropic-key]",
    ),
    # 9. JWT tokens (three base64url segments)
    (
        "jwt-token",
        re.compile(r"\beyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.?[A-Za-z0-9\-_]*\b"),
        "[REDACTED:jwt-token]",
    ),
    # 10. Generic high-entropy-looking tokens in assignment / export lines.
    # Avoid matching values that were already redacted by earlier patterns.
    (
        "generic-secret",
        re.compile(
            r"""(?:(?:export\s+)?[A-Z_][A-Z0-9_]{0,40}=|(?:token|secret|key|password|passwd)\s*[:=]\s*)"""
            r"""((?!\[REDACTED:)[\x21-\x7e]{20,})""",
            re.IGNORECASE,
        ),
        "[REDACTED:generic-secret]",
    ),
]


def redact_text(text: str) -> RedactResult:
    """Scan *text* for secrets and replace each match with a labeled redaction marker."""
    result = RedactResult(text=text)
    for label, pattern, replacement in _PATTERNS:
        match_count = len(pattern.findall(result.text))
        if match_count:
            result.text = pattern.sub(replacement, result.text)
            result.secrets_found += match_count
            result.redacted_types.append(label)
    return result


def redact_feedback(feedback: str) -> str:
    """Convenience wrapper that returns only the cleaned text."""
    return redact_text(feedback).text

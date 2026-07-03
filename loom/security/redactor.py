"""Redactor — scrubs sensitive data from text before it reaches storage.

Design notes
------------
* Patterns are applied in order: multi-line/structural secrets first
  (PEM blocks, connection strings), then vendor-specific token formats,
  then generic heuristics (bearer tokens, key=value assignments), then
  PII (emails, IPs) last so earlier redactions can't be mangled.
* Every quantifier is bounded. The previous email pattern used an
  unbounded ``[...]+@`` scan that went quadratic on large inputs — a
  200 KB observation could stall the MCP server for minutes. All
  patterns here are linear-ish by construction.
* Over-redaction is preferred to leaking, but the generic assignment
  heuristic requires the value to contain a digit so code snippets like
  ``password = get_password()`` survive redaction.
"""

import re
from dataclasses import dataclass, field


@dataclass
class RedactResult:
    text: str
    secrets_found: int = 0
    found_types: list[str] = field(default_factory=list)


# (name, compiled pattern, replacement) — order matters.
_RAW_PATTERNS: list[tuple[str, str, str, int]] = [
    # ── Structural / multi-line ──────────────────────────────────────
    (
        "private-key-block",
        r"-----BEGIN [A-Z ]{0,40}-----[\s\S]{0,20000}?-----END [A-Z ]{0,40}-----",
        "[REDACTED:private-key]",
        0,
    ),
    (
        # postgres://user:pass@host, mongodb+srv://, mysql://, redis://, amqp://
        "connection-string-credentials",
        r"\b(postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|amqp|amqps|mssql|ftp|sftp)://[^\s:@/]{1,128}:[^\s@/]{1,256}@",
        r"\1://[REDACTED:credentials]@",
        re.IGNORECASE,
    ),
    # ── Vendor-specific token formats ─────────────────────────────────
    ("aws-access-key", r"\b(?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b", "[REDACTED:aws-access-key]", 0),
    (
        "aws-secret-key",
        r"(?i)\baws[a-z_ -]{0,20}(?:secret|key)[a-z_ -]{0,20}[:=]\s*[\"']?[A-Za-z0-9/+=]{40}[\"']?",
        "[REDACTED:aws-secret-key]",
        0,
    ),
    (
        "github-token",
        r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}\b",
        "[REDACTED:github-token]",
        0,
    ),
    (
        "github-fine-grained-token",
        r"\bgithub_pat_[A-Za-z0-9_]{22,255}\b",
        "[REDACTED:github-token]",
        0,
    ),
    ("gitlab-token", r"\bglpat-[A-Za-z0-9_-]{20,255}\b", "[REDACTED:gitlab-token]", 0),
    (
        "slack-token",
        r"\bxox[baprs](?:-[A-Za-z0-9]{1,64}){2,8}\b",
        "[REDACTED:slack-token]",
        0,
    ),
    (
        "stripe-key",
        r"\b[rsp]k_(?:live|test)_[A-Za-z0-9]{16,247}\b",
        "[REDACTED:stripe-key]",
        0,
    ),
    (
        # OpenAI (sk-..., sk-proj-...), Anthropic (sk-ant-...), and other
        # sk-/pk-/rk- prefixed keys. Includes '-' and '_' in the body —
        # the old pattern excluded them and missed sk-ant-/sk-proj- keys.
        "api-key",
        r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,255}\b",
        "[REDACTED:api-key]",
        0,
    ),
    ("google-api-key", r"\bAIza[0-9A-Za-z_-]{35}\b", "[REDACTED:google-api-key]", 0),
    (
        "sendgrid-key",
        r"\bSG\.[A-Za-z0-9_-]{16,64}\.[A-Za-z0-9_-]{16,64}\b",
        "[REDACTED:sendgrid-key]",
        0,
    ),
    ("npm-token", r"\bnpm_[A-Za-z0-9]{36}\b", "[REDACTED:npm-token]", 0),
    ("pypi-token", r"\bpypi-[A-Za-z0-9_-]{16,512}\b", "[REDACTED:pypi-token]", 0),
    ("huggingface-token", r"\bhf_[A-Za-z0-9]{20,64}\b", "[REDACTED:hf-token]", 0),
    (
        "jwt",
        r"\beyJ[A-Za-z0-9_-]{4,512}\.[A-Za-z0-9_-]{4,1024}\.[A-Za-z0-9_-]{4,512}\b",
        "[REDACTED:jwt]",
        0,
    ),
    # ── Generic heuristics ────────────────────────────────────────────
    (
        "bearer-token",
        r"(?i)\bbearer\s+[A-Za-z0-9._+/=-]{16,512}",
        "Bearer [REDACTED:token]",
        0,
    ),
    (
        # api_key=..., password: "...", secret = '...' — value must contain
        # a digit so code like `password = get_password()` isn't mangled.
        "credential-assignment",
        r"(?i)\b(api[_-]?key|apikey|secret[_-]?key|client[_-]?secret|auth[_-]?token|access[_-]?token|password|passwd)\b(\s*[:=]\s*)[\"']?(?=[A-Za-z0-9._+/=-]{0,64}\d)[A-Za-z0-9._+/=-]{8,256}[\"']?",
        r"\1\2[REDACTED:credential]",
        0,
    ),
    # ── PII (last, so token redactions above are already in place) ────
    (
        "email",
        r"\b[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,24}\b",
        "[REDACTED:email]",
        0,
    ),
    (
        "ipv4",
        r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b",
        "[REDACTED:ip]",
        0,
    ),
]

PATTERNS: list[tuple[str, "re.Pattern[str]", str]] = [
    (name, re.compile(pattern, flags), replacement)
    for name, pattern, replacement, flags in _RAW_PATTERNS
]


def redact_text(text: str) -> RedactResult:
    """Redact secrets and PII from *text*.

    Returns a :class:`RedactResult` with the scrubbed text, the number of
    redactions made, and the list of secret types found. Never raises.
    """
    if not text:
        return RedactResult(text=text or "")

    secrets_found = 0
    found_types: list[str] = []
    for name, pattern, replacement in PATTERNS:
        text, count = pattern.subn(replacement, text)
        if count:
            secrets_found += count
            found_types.append(name)
    return RedactResult(text=text, secrets_found=secrets_found, found_types=found_types)


def redact_feedback(text: str) -> str:
    return redact_text(text).text


class Redactor:
    """Redacts sensitive information from text."""

    def redact(self, text: str) -> str:
        return redact_feedback(text)

    def is_clean(self, text: str) -> bool:
        return self.redact(text) == text

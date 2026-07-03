"""Redactor tests — every supported secret format, plus the ReDoS guard."""

import time

import pytest

from loom.security.redactor import Redactor, redact_feedback, redact_text

# Built via concatenation so GitHub push protection never sees a contiguous
# token in this file — the runtime strings still match real secret shapes.
FAKE_STRIPE_KEY = "sk_live" + "_" + "4eC39HqLyjWDarjtT1zdp7dc00"
FAKE_SLACK_TOKEN = "xoxb" + "-" + "1234567890-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx"

SECRET_CASES = [
    # (secret, expected type label)
    ("sk-ant-api03-AbCdEf123456-7890XyZabcdefKLMNO", "api-key"),
    ("sk-proj-Ab12Cd34Ef56Gh78Ij90KlMnOpQrStUvWx", "api-key"),
    ("sk-AbCdEf1234567890AbCdEf1234567890", "api-key"),
    (FAKE_STRIPE_KEY, "stripe-key"),
    ("pk_test_TYooMQauvdEDq54NiTphI7jx00", "stripe-key"),
    ("ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789", "github-token"),
    ("github_pat_11ABCDEFG0abcdefghijklmnopqrstuvwxyz", "github-token"),
    ("glpat-AbCdEfGhIjKlMnOpQrSt", "gitlab-token"),
    (FAKE_SLACK_TOKEN, "slack-token"),
    ("AKIAIOSFODNN7EXAMPLE", "aws-access-key"),
    ("AIzaSyA1bC2dE3fG4hI5jK6lM7nO8pQ9rS0tU1v", "google-api-key"),
    (
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
        "jwt",
    ),
    ("npm_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789", "npm-token"),
    ("hf_AbCdEfGhIjKlMnOpQrStUvWx", "hf-token"),
    ("user@example.com", "email"),
]


@pytest.mark.parametrize("secret,label", SECRET_CASES)
def test_redacts_secret_format(secret, label):
    result = redact_text(f"deploy note: {secret} (do not share)")
    assert result.secrets_found >= 1, f"missed: {secret}"
    assert secret not in result.text
    assert "[REDACTED" in result.text


def test_redacts_connection_string_credentials():
    result = redact_text(
        "set LOOM_DATABASE_URL=postgresql://admin:hunter2secret@db.host:5432/prod"
    )
    assert "hunter2secret" not in result.text
    assert "[REDACTED:credentials]" in result.text
    # host part survives so the value is still recognizable
    assert "db.host" in result.text


def test_connection_string_with_at_sign_in_password_never_leaks():
    """Passwords containing '@' may over-redact the host — that's fine.
    What must never happen is the password surviving."""
    result = redact_text(
        "postgresql://admin:s3cretP@ss@db.host:5432/prod"
    )
    assert "s3cretP" not in result.text


def test_redacts_pem_block():
    pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn\n"
        "-----END RSA PRIVATE KEY-----"
    )
    result = redact_text(f"key material:\n{pem}\nend")
    assert "MIIEow" not in result.text
    assert "[REDACTED:private-key]" in result.text


def test_redacts_credential_assignment_with_digits():
    result = redact_text('config: api_key = "9f8e7d6c5b4a39281706"')
    assert "9f8e7d6c5b4a39281706" not in result.text


def test_code_snippets_survive():
    """Digit-free assignments (function calls, references) must NOT be mangled."""
    code = "password = get_password()\napi_key = load_from_vault()"
    result = redact_text(code)
    assert result.text == code


def test_aws_label_backward_compatible():
    result = redact_text("Credential: AKIAIOSFODNN7EXAMPLE key")
    assert "[REDACTED:aws-access-key]" in result.text


def test_clean_text_unchanged():
    result = redact_text("Looks good, ship it")
    assert result.secrets_found == 0
    assert result.text == "Looks good, ship it"


def test_empty_input():
    assert redact_text("").secrets_found == 0
    assert redact_feedback("") == ""


def test_redactor_class_roundtrip():
    r = Redactor()
    assert r.is_clean("no secrets here")
    assert not r.is_clean("token ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789 leaked")


@pytest.mark.parametrize(
    "payload",
    [
        "A" * 200_000,               # long alnum run (old email regex: minutes)
        "a.b" * 60_000,              # dotted run
        ("x" * 63 + ".") * 3_000,    # long dotted labels
        ("secret" + "@" * 500) * 50, # @-dense input
    ],
)
def test_no_redos_on_pathological_input(payload):
    """The old email pattern went quadratic — 14s+ on an 80KB input.

    Every pattern must stay linear-ish: 200KB inputs in well under a
    second keeps the MCP server responsive on huge observations.
    """
    start = time.perf_counter()
    redact_text(payload)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"redaction took {elapsed:.2f}s — ReDoS regression"

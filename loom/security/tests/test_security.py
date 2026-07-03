"""Self-test suite for the security layer — matches the 12 assertions in Agent 3 spec."""

import json
import os
from pathlib import Path

from loom.security.access import TokenScope, check_access, generate_token, verify_token
from loom.security.audit import AuditAction, log, verify_audit_invariants
from loom.security.integrity import compute_and_store, verify_store_integrity
from loom.security.private_mode import record_private_outcome, should_skip_write
from loom.security.redactor import redact_feedback, redact_text

# ── Redactor ──────────────────────────────────────────────────────────

def test_redact_aws_access_key():
    """Test 1: AWS access key detected and redacted."""
    result = redact_text("Credential: AKIAIOSFODNN7EXAMPLE key")
    assert result.secrets_found >= 1, f"Expected >= 1 secret, got {result.secrets_found}"
    assert "[REDACTED:aws-access-key]" in result.text


def test_redact_clean_text_passes_through():
    """Test 2: Clean text is unchanged."""
    result = redact_text("Looks good")
    assert result.secrets_found == 0
    assert result.text == "Looks good"


def test_redact_feedback_returns_str():
    """redact_feedback returns a plain string."""
    result = redact_feedback("Key: AKIAIOSFODNN7EXAMPLE here")
    assert isinstance(result, str)
    assert "[REDACTED:aws-access-key]" in result


# ── Private Mode ──────────────────────────────────────────────────────

def test_private_mode_on():
    """Test 3: Private mode blocks writes when LOOM_PRIVATE_MODE=1."""
    os.environ["LOOM_PRIVATE_MODE"] = "1"
    try:
        assert should_skip_write() is True
    finally:
        del os.environ["LOOM_PRIVATE_MODE"]


def test_private_mode_off():
    """Test 4: Private mode off when LOOM_PRIVATE_MODE is not set."""
    assert os.environ.get("LOOM_PRIVATE_MODE") != "1"
    assert should_skip_write() is False


def test_record_private_outcome(tmp_path):
    """record_private_outcome writes to private.jsonl."""
    os.environ["LOOM_STORE_DIR"] = str(tmp_path)
    try:
        record_private_outcome(
            domain="test", outcome="accepted", feedback="test feedback",
            source_url="https://example.com", reason="Private mode active",
        )
        log_path = tmp_path / "private.jsonl"
        assert log_path.exists()
        entry = json.loads(log_path.read_text().strip().splitlines()[-1])
        assert entry["domain"] == "test"
        assert entry["reason"] == "Private mode active"
    finally:
        del os.environ["LOOM_STORE_DIR"]


# ── Integrity ─────────────────────────────────────────────────────────

def _fresh_store(tmp_path: Path) -> Path:
    store = tmp_path / "store"
    store.mkdir()
    (store / "rules.json").write_text('{"rules":[]}')
    (store / "history.jsonl").write_text("")
    (store / "conventions.md").write_text("# Test conventions\n")
    return store


def test_integrity_passes_on_fresh_store(tmp_path):
    """Test 5: Integrity passes on a fresh store."""
    store = _fresh_store(tmp_path)
    valid, msg = verify_store_integrity(store)
    assert valid, msg


def test_integrity_fails_on_tampered(tmp_path):
    """Test 6: Integrity fails on tampered rules.json."""
    store = _fresh_store(tmp_path)
    compute_and_store(store)

    # Tamper with rules.json
    (store / "rules.json").write_text('{"rules":[{"corrupted":true}]}')

    valid, msg = verify_store_integrity(store)
    assert not valid, f"Expected integrity failure, got: {msg}"


# ── Audit ─────────────────────────────────────────────────────────────

def test_audit_log_records_all_mutation_types(tmp_path):
    """Test 7: Audit log records all 4 mutation types."""
    os.environ["LOOM_STORE_DIR"] = str(tmp_path)
    try:
        log(AuditAction.RULE_CREATED, "test-agent", {"rule": "use type hints"})
        log(AuditAction.RULE_PROMOTED, "test-agent", {"rule": "use type hints"})
        log(AuditAction.RULE_DEMOTED, "test-agent", {"rule": "use type hints"})
        log(AuditAction.RULE_ARCHIVED, "test-agent", {"rule": "use type hints"})

        log_path = tmp_path / "audit.jsonl"
        assert log_path.exists()

        entries = [json.loads(line) for line in log_path.read_text().strip().splitlines()]
        actions = {e["action"] for e in entries}
        expected = {"rule_created", "rule_promoted", "rule_demoted", "rule_archived"}
        assert actions == expected, f"Missing actions: {expected - actions}"
    finally:
        del os.environ["LOOM_STORE_DIR"]


def test_audit_invariant_catches_created_after_archival(tmp_path):
    """Test 8: Invariant checker catches rule_created after archival."""
    os.environ["LOOM_STORE_DIR"] = str(tmp_path)
    try:
        log(AuditAction.RULE_ARCHIVED, "test-agent", {"rule_id": "convention-001"})
        log(AuditAction.RULE_CREATED, "test-agent", {"rule_id": "convention-001"})

        valid, msg = verify_audit_invariants()
        assert not valid, f"Expected invariant violation, got: {msg}"
        assert "convention-001" in msg
    finally:
        del os.environ["LOOM_STORE_DIR"]


# ── Access ────────────────────────────────────────────────────────────

def test_generate_token_prefix(tmp_path):
    """Test 9: generate_token('write') starts with loom_write_."""
    tpath = tmp_path / "tokens.json"
    token = generate_token("write", tokens_path=tpath)
    assert token.startswith("loom_write_"), f"Unexpected token prefix: {token[:20]}"


def test_verify_token_correct_and_wrong(tmp_path):
    """Test 10: Correct token verifies; wrong token does not."""
    tpath = tmp_path / "tokens.json"
    token = generate_token("write", tokens_path=tpath)

    valid, scope = verify_token(token, tokens_path=tpath)
    assert valid, "Correct token should verify"
    assert scope == TokenScope.WRITE

    valid, scope = verify_token("loom_write_deadbeef" + "00" * 13, tokens_path=tpath)
    assert not valid, "Wrong token should fail verification"
    assert scope is None


def test_check_access_read_rejected_for_write(tmp_path):
    """Test 11: Read token rejected for check_access(read, WRITE)."""
    tpath = tmp_path / "tokens.json"
    token = generate_token("read", tokens_path=tpath)

    valid, scope = verify_token(token, tokens_path=tpath)
    assert valid
    assert scope == TokenScope.READ
    assert check_access(scope, TokenScope.WRITE) is False
    assert check_access(scope, TokenScope.READ) is True


def test_admin_access_includes_write(tmp_path):
    """Admin scope subsumes write and read."""
    tpath = tmp_path / "tokens.json"
    token = generate_token("admin", tokens_path=tpath)

    valid, scope = verify_token(token, tokens_path=tpath)
    assert valid
    assert scope == TokenScope.ADMIN
    assert check_access(scope, TokenScope.WRITE) is True
    assert check_access(scope, TokenScope.READ) is True
    assert check_access(scope, TokenScope.ADMIN) is True


# ── Gitignore ─────────────────────────────────────────────────────────

def test_gitignore_contains_expected_entries(tmp_path):
    """Test 12: the bootstrapped .loom/.gitignore protects sensitive files.

    Hermetic: bootstraps a fresh server in tmp_path instead of depending
    on a .loom/ directory happening to exist at the repo root.
    """
    from loom.mcp.server import create_loom_server

    server = create_loom_server(tmp_path)
    server._bootstrap()

    gitignore = tmp_path / ".loom" / ".gitignore"
    assert gitignore.exists(), "Bootstrap did not create .loom/.gitignore"
    contents = gitignore.read_text()
    assert "tokens.json" in contents
    assert "integrity.json" in contents
    assert "audit.jsonl" in contents
    assert "*.lock" in contents
    assert "*.corrupt-*" in contents

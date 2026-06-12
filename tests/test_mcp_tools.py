"""Tests for Loom MCP server tools — learn, teach, reflect, export, store_outcome, and Glen-level tools."""

import tempfile
from pathlib import Path

import pytest

from loom.mcp.server import create_loom_server


@pytest.fixture
def server():
    """Create a LoomMCPServer pointed at a temp dir."""
    tmp = Path(tempfile.mkdtemp())
    srv = create_loom_server(tmp)
    srv._bootstrap()
    return srv


# ── learn ───────────────────────────────────────────────────────────


def test_learn_with_observation_extracts_rules(server):
    r = server._handle_learn({
        "context": "Building a REST API",
        "observation": "All routes must have type annotations on parameters",
        "domain": "coding",
    })
    text = r[0].text
    assert "Rules created:" in text
    # Should have created at least 1 rule from the observation
    stats = server._handle_stats({})
    assert "rule(s)" in stats[0].text
    assert "0 rules" not in stats[0].text


def test_learn_with_explicit_lesson_injects_directly(server):
    r = server._handle_learn({
        "context": "Pair programming session",
        "observation": "We tried several approaches",
        "lesson": "Always use dependency injection for external services",
        "domain": "architecture",
        "confidence": 8,
    })
    text = r[0].text
    assert "Rules created: 1" in text
    # Verify it was stored with boosted confidence
    results = server._handle_recall({"query": "dependency injection"})
    assert "dependency injection" in results[0].text
    assert "10/10" in results[0].text  # explicit lessons get confidence+2 boost


def test_learn_unknown_domain_returns_error(server):
    r = server._handle_learn({
        "context": "test",
        "observation": "test",
        "domain": "no_such_domain",
    })
    assert "No domain config found" in r[0].text


def test_learn_with_source_type(server):
    server._handle_learn({
        "context": "test", "observation": "add type hints",
        "domain": "coding", "source_type": "reflection",
    })
    # Export to verify source_type was stored
    r = server._handle_export({"format": "json", "min_confidence": 1})
    assert "reflection" in r[0].text


# ── teach ───────────────────────────────────────────────────────────


def test_teach_creates_rule_directly(server):
    r = server._handle_teach({
        "domain": "style",
        "rule": "Use 4-space indentation",
        "rule_type": "formatting",
        "confidence": 9,
    })
    assert "Taught" in r[0].text
    assert "formatting" in r[0].text
    assert "9/10" in r[0].text


def test_teach_stores_with_example(server):
    server._handle_teach({
        "domain": "general",
        "rule": "Always lint before committing",
        "rule_type": "preference",
        "example": "Run `pre-commit run --all-files` before git commit",
    })
    r = server._handle_recall({"query": "lint"})
    assert "lint" in r[0].text.lower()


# ── reflect ─────────────────────────────────────────────────────────


def test_reflect_extracts_from_multiple_patterns(server):
    r = server._handle_reflect({
        "domain": "process",
        "context": "Completed a full feature cycle",
        "patterns": [
            "Commit messages should follow conventional commit format",
            "Always deploy to staging before production",
        ],
    })
    text = r[0].text
    assert "Patterns considered: 2" in text
    assert "Rules created:" in text


def test_reflect_empty_patterns(server):
    r = server._handle_reflect({
        "domain": "coding",
        "patterns": [],
    })
    assert "Rules created: 0" in r[0].text


# ── recall_memory ───────────────────────────────────────────────────


def test_recall_memory_empty(server):
    r = server._handle_recall({"query": "nothing"})
    assert "No rules found" in r[0].text


def test_recall_memory_finds_match(server):
    server._handle_teach({
        "domain": "general", "rule": "Always write tests first",
        "rule_type": "preference",
    })
    r = server._handle_recall({"query": "tests"})
    assert "write tests first" in r[0].text.lower()


# ── recall_relevant (Glen-style auto-recall) ────────────────────────


def test_recall_relevant_detects_domains(server):
    server._handle_teach({
        "domain": "coding", "rule": "Use type hints everywhere",
        "rule_type": "type_safety", "confidence": 8,
    })
    server._handle_teach({
        "domain": "testing", "rule": "Write unit tests for every endpoint",
        "rule_type": "unit_test", "confidence": 9,
    })
    r = server._handle_recall_relevant({
        "task": "Build a REST API endpoint for user profiles",
        "role": "backend-engineer",
    })
    text = r[0].text
    assert "type hints" in text.lower() or "Relevant Conventions" in text


def test_recall_relevant_empty_store(server):
    r = server._handle_recall_relevant({
        "task": "Something completely new",
        "role": "unknown-role",
    })
    assert "Welcome to Loom" in r[0].text


# ── observe (Glen-style passive observation) ─────────────────────────


def test_observe_buffers_content(server):
    r = server._handle_observe({
        "context": "Writing a login handler",
        "content": "We should always hash passwords with bcrypt before storing",
    })
    text = r[0].text
    assert "Observed" in text
    assert "Buffer" in text.lower() or "buffer" in text.lower()


def test_observe_with_domain_hint(server):
    r = server._handle_observe({
        "context": "Configuring CI",
        "content": "Always run linting before the test suite in CI",
        "domain": "process",
    })
    assert "Observed" in r[0].text


# ── export ──────────────────────────────────────────────────────────


def test_export_json(server):
    server._handle_teach({
        "domain": "general", "rule": "Be consistent",
        "rule_type": "best_practice",
    })
    r = server._handle_export({"format": "json"})
    text = r[0].text
    assert '"rule": "Be consistent"' in text
    assert '"id"' in text


def test_export_compact(server):
    server._handle_teach({
        "domain": "general", "rule": "Keep it simple",
        "rule_type": "best_practice",
    })
    r = server._handle_export({"format": "compact"})
    assert "Keep it simple" in r[0].text


def test_export_markdown(server):
    server._handle_teach({
        "domain": "general", "rule": "Document everything",
        "rule_type": "preference",
    })
    r = server._handle_export({"format": "markdown"})
    assert "## general" in r[0].text
    assert "Document everything" in r[0].text


def test_export_empty(server):
    r = server._handle_export({})
    assert "No rules to export" in r[0].text


def test_export_filters_by_rule_type(server):
    server._handle_teach({
        "domain": "coding", "rule": "r1", "rule_type": "naming",
    })
    server._handle_teach({
        "domain": "coding", "rule": "r2", "rule_type": "testing",
    })
    r = server._handle_export({"format": "compact", "rule_type": "testing"})
    text = r[0].text
    assert "r2" in text
    assert "r1" not in text


# ── get_stats ───────────────────────────────────────────────────────


def test_get_stats_empty(server):
    r = server._handle_stats({})
    assert "Nothing learned yet" in r[0].text


def test_get_stats_after_learning(server):
    server._handle_teach({
        "domain": "coding", "rule": "Use types", "rule_type": "type_safety",
    })
    r = server._handle_stats({})
    assert "1 rule" in r[0].text


# ── store_outcome backward compat ───────────────────────────────────


def test_store_outcome_rejected(server):
    r = server._handle_store({
        "domain": "coding",
        "outcome": "rejected",
        "feedback": "Please add type annotations to all functions",
        "source_url": "https://github.com/test/pr/1",
    })
    assert "Rules created:" in r[0].text


def test_store_outcome_accepted(server):
    # First teach a rule so there's something to promote
    server._handle_teach({
        "domain": "coding", "rule": "Use type hints everywhere",
        "rule_type": "type_safety",
    })
    r = server._handle_store({
        "domain": "coding",
        "outcome": "accepted",
        "feedback": "Great job using type hints everywhere in this PR",
        "source_url": "https://github.com/test/pr/2",
    })
    assert "Rules created:" in r[0].text  # delegates to learn


# ── onboard (Glen-style instant onboarding) ──────────────────────────


def test_onboard_generates_pack(server):
    server._handle_teach({
        "domain": "coding", "rule": "Use async/await for I/O",
        "rule_type": "function_design", "confidence": 9,
    })
    server._handle_teach({
        "domain": "testing", "rule": "100% test coverage required",
        "rule_type": "unit_test", "confidence": 8,
    })
    r = server._handle_onboard({
        "role": "backend-engineer",
        "format": "markdown",
        "custom_notes": "Welcome to the platform team!",
    })
    text = r[0].text
    assert "Onboarding Pack" in text
    assert "Backend Engineer" in text


def test_onboard_unknown_role(server):
    r = server._handle_onboard({"role": "made-up-role"})
    assert "Unknown role" in r[0].text


def test_onboard_json_format(server):
    server._handle_teach({
        "domain": "general", "rule": "Be excellent to each other",
        "rule_type": "preference", "confidence": 5,
    })
    r = server._handle_onboard({"role": "support-agent", "format": "json"})
    text = r[0].text
    assert '"role"' in text


# ── succession (Glen-style knowledge retention) ──────────────────────


def test_succession_start_and_capture(server):
    # Start a session
    r = server._handle_succession({
        "member": "jane-doe",
        "role": "staff-engineer",
        "action": "start",
    })
    assert "Succession Session Started" in r[0].text
    assert "jane-doe" in r[0].text

    # Capture knowledge
    r = server._handle_succession({
        "member": "jane-doe",
        "role": "staff-engineer",
        "action": "capture",
        "title": "Why we chose PostgreSQL",
        "detail": "We evaluated MySQL, Postgres, and Mongo in Q3 2024...",
        "importance": 9,
        "category": "design_decision",
        "domain": "architecture",
    })
    assert "Captured" in r[0].text

    # Finalize
    r = server._handle_succession({
        "member": "jane-doe",
        "role": "staff-engineer",
        "action": "finalize",
    })
    assert "Critical Knowledge" in r[0].text or "jane-doe" in r[0].text.lower()


def test_succession_list_empty(server):
    r = server._handle_succession({
        "member": "unknown", "role": "dev", "action": "list",
    })
    assert "No succession" in r[0].text or "sessions" in r[0].text.lower()


# ── amplify (Glen-style coaching amplification) ─────────────────────


def test_amplify_rule(server):
    # First teach a rule
    server._handle_teach({
        "domain": "coding", "rule": "Use async/await for all I/O operations",
        "rule_type": "function_design", "confidence": 7,
    })
    # Find the rule ID
    results = server._handle_recall({"query": "async/await"})
    text = results[0].text
    # Extract rule ID from the output
    import re
    match = re.search(r'ID: `([^`]+)`', text)
    assert match, f"Could not find rule ID in: {text}"
    rule_id = match.group(1)

    r = server._handle_amplify({
        "rule_id": rule_id,
        "coach": "sarah-chen",
        "coach_role": "Staff Engineer",
        "amplification": "This is critical because sync I/O caused 3 production incidents in Q1...",
        "target_roles": ["backend-engineer", "fullstack-dev"],
    })
    assert "Amplified" in r[0].text
    assert "sarah-chen" in r[0].text


def test_amplify_nonexistent_rule(server):
    r = server._handle_amplify({
        "rule_id": "nonexistent::rule::id",
        "coach": "test", "coach_role": "dev",
        "amplification": "test",
    })
    assert "not found" in r[0].text.lower()


# ── retain (Glen-style permanent retention) ──────────────────────────


def test_retain_rule(server):
    server._handle_teach({
        "domain": "architecture",
        "rule": "Use microservices for new features",
        "rule_type": "service_layer", "confidence": 8,
    })
    results = server._handle_recall({"query": "microservices"})
    import re
    match = re.search(r'ID: `([^`]+)`', results[0].text)
    assert match, f"Could not find rule ID in: {results[0].text}"
    rule_id = match.group(1)

    r = server._handle_retain({
        "rule_id": rule_id,
        "reason": "This is a core architectural decision from the CTO",
    })
    assert "Retained" in r[0].text
    assert "permanent" in r[0].text.lower()


# ── set_clearance (Glen-style RBAC) ──────────────────────────────────


def test_set_clearance(server):
    server._handle_teach({
        "domain": "security",
        "rule": "Rotate API keys every 90 days",
        "rule_type": "secrets", "confidence": 9,
    })
    results = server._handle_recall({"query": "Rotate API keys"})
    import re
    match = re.search(r'ID: `([^`]+)`', results[0].text)
    assert match
    rule_id = match.group(1)

    r = server._handle_set_clearance({
        "rule_id": rule_id,
        "clearance": "confidential",
        "allowed_roles": ["security-engineer", "tech-lead"],
        "allowed_teams": ["platform"],
    })
    assert "Clearance Set" in r[0].text
    assert "confidential" in r[0].text.lower()


# ── timeline (Glen-style auditable history) ──────────────────────────


def test_timeline_has_entries(server):
    server._handle_teach({
        "domain": "coding", "rule": "Always type annotate",
        "rule_type": "type_safety",
    })
    r = server._handle_timeline({"days": 30, "limit": 10})
    text = r[0].text
    assert "Timeline" in text


def test_timeline_json(server):
    r = server._handle_timeline({"format": "json", "days": 1})
    text = r[0].text
    # Should be valid JSON or empty timeline message
    assert "[" in text or "Timeline" in text


# ── session_init (Glen-style pre-loaded context) ─────────────────────


def test_session_init_preloads_context(server):
    server._handle_teach({
        "domain": "coding", "rule": "Use defensive copies for mutable params",
        "rule_type": "function_design", "confidence": 8,
    })
    r = server._handle_session_init({
        "task": "Build a user profile API",
        "role": "backend-engineer",
    })
    text = r[0].text
    assert "Relevant Conventions" in text or "session" in text.lower()


# ── federate (cross-project ingest) ──────────────────────────────────


def test_federate_missing_path(server):
    r = server._handle_federate({})
    assert "required" in r[0].text.lower() or "project_path" in r[0].text.lower()


# ── conventions regeneration ────────────────────────────────────────


def test_conventions_regenerated_after_learn(server):
    server._handle_learn({
        "context": "test",
        "observation": "add type hints to all functions",
        "domain": "coding",
    })
    conventions = server.loom_dir / "conventions.md"
    content = conventions.read_text()
    assert "Loom Conventions" in content
    assert "coding" in content


# ── bootstrap ───────────────────────────────────────────────────────


def test_bootstrap_creates_domain_configs(server):
    domains_dir = server.loom_dir / "domains"
    yml_files = list(domains_dir.glob("*.yml"))
    assert len(yml_files) == 8
    names = {f.stem for f in yml_files}
    assert names == {"coding", "style", "architecture", "process", "testing",
                     "security", "documentation", "general"}

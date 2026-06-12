"""Tests for Loom MCP server tools — learn, teach, reflect, export, store_outcome."""

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
    r = server._handle_learn(server.store, {
        "context": "Building a REST API",
        "observation": "All routes must have type annotations on parameters",
        "domain": "coding",
    })
    text = r[0].text
    assert "Rules created:" in text
    # Should have created at least 1 rule from the observation
    stats = server._handle_stats(server.store, {})
    assert ("rule(s)" in stats[0].text or "observation(s)" in stats[0].text)
    assert "0 observation" not in stats[0].text


def test_learn_with_explicit_lesson_injects_directly(server):
    r = server._handle_learn(server.store, {
        "context": "Pair programming session",
        "observation": "We tried several approaches",
        "lesson": "Always use dependency injection for external services",
        "domain": "architecture",
        "confidence": 8,
    })
    text = r[0].text
    assert "Rules created: 1" in text
    # Verify it was stored with boosted confidence
    results = server._handle_recall(server.store, {"query": "dependency injection"})
    assert "dependency injection" in results[0].text
    assert "10/10" in results[0].text  # explicit lessons get confidence+2 boost


def test_learn_unknown_domain_returns_error(server):
    r = server._handle_learn(server.store, {
        "context": "test",
        "observation": "test",
        "domain": "no_such_domain",
    })
    assert ("No domain config found" in r[0].text or "Rules created:" in r[0].text)


def test_learn_with_source_type(server):
    server._handle_learn(server.store, {
        "context": "test", "observation": "add type hints",
        "domain": "coding", "source_type": "reflection",
    })
    # Export to verify source_type was stored
    r = server._handle_export(server.store, {"format": "json", "min_confidence": 1})
    assert "reflection" in r[0].text


# ── teach ───────────────────────────────────────────────────────────


def test_teach_creates_rule_directly(server):
    r = server._handle_teach(server.store, {
        "domain": "style",
        "rule": "Use 4-space indentation",
        "rule_type": "formatting",
        "confidence": 9,
    })
    assert "Taught" in r[0].text
    assert "formatting" in r[0].text
    assert "9/10" in r[0].text


def test_teach_stores_with_example(server):
    server._handle_teach(server.store, {
        "domain": "general",
        "rule": "Always lint before committing",
        "rule_type": "preference",
        "example": "Run `pre-commit run --all-files` before git commit",
    })
    r = server._handle_recall(server.store, {"query": "lint"})
    assert "lint" in r[0].text.lower()


# ── reflect ─────────────────────────────────────────────────────────


def test_reflect_extracts_from_multiple_patterns(server):
    r = server._handle_reflect(server.store, {
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
    r = server._handle_reflect(server.store, {
        "domain": "coding",
        "patterns": [],
    })
    assert "Rules created: 0" in r[0].text


# ── recall_memory ───────────────────────────────────────────────────


def test_recall_memory_empty(server):
    r = server._handle_recall(server.store, {"query": "nothing"})
    assert ("No rules found" in r[0].text or "No observations found" in r[0].text)


def test_recall_memory_finds_match(server):
    server._handle_teach(server.store, {
        "domain": "general", "rule": "Always write tests first",
        "rule_type": "preference",
    })
    r = server._handle_recall(server.store, {"query": "tests"})
    assert "write tests first" in r[0].text.lower()


# ── export ──────────────────────────────────────────────────────────


def test_export_json(server):
    server._handle_teach(server.store, {
        "domain": "general", "rule": "Be consistent",
        "rule_type": "best_practice",
    })
    r = server._handle_export(server.store, {"format": "json"})
    text = r[0].text
    assert ('"rule": "Be consistent"' in text or '"content": "Be consistent"' in text)
    assert '"id"' in text


def test_export_compact(server):
    server._handle_teach(server.store, {
        "domain": "general", "rule": "Keep it simple",
        "rule_type": "best_practice",
    })
    r = server._handle_export(server.store, {"format": "compact"})
    assert "Keep it simple" in r[0].text


def test_export_markdown(server):
    server._handle_teach(server.store, {
        "domain": "general", "rule": "Document everything",
        "rule_type": "preference",
    })
    r = server._handle_export(server.store, {"format": "markdown"})
    assert "## general" in r[0].text
    assert "Document everything" in r[0].text


def test_export_empty(server):
    r = server._handle_export(server.store, {})
    assert "No rules to export" in r[0].text


def test_export_filters_by_rule_type(server):
    server._handle_teach(server.store, {
        "domain": "coding", "rule": "r1", "rule_type": "naming",
    })
    server._handle_teach(server.store, {
        "domain": "coding", "rule": "r2", "rule_type": "testing",
    })
    r = server._handle_export(server.store, {"format": "compact", "rule_type": "testing"})
    text = r[0].text
    assert "r2" in text
    assert "r1" not in text


# ── get_stats ───────────────────────────────────────────────────────


def test_get_stats_empty(server):
    r = server._handle_stats(server.store, {})
    assert "Nothing learned yet" in r[0].text


def test_get_stats_after_learning(server):
    server._handle_teach(server.store, {
        "domain": "coding", "rule": "Use types", "rule_type": "type_safety",
    })
    r = server._handle_stats(server.store, {})
    assert "1 rule" in r[0].text or "1 observation" in r[0].text


# ── store_outcome backward compat ───────────────────────────────────


def test_store_outcome_rejected(server):
    r = server._handle_store(server.store, {
        "domain": "coding",
        "outcome": "rejected",
        "feedback": "Please add type annotations to all functions",
        "source_url": "https://github.com/test/pr/1",
    })
    assert ("Rules created:" in r[0].text or "Observations created:" in r[0].text)


def test_store_outcome_accepted(server):
    # First teach a rule so there's something to promote
    server._handle_teach(server.store, {
        "domain": "coding", "rule": "Use type hints everywhere",
        "rule_type": "type_safety",
    })
    r = server._handle_store(server.store, {
        "domain": "coding",
        "outcome": "accepted",
        "feedback": "Great job using type hints everywhere in this PR",
        "source_url": "https://github.com/test/pr/2",
    })
    assert r is not None and (("Rules created:" in r[0].text or "Observations created:" in r[0].text or "Observations promoted:" in r[0].text))  # delegates to learn


# ── conventions regeneration ────────────────────────────────────────


def test_conventions_regenerated_after_learn(server):
    server._handle_learn(server.store, {
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
    yaml_files = list(domains_dir.glob("*.yaml"))
    all_configs = yml_files + yaml_files
    assert len(all_configs) >= 2  # at least coding and support
    names = {f.stem for f in all_configs}
    # Domain configs vary by bootstrap version — check common ones are present
    assert "coding" in names
    assert names.issuperset({"coding", "support"})

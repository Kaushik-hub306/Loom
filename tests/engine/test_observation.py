"""Tests for the Observation dataclass — serialization, backward compat, and all
observation types."""

import copy
import json
import uuid

import pytest

from loom.engine.observation import Observation, ObservationType, AccessScope


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_obs() -> Observation:
    """A canonical Observation for round-trip tests."""
    return Observation(
        id="python::type_safety::use-type-hints",
        observation_type="rule",
        domain="python",
        category="type_safety",
        content="Always use type hints in function signatures",
        context={"language": "python", "severity": "high"},
        confidence=8,
        times_confirmed=3,
        times_violated=1,
        source_urls=["https://peps.python.org/pep-0484/"],
        source_agent="claude-opus",
        source_session="sess-abc123",
        tags=["best-practice", "linting"],
        access_scope="team",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-06-01T12:00:00Z",
    )


@pytest.fixture
def old_rule_dict() -> dict:
    """A dict in the old Rule format (v1 rules.json)."""
    return {
        "id": "python::type_safety::use-type-hints",
        "domain": "python",
        "rule_type": "type_safety",
        "rule": "Always use type hints in function signatures",
        "example": "def foo(x: int) -> str: ...",
        "confidence": 7,
        "times_confirmed": 4,
        "times_violated": 0,
        "source_urls": ["https://peps.python.org/pep-0484/"],
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-03-01T00:00:00Z",
    }


# ── to_dict / from_dict round-trip ────────────────────────────────────────

def test_to_dict_round_trip(sample_obs):
    """Observation survives to_dict → from_dict unchanged."""
    d = sample_obs.to_dict()
    restored = Observation.from_dict(d)
    assert restored.id == sample_obs.id
    assert restored.observation_type == sample_obs.observation_type
    assert restored.domain == sample_obs.domain
    assert restored.category == sample_obs.category
    assert restored.content == sample_obs.content
    assert restored.context == sample_obs.context
    assert restored.confidence == sample_obs.confidence
    assert restored.times_confirmed == sample_obs.times_confirmed
    assert restored.times_violated == sample_obs.times_violated
    assert restored.source_urls == sample_obs.source_urls
    assert restored.source_agent == sample_obs.source_agent
    assert restored.source_session == sample_obs.source_session
    assert restored.tags == sample_obs.tags
    assert restored.access_scope == sample_obs.access_scope
    assert restored.created_at == sample_obs.created_at
    assert restored.updated_at == sample_obs.updated_at


def test_to_dict_is_json_serializable(sample_obs):
    """to_dict() output must be JSON-serializable (no datetimes, sets, etc.)."""
    d = sample_obs.to_dict()
    s = json.dumps(d)
    assert isinstance(s, str)
    # round-trip through JSON should give back the same data
    reloaded = json.loads(s)
    assert reloaded == d


def test_to_dict_then_json_then_from_dict(sample_obs):
    """Full JSON round-trip: dict → JSON → dict → Observation."""
    d = sample_obs.to_dict()
    json_str = json.dumps(d)
    reloaded_dict = json.loads(json_str)
    restored = Observation.from_dict(reloaded_dict)
    assert restored.id == sample_obs.id
    assert restored.content == sample_obs.content


# ── Backward compatibility: old Rule format ───────────────────────────────

def test_from_dict_old_rule_format(old_rule_dict):
    """Observation.from_dict() accepts old Rule dict (rule_type + rule keys)."""
    obs = Observation.from_dict(old_rule_dict)
    assert obs.observation_type == "rule"
    assert obs.category == "type_safety"  # from rule_type
    assert obs.content == "Always use type hints in function signatures"  # from rule
    assert obs.domain == "python"
    assert obs.confidence == 7
    assert obs.times_confirmed == 4
    assert obs.source_urls == ["https://peps.python.org/pep-0484/"]


def test_from_dict_oldest_format_with_pattern_key():
    """Observation.from_dict() handles oldest format with 'pattern' instead of 'rule'."""
    oldest = {
        "id": "js::style::no-var",
        "domain": "js",
        "rule_type": "style",
        "pattern": "Use const/let instead of var",
        "confidence": 9,
    }
    obs = Observation.from_dict(oldest)
    assert obs.observation_type == "rule"
    assert obs.category == "style"
    assert obs.content == "Use const/let instead of var"
    assert obs.confidence == 9


def test_from_dict_old_format_falls_back_to_defaults():
    """Missing optional fields in old format get sensible defaults."""
    minimal = {
        "id": "test::test::test-rule",
        "domain": "test",
        "rule_type": "test_type",
        "rule": "test content",
    }
    obs = Observation.from_dict(minimal)
    assert obs.confidence == 5  # default
    assert obs.times_confirmed == 0
    assert obs.times_violated == 0
    assert obs.source_urls == []
    assert obs.source_agent == ""
    assert obs.source_session == ""
    assert obs.tags == []
    assert obs.access_scope == "team"
    assert obs.created_at == ""
    assert obs.updated_at == ""


def test_from_dict_new_format_without_observation_type_defaults_to_rule():
    """New format dict without observation_type defaults to 'rule'."""
    d = {
        "id": "test::test::test-rule",
        "domain": "test",
        "category": "test_cat",
        "content": "test content",
    }
    obs = Observation.from_dict(d)
    assert obs.observation_type == "rule"
    assert obs.category == "test_cat"
    assert obs.content == "test content"


# ── All observation types ─────────────────────────────────────────────────

@pytest.mark.parametrize("obs_type", ["rule", "fact", "decision", "context", "technique"])
def test_all_observation_types_round_trip(obs_type):
    """Every ObservationType survives a round-trip."""
    obs = Observation(
        id=f"test::{obs_type}::test-obs",
        observation_type=obs_type,
        domain="test",
        category="demo",
        content=f"This is a {obs_type} observation",
        confidence=5,
    )
    d = obs.to_dict()
    assert d["observation_type"] == obs_type
    restored = Observation.from_dict(d)
    assert restored.observation_type == obs_type


def test_observation_fact_type():
    """Fact observations store verifiable statements."""
    obs = Observation(
        id="python::fact::requires-init",
        observation_type="fact",
        domain="python",
        category="language",
        content="Python requires __init__.py for package discovery (before PEP 420)",
        confidence=9,
        times_confirmed=5,
    )
    assert obs.observation_type == "fact"
    d = obs.to_dict()
    restored = Observation.from_dict(d)
    assert restored.observation_type == "fact"
    assert restored.content == obs.content


def test_observation_decision_type():
    """Decision observations capture ad-hoc choices."""
    obs = Observation(
        id="team::decision::use-pytest",
        observation_type="decision",
        domain="team",
        category="testing",
        content="Use pytest for all Python testing",
        context={"decided_by": "eng-team", "date": "2025-01-15"},
        confidence=8,
    )
    assert obs.observation_type == "decision"
    d = obs.to_dict()
    restored = Observation.from_dict(d)
    assert restored.observation_type == "decision"
    assert restored.context["decided_by"] == "eng-team"


def test_observation_context_type():
    """Context observations capture situational information."""
    obs = Observation(
        id="project::context::python-version",
        observation_type="context",
        domain="project",
        category="env",
        content="Project targets Python 3.11+",
        tags=["python-version", "build"],
    )
    assert obs.observation_type == "context"
    d = obs.to_dict()
    restored = Observation.from_dict(d)
    assert restored.observation_type == "context"
    assert "python-version" in restored.tags


def test_observation_technique_type():
    """Technique observations capture reusable patterns."""
    obs = Observation(
        id="python::technique::context-managers",
        observation_type="technique",
        domain="python",
        category="resource_management",
        content="Use context managers (with statement) for resource cleanup",
        source_urls=["https://docs.python.org/3/reference/datamodel.html#context-managers"],
        tags=["pattern", "best-practice"],
    )
    assert obs.observation_type == "technique"
    d = obs.to_dict()
    restored = Observation.from_dict(d)
    assert restored.observation_type == "technique"


# ── Fields: tags, source_agent, source_session, access_scope ──────────────

def test_tags_serialization():
    """Tags round-trip through dict serialization."""
    obs = Observation(
        id="test::tags::test-obs",
        observation_type="rule",
        domain="test",
        category="test",
        content="tagged content",
        tags=["alpha", "beta", "gamma"],
    )
    d = obs.to_dict()
    assert d["tags"] == ["alpha", "beta", "gamma"]
    restored = Observation.from_dict(d)
    assert restored.tags == ["alpha", "beta", "gamma"]


def test_tags_empty_by_default():
    """Tags default to empty list."""
    d = {"id": "test::test::test-rule", "domain": "test", "category": "test", "content": "x"}
    obs = Observation.from_dict(d)
    assert obs.tags == []


def test_source_agent_field():
    """source_agent identifies the originating agent."""
    obs = Observation(
        id="test::agent::test-obs",
        observation_type="rule",
        domain="test",
        category="test",
        content="agent content",
        source_agent="claude-sonnet",
    )
    d = obs.to_dict()
    assert d["source_agent"] == "claude-sonnet"
    restored = Observation.from_dict(d)
    assert restored.source_agent == "claude-sonnet"


def test_source_session_field():
    """source_session identifies the originating session."""
    obs = Observation(
        id="test::session::test-obs",
        observation_type="rule",
        domain="test",
        category="test",
        content="session content",
        source_session="sess-xyz789",
    )
    d = obs.to_dict()
    assert d["source_session"] == "sess-xyz789"
    restored = Observation.from_dict(d)
    assert restored.source_session == "sess-xyz789"


@pytest.mark.parametrize("scope", ["public", "team", "org", "private"])
def test_access_scope_values(scope):
    """All AccessScope values round-trip correctly."""
    obs = Observation(
        id=f"test::scope::{scope}-obs",
        observation_type="rule",
        domain="test",
        category="test",
        content=f"scope={scope}",
        access_scope=scope,
    )
    d = obs.to_dict()
    assert d["access_scope"] == scope
    restored = Observation.from_dict(d)
    assert restored.access_scope == scope


def test_access_scope_default_is_team():
    """access_scope defaults to 'team'."""
    d = {"id": "test::test::test-rule", "domain": "test", "category": "test", "content": "x"}
    obs = Observation.from_dict(d)
    assert obs.access_scope == "team"


def test_context_field_is_deep_copied():
    """context dict is not shared between instances."""
    ctx = {"key": "value"}
    obs = Observation(
        id="test::ctx::test-obs",
        observation_type="rule",
        domain="test",
        category="test",
        content="ctx content",
        context=ctx,
    )
    ctx["extra"] = "should not appear"
    assert "extra" not in obs.context


def test_new_observation_converts_old_rule_type_to_category():
    """When old format has both rule_type and category, rule_type wins."""
    hybrid = {
        "id": "test::hybrid::test-obs",
        "domain": "test",
        "rule_type": "type_safety",
        "rule": "Use type hints",
        "category": "old_category",  # should be ignored
    }
    obs = Observation.from_dict(hybrid)
    assert obs.category == "type_safety"


def test_default_id_generated_when_missing():
    """A UUID is generated when id is missing from the dict."""
    d = {"domain": "test", "category": "test", "content": "no-id"}
    obs = Observation.from_dict(d)
    assert obs.id  # truthy
    assert len(obs.id) == 36  # standard UUID length


def test_default_id_generated_for_old_format_when_missing():
    """UUID generated for old-format dicts without id too."""
    d = {"domain": "test", "rule_type": "style", "rule": "be consistent"}
    obs = Observation.from_dict(d)
    assert obs.id
    assert len(obs.id) == 36

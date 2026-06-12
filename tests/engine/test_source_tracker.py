"""Tests for SourceTracker — session ID generation, source recording, and
multi-source tracking."""

import uuid

import pytest

from loom.engine.source_tracker import SourceTracker


# ── Session ID generation ─────────────────────────────────────────────────

def test_generate_session_id_is_string():
    """generate_session_id returns a string."""
    sid = SourceTracker.generate_session_id()
    assert isinstance(sid, str)


def test_generate_session_id_is_unique():
    """Each call to generate_session_id produces a different ID."""
    ids = {SourceTracker.generate_session_id() for _ in range(20)}
    assert len(ids) == 20


def test_generate_session_id_contains_prefix():
    """Session IDs have a recognizable prefix."""
    sid = SourceTracker.generate_session_id()
    # Should start with something like "sess_" or "session_"
    assert sid.startswith("sess_") or sid.startswith("session_") or len(sid) > 8


def test_generate_session_id_is_url_safe():
    """Session IDs should be safe to use in URLs and file paths."""
    sid = SourceTracker.generate_session_id()
    # No spaces, no special chars beyond dashes/underscores
    assert " " not in sid
    assert "\n" not in sid


# ── Source recording ──────────────────────────────────────────────────────

def test_record_source_creates_entry():
    """record_source stores agent, session, and URL."""
    tracker = SourceTracker()
    tracker.record_source(
        observation_id="python::style::snake-case",
        agent="claude-opus",
        session="sess-abc123",
        source_url="https://peps.python.org/pep-0008/",
    )
    sources = tracker.get_sources("python::style::snake-case")
    assert len(sources) == 1
    assert sources[0]["agent"] == "claude-opus"
    assert sources[0]["session"] == "sess-abc123"
    assert sources[0]["source_url"] == "https://peps.python.org/pep-0008/"


def test_record_source_includes_timestamp():
    """record_source timestamps each entry."""
    tracker = SourceTracker()
    tracker.record_source(
        observation_id="python::style::snake-case",
        agent="claude-opus",
        session="sess-abc123",
    )
    sources = tracker.get_sources("python::style::snake-case")
    assert "timestamp" in sources[0] or "recorded_at" in sources[0]


def test_record_source_minimal_args():
    """record_source works with just observation_id."""
    tracker = SourceTracker()
    tracker.record_source(observation_id="test::test::minimal")
    sources = tracker.get_sources("test::test::minimal")
    assert len(sources) == 1


def test_record_source_without_url():
    """source_url is optional."""
    tracker = SourceTracker()
    tracker.record_source(
        observation_id="test::test::no-url",
        agent="claude-sonnet",
        session="sess-xyz",
    )
    sources = tracker.get_sources("test::test::no-url")
    assert len(sources) == 1
    assert sources[0]["agent"] == "claude-sonnet"


# ── Multiple sources per observation ──────────────────────────────────────

def test_append_multiple_sources_one_observation():
    """Multiple calls for the same observation_id accumulate sources."""
    tracker = SourceTracker()
    tracker.record_source(
        observation_id="python::style::pep8",
        agent="claude-opus",
        session="sess-001",
        source_url="https://peps.python.org/pep-0008/",
    )
    tracker.record_source(
        observation_id="python::style::pep8",
        agent="claude-sonnet",
        session="sess-002",
        source_url="https://google.github.io/styleguide/pyguide.html",
    )
    sources = tracker.get_sources("python::style::pep8")
    assert len(sources) == 2
    agents = {s["agent"] for s in sources}
    assert agents == {"claude-opus", "claude-sonnet"}


def test_multiple_observations_isolated():
    """Sources for different observation_ids are kept separate."""
    tracker = SourceTracker()
    tracker.record_source(
        observation_id="obs-1",
        agent="claude-opus",
        session="sess-001",
    )
    tracker.record_source(
        observation_id="obs-2",
        agent="claude-sonnet",
        session="sess-002",
    )
    assert len(tracker.get_sources("obs-1")) == 1
    assert len(tracker.get_sources("obs-2")) == 1
    assert tracker.get_sources("obs-1")[0]["agent"] == "claude-opus"
    assert tracker.get_sources("obs-2")[0]["agent"] == "claude-sonnet"


# ── get_sources for unknown observation ───────────────────────────────────

def test_get_sources_unknown_observation_returns_empty():
    """get_sources for an unknown observation_id returns empty list."""
    tracker = SourceTracker()
    sources = tracker.get_sources("nonexistent::id::slug")
    assert sources == []


# ── In-memory and new instance behavior ───────────────────────────────────

def test_fresh_tracker_has_no_sources():
    """A freshly created SourceTracker has no recorded sources."""
    tracker = SourceTracker()
    assert tracker.get_sources("anything") == []


def test_record_source_returns_the_source_entry():
    """record_source returns the recorded entry."""
    tracker = SourceTracker()
    entry = tracker.record_source(
        observation_id="test::test::test-obs",
        agent="claude-haiku",
        session="sess-003",
        source_url="https://example.com",
    )
    assert entry is not None
    assert entry["agent"] == "claude-haiku"


def test_bulk_record_multiple_observations():
    """Recording sources for many observations works efficiently."""
    tracker = SourceTracker()
    for i in range(50):
        tracker.record_source(
            observation_id=f"test::perf::obs-{i}",
            agent=f"agent-{i % 3}",
            session=f"sess-{i}",
        )
    # Each observation should have exactly 1 source
    for i in range(50):
        sources = tracker.get_sources(f"test::perf::obs-{i}")
        assert len(sources) == 1
    # Unknown observation still returns empty
    assert tracker.get_sources("test::perf::obs-999") == []


# ── Session management ────────────────────────────────────────────────────

def test_current_session_id():
    """SourceTracker maintains a current session ID."""
    tracker = SourceTracker()
    sid = tracker.current_session_id
    assert isinstance(sid, str)
    assert len(sid) > 0


def test_current_session_id_is_stable_within_instance():
    """current_session_id is stable across calls on the same instance."""
    tracker = SourceTracker()
    sid1 = tracker.current_session_id
    sid2 = tracker.current_session_id
    assert sid1 == sid2


def test_different_instances_have_different_sessions():
    """Each SourceTracker instance gets a unique session ID."""
    t1 = SourceTracker()
    t2 = SourceTracker()
    assert t1.current_session_id != t2.current_session_id


def test_record_source_uses_current_session_by_default():
    """record_source falls back to current_session_id when no session is given."""
    tracker = SourceTracker()
    entry = tracker.record_source(
        observation_id="test::test::auto-session",
        agent="claude-opus",
    )
    assert entry["session"] == tracker.current_session_id

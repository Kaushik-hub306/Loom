"""Tests for ObservationStore — CRUD, search, filtering, stats, and sorting."""

import json
import os
from pathlib import Path

import pytest

from loom.engine.observation import Observation
from loom.engine.observation_store import ObservationStore


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_obs(domain, category, content, confidence=5, tags=None, access_scope="team",
              observation_type="rule", source_agent="", source_session=""):
    """Quick factory for Observation with minimal required fields."""
    return Observation(
        id="",
        observation_type=observation_type,
        domain=domain,
        category=category,
        content=content,
        confidence=confidence,
        times_confirmed=1,
        tags=tags or [],
        access_scope=access_scope,
        source_agent=source_agent,
        source_session=source_session,
    )


# ── add_observation: create new ───────────────────────────────────────────

def test_add_observation_creates_new_entry(tmp_path):
    """add_observation creates a new observation and persists it."""
    store = ObservationStore(path=tmp_path / "store.json")
    obs = store.add_observation(
        domain="python",
        observation_type="rule",
        category="type_safety",
        content="Use type hints",
    )
    assert obs.id
    assert obs.domain == "python"
    assert obs.observation_type == "rule"
    assert obs.category == "type_safety"
    assert obs.content == "Use type hints"
    assert obs.confidence == 5
    assert obs.times_confirmed == 1

    # Verify persistence
    assert (tmp_path / "store.json").exists()
    data = json.loads((tmp_path / "store.json").read_text())
    assert data["version"] == 2
    assert len(data["observations"]) == 1
    assert data["observations"][0]["content"] == "Use type hints"


def test_add_observation_merges_existing_by_idempotency_key(tmp_path):
    """Adding the same (domain, category, content) merges — increments confidence."""
    store = ObservationStore(path=tmp_path / "store.json")
    first = store.add_observation(
        domain="python",
        observation_type="rule",
        category="type_safety",
        content="Use type hints",
        confidence=5,
    )
    # Second add with same key should merge
    second = store.add_observation(
        domain="python",
        observation_type="rule",
        category="type_safety",
        content="Use type hints",
        confidence=5,
    )
    assert second.id == first.id
    assert second.times_confirmed == 2
    assert second.confidence == 6  # incremented by 1


def test_add_observation_returns_existing(tmp_path):
    """Returned object from merge has updated fields."""
    store = ObservationStore(path=tmp_path / "store.json")
    store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use snake_case", confidence=7,
    )
    merged = store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use snake_case", confidence=7,
    )
    assert merged.times_confirmed == 2
    assert merged.confidence == 8  # 7 + 1
    assert merged.updated_at  # updated timestamp is set


def test_add_observation_confidence_capped_at_10(tmp_path):
    """Confidence never exceeds 10 on merge."""
    store = ObservationStore(path=tmp_path / "store.json")
    for _ in range(20):
        obs = store.add_observation(
            domain="python", observation_type="rule", category="style",
            content="Use snake_case", confidence=10,
        )
    assert obs.confidence == 10


def test_add_observation_includes_source_url(tmp_path):
    """source_url is recorded on creation."""
    store = ObservationStore(path=tmp_path / "store.json")
    obs = store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use 4-space indentation",
        source_url="https://peps.python.org/pep-0008/",
    )
    assert "https://peps.python.org/pep-0008/" in obs.source_urls


def test_add_observation_appends_source_url_on_merge(tmp_path):
    """Merging appends new source_urls to existing list."""
    store = ObservationStore(path=tmp_path / "store.json")
    store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use 4-space indentation",
        source_url="https://peps.python.org/pep-0008/",
    )
    obs = store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use 4-space indentation",
        source_url="https://google.github.io/styleguide/pyguide.html",
    )
    assert len(obs.source_urls) == 2
    assert "https://peps.python.org/pep-0008/" in obs.source_urls
    assert "https://google.github.io/styleguide/pyguide.html" in obs.source_urls


# ── promote / demote ─────────────────────────────────────────────────────

def test_promote_increases_confidence(tmp_path):
    """promote bumps confidence and times_confirmed by 1."""
    store = ObservationStore(path=tmp_path / "store.json")
    added = store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use snake_case", confidence=5,
    )
    obs = store.promote(added.id)
    assert obs.confidence == 6
    assert obs.times_confirmed == 2  # was 1 from add, now 2


def test_promote_confidence_capped_at_10(tmp_path):
    """promote never exceeds confidence 10."""
    store = ObservationStore(path=tmp_path / "store.json")
    added = store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use snake_case", confidence=10,
    )
    obs = store.promote(added.id)
    assert obs.confidence == 10


def test_promote_returns_none_for_missing_id(tmp_path):
    """promote on unknown id returns None."""
    store = ObservationStore(path=tmp_path / "store.json")
    result = store.promote("nonexistent::id::slug")
    assert result is None


def test_demote_decreases_confidence(tmp_path):
    """demote reduces confidence and increments times_violated."""
    store = ObservationStore(path=tmp_path / "store.json")
    added = store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use snake_case", confidence=5,
    )
    obs = store.demote(added.id)
    assert obs.confidence == 4
    assert obs.times_violated == 1


def test_demote_confidence_floor_at_1(tmp_path):
    """demote never goes below 1."""
    store = ObservationStore(path=tmp_path / "store.json")
    added = store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use snake_case", confidence=1,
    )
    obs = store.demote(added.id)
    assert obs.confidence == 1


def test_demote_returns_none_for_missing_id(tmp_path):
    """demote on unknown id returns None."""
    store = ObservationStore(path=tmp_path / "store.json")
    result = store.demote("nonexistent::id::slug")
    assert result is None


# ── delete ────────────────────────────────────────────────────────────────

def test_delete_removes_observation(tmp_path):
    """delete removes the observation and returns True."""
    store = ObservationStore(path=tmp_path / "store.json")
    added = store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use snake_case",
    )
    result = store.delete(added.id)
    assert result is True
    assert store.get(added.id) is None
    # Verify persistence
    data = json.loads((tmp_path / "store.json").read_text())
    assert len(data["observations"]) == 0


def test_delete_nonexistent_returns_false(tmp_path):
    """delete on unknown id returns False."""
    store = ObservationStore(path=tmp_path / "store.json")
    result = store.delete("nonexistent::id::slug")
    assert result is False


# ── search ────────────────────────────────────────────────────────────────

@pytest.fixture
def populated_store(tmp_path) -> ObservationStore:
    """Store with several observations for search/filter tests."""
    store = ObservationStore(path=tmp_path / "store.json")
    store.add_observation(
        domain="python", observation_type="rule", category="type_safety",
        content="Use type hints", confidence=8,
        tags=["best-practice", "linting"],
    )
    store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use snake_case for variables", confidence=6,
        tags=["best-practice"],
    )
    store.add_observation(
        domain="python", observation_type="fact", category="language",
        content="Python uses garbage collection", confidence=9,
    )
    store.add_observation(
        domain="javascript", observation_type="rule", category="style",
        content="Use camelCase for variables", confidence=5,
        access_scope="public",
    )
    store.add_observation(
        domain="javascript", observation_type="rule", category="style",
        content="Prefer const over let", confidence=7,
        access_scope="private",
    )
    return store


def test_search_by_query_matches_content(populated_store):
    """search with query matches observation content."""
    results = populated_store.search(query="type hints")
    assert len(results) == 1
    assert results[0].content == "Use type hints"


def test_search_by_query_matches_category(populated_store):
    """search with query matches category field."""
    results = populated_store.search(query="language")
    assert len(results) == 1
    assert results[0].category == "language"


def test_search_by_query_case_insensitive(populated_store):
    """search query is case-insensitive."""
    results = populated_store.search(query="SNAKE_CASE")
    assert len(results) == 1
    assert "snake_case" in results[0].content


def test_search_by_domain_filter(populated_store):
    """search with domain filter restricts results."""
    results = populated_store.search(query="variable", domain="python")
    assert len(results) == 1
    assert results[0].domain == "python"


def test_search_by_domain_filter_excludes_others(populated_store):
    """domain filter excludes non-matching domains."""
    results = populated_store.search(domain="ruby")
    assert len(results) == 0


def test_search_with_min_confidence(populated_store):
    """min_confidence filters out low-confidence observations."""
    results = populated_store.search(min_confidence=8)
    assert len(results) == 2
    assert all(r.confidence >= 8 for r in results)


def test_search_with_limit(populated_store):
    """limit caps the number of returned results."""
    # Without limit, we get all matching
    all_results = populated_store.search(query="")
    assert len(all_results) == 5
    limited = populated_store.search(query="", limit=2)
    assert len(limited) == 2


def test_search_sorts_by_confidence_then_times_confirmed_desc(populated_store):
    """search results are sorted by (confidence desc, times_confirmed desc)."""
    results = populated_store.search(query="")
    confidences = [r.confidence for r in results]
    assert confidences == sorted(confidences, reverse=True)
    # Within same confidence, times_confirmed desc
    for i in range(len(results) - 1):
        if results[i].confidence == results[i + 1].confidence:
            assert results[i].times_confirmed >= results[i + 1].times_confirmed


# ── tag-based filtering ───────────────────────────────────────────────────

def test_search_by_tag(populated_store):
    """search with tags filter returns matching observations."""
    results = populated_store.search(query="", tags=["best-practice"])
    assert len(results) == 2
    assert all("best-practice" in r.tags for r in results)


def test_search_by_multiple_tags_and_logic(populated_store):
    """search with multiple tags requires ALL tags (AND logic)."""
    results = populated_store.search(query="", tags=["best-practice", "linting"])
    assert len(results) == 1
    assert all(t in results[0].tags for t in ["best-practice", "linting"])


def test_search_by_tag_returns_empty_when_no_match(populated_store):
    """search with a tag no observation has returns empty."""
    results = populated_store.search(query="", tags=["nonexistent-tag"])
    assert len(results) == 0


# ── access_scope filtering ────────────────────────────────────────────────

def test_search_by_access_scope(populated_store):
    """search with access_scope filter returns matching observations."""
    results = populated_store.search(query="", access_scope="public")
    assert len(results) == 1
    assert results[0].access_scope == "public"


def test_search_by_access_scope_private(populated_store):
    """access_scope='private' returns only private observations."""
    results = populated_store.search(query="", access_scope="private")
    assert len(results) == 1
    assert results[0].access_scope == "private"


def test_search_no_access_scope_filter_returns_all(populated_store):
    """When access_scope is None, all observations are returned."""
    results = populated_store.search(query="")
    assert len(results) == 5


def test_search_combined_filters(populated_store):
    """Multiple filters combine correctly."""
    results = populated_store.search(
        query="variable", domain="javascript", access_scope="public"
    )
    assert len(results) == 1
    assert results[0].content == "Use camelCase for variables"


# ── get_stats ─────────────────────────────────────────────────────────────

def test_get_stats(populated_store):
    """get_stats returns total, by_type, and avg_confidence."""
    stats = populated_store.get_stats(domain="python")
    assert stats["total"] == 3
    assert stats["by_type"]["rule"] == 2
    assert stats["by_type"]["fact"] == 1
    # Average confidence: (8 + 6 + 9) / 3 = 7.666...
    assert abs(stats["avg_confidence"] - 7.666) < 0.01


def test_get_stats_global_when_no_domain(populated_store):
    """get_stats with domain=None returns global stats."""
    stats = populated_store.get_stats()
    assert stats["total"] == 5


def test_get_stats_empty_store(tmp_path):
    """get_stats on empty store returns zeros."""
    store = ObservationStore(path=tmp_path / "store.json")
    stats = store.get_stats()
    assert stats["total"] == 0
    assert stats["by_type"] == {}
    assert stats["avg_confidence"] == 0.0


# ── get_all_domain_stats ──────────────────────────────────────────────────

def test_get_all_domain_stats(populated_store):
    """get_all_domain_stats returns per-domain breakdown."""
    all_stats = populated_store.get_all_domain_stats()
    assert "python" in all_stats
    assert "javascript" in all_stats
    assert all_stats["python"]["total"] == 3
    assert all_stats["javascript"]["total"] == 2


def test_get_all_domain_stats_empty_store(tmp_path):
    """get_all_domain_stats on empty store returns empty dict."""
    store = ObservationStore(path=tmp_path / "store.json")
    stats = store.get_all_domain_stats()
    assert stats == {}


# ── load / get ────────────────────────────────────────────────────────────

def test_load_existing_store(tmp_path):
    """Store correctly loads from an existing JSON file."""
    store = ObservationStore(path=tmp_path / "store.json")
    store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use snake_case",
    )
    # Reload from the same file
    reloaded = ObservationStore(path=tmp_path / "store.json")
    assert len(reloaded) == 1
    obs = reloaded.search(query="snake_case")[0]
    assert obs.content == "Use snake_case"


def test_get_returns_observation_by_id(tmp_path):
    """get() returns Observation for known id, None for unknown."""
    store = ObservationStore(path=tmp_path / "store.json")
    added = store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use snake_case",
    )
    found = store.get(added.id)
    assert found is not None
    assert found.id == added.id
    assert found.content == "Use snake_case"
    assert store.get("nonexistent") is None


def test_len(tmp_path):
    """__len__ returns the count of stored observations."""
    store = ObservationStore(path=tmp_path / "store.json")
    assert len(store) == 0
    store.add_observation(
        domain="python", observation_type="rule", category="style",
        content="Use snake_case",
    )
    assert len(store) == 1
    store.add_observation(
        domain="python", observation_type="rule", category="type_safety",
        content="Use type hints",
    )
    assert len(store) == 2


def test_empty_store_creates_file_on_init(tmp_path):
    """Store creates the backing file on init so tooling can rely on its presence."""
    path = tmp_path / "store.json"
    assert not path.exists()
    store = ObservationStore(path=path)
    assert path.exists()  # created immediately
    data = json.loads(path.read_text())
    assert data["version"] == 2
    assert data["observations"] == []


def test_store_with_nonexistent_file_starts_empty(tmp_path):
    """ObservationStore with no existing file starts empty."""
    path = tmp_path / "nonexistent.json"
    store = ObservationStore(path=path)
    assert len(store) == 0
    assert store.get_stats()["total"] == 0

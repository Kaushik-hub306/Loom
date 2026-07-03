"""Tests for RuleStore — CRUD, search, migration, and data model."""

import tempfile
from pathlib import Path

import pytest

from loom.engine.rule_store import Rule, RuleStore

# ── Rule dataclass ──────────────────────────────────────────────────


def test_rule_defaults():
    r = Rule(id="x", domain="d", rule_type="rt", rule="do this")
    assert r.sources == []
    assert r.source_type == ""
    assert r.confidence == 5


def test_rule_to_dict_includes_new_fields():
    r = Rule(id="a::b::c", domain="a", rule_type="b", rule="c",
             sources=["s1"], source_type="observation")
    d = r.to_dict()
    assert "sources" in d
    assert "source_type" in d
    assert "source_urls" not in d  # old key gone
    assert d["sources"] == ["s1"]
    assert d["source_type"] == "observation"


def test_rule_from_dict_migrates_old_source_urls():
    old = {
        "id": "a::b::c", "domain": "a", "rule_type": "b", "rule": "c",
        "source_urls": ["http://old.com"],
    }
    r = Rule.from_dict(old)
    assert r.sources == ["http://old.com"]
    assert r.source_type == ""


def test_rule_from_dict_prefers_new_sources():
    new = {
        "id": "a::b::c", "domain": "a", "rule_type": "b", "rule": "c",
        "sources": ["http://new.com"], "source_type": "reflection",
    }
    r = Rule.from_dict(new)
    assert r.sources == ["http://new.com"]
    assert r.source_type == "reflection"


def test_rule_from_dict_new_sources_wins_over_old():
    both = {
        "id": "a::b::c", "domain": "a", "rule_type": "b", "rule": "c",
        "sources": ["new"], "source_urls": ["old"],
    }
    r = Rule.from_dict(both)
    assert r.sources == ["new"]


# ── RuleStore CRUD ──────────────────────────────────────────────────


@pytest.fixture
def store():
    tmp = tempfile.mkdtemp()
    p = Path(tmp) / "rules.json"
    yield RuleStore(p)


def test_add_rule_creates(store: RuleStore):
    r = store.add_rule("coding", "naming", "Use snake_case")
    assert r.id.startswith("coding::naming::")
    assert r.confidence == 5
    assert r.times_confirmed == 1
    assert r.source_type == ""


def test_add_rule_with_source_type(store: RuleStore):
    r = store.add_rule("coding", "naming", "Use snake_case",
                       sources=["context"], source_type="observation")
    assert r.source_type == "observation"
    assert r.sources == ["context"]


def test_add_rule_dedup_merges(store: RuleStore):
    r1 = store.add_rule("coding", "naming", "Use snake_case")
    r2 = store.add_rule("coding", "naming", "Use snake_case",
                        sources=["ctx2"], source_type="reflection")
    assert r1.id == r2.id
    assert r2.times_confirmed == 2
    assert r2.confidence == 6  # incremented by 1
    assert "ctx2" in r2.sources
    assert r2.source_type == "reflection"  # updated


def test_add_rule_backward_compat_source_url(store: RuleStore):
    r = store.add_rule("coding", "naming", "Use camelCase", source_url="http://x.com")
    assert "http://x.com" in r.sources


def test_search_rules_finds_in_sources(store: RuleStore):
    store.add_rule("coding", "naming", "Rule text", sources=["special-context-xyz"])
    results = store.search_rules("special-context")
    assert len(results) == 1


def test_search_rules_filters_by_rule_type(store: RuleStore):
    store.add_rule("coding", "naming", "Use snake_case")
    store.add_rule("coding", "testing", "Write tests")
    results = store.search_rules("", rule_type="testing")
    assert len(results) == 1
    assert results[0].rule_type == "testing"


def test_search_rules_respects_min_confidence(store: RuleStore):
    store.add_rule("coding", "naming", "Use snake_case", confidence=3)
    store.add_rule("coding", "testing", "Write tests", confidence=8)
    results = store.search_rules("", min_confidence=5)
    assert len(results) == 1
    assert results[0].rule_type == "testing"


def test_search_rules_sorts_by_confidence(store: RuleStore):
    store.add_rule("coding", "a", "Aaa", confidence=3)
    store.add_rule("coding", "b", "Bbb", confidence=9)
    results = store.search_rules("")
    assert results[0].confidence == 9


def test_promote_rule(store: RuleStore):
    r = store.add_rule("coding", "naming", "Use snake_case", confidence=5)
    store.promote_rule(r.id)
    assert store.get_rule(r.id).confidence == 6
    assert store.get_rule(r.id).times_confirmed == 2


def test_demote_rule(store: RuleStore):
    r = store.add_rule("coding", "naming", "Use snake_case", confidence=3)
    store.demote_rule(r.id)
    assert store.get_rule(r.id).confidence == 2
    assert store.get_rule(r.id).times_violated == 1


def test_delete_rule(store: RuleStore):
    r = store.add_rule("coding", "naming", "Delete me")
    assert store.delete_rule(r.id)
    assert store.get_rule(r.id) is None


def test_get_active_rules(store: RuleStore):
    store.add_rule("a", "t1", "r1", confidence=5)
    store.add_rule("a", "t2", "r2", confidence=1)
    assert len(store.get_active_rules(min_confidence=3)) == 1


def test_get_rules_by_domain(store: RuleStore):
    store.add_rule("coding", "naming", "r1")
    store.add_rule("style", "formatting", "r2")
    assert len(store.get_rules_by_domain("coding")) == 1


def test_get_all_domain_stats(store: RuleStore):
    store.add_rule("coding", "naming", "r1", confidence=8)
    store.add_rule("coding", "testing", "r2", confidence=4)
    store.add_rule("style", "formatting", "r3", confidence=6)
    stats = store.get_all_domain_stats()
    assert "coding" in stats
    assert "style" in stats
    assert stats["coding"]["total"] == 2
    assert stats["coding"]["avg_confidence"] == 6.0

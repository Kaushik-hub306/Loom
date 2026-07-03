"""Storage-safety regression tests.

These lock in the fixes for the worst bug class found in the audit:
a single malformed entry (or a crash mid-write) permanently destroying
the entire rule store.
"""

import json

from loom.engine.rule_store import RuleStore
from loom.engine.timeline import Timeline
from loom.storage.jsonio import atomic_write_json, load_json_dict


def test_malformed_entry_does_not_wipe_store(tmp_path):
    """One bad entry used to erase every good rule on the next save."""
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({
        "rules": [
            {"id": "a::x::one", "domain": "a", "rule_type": "x", "rule": "one"},
            {"this-entry": "is-broken"},
            None,
            {"id": "a::x::two", "domain": "a", "rule_type": "x", "rule": "two"},
        ]
    }))

    store = RuleStore(path)
    assert len(store) == 2, "valid entries must survive a malformed sibling"

    store.add_rule(domain="a", rule_type="x", rule="three")
    reloaded = RuleStore(path)
    assert len(reloaded) == 3, "the save after a partial load must not lose rules"


def test_corrupt_file_is_quarantined_not_destroyed(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text("{definitely not json")

    store = RuleStore(path)
    assert len(store) == 0

    quarantined = list(tmp_path.glob("rules.json.corrupt-*"))
    assert quarantined, "corrupt file must be preserved for recovery"
    assert quarantined[0].read_text() == "{definitely not json"


def test_wrong_top_level_type_is_quarantined(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps([1, 2, 3]))  # array instead of object
    store = RuleStore(path)  # must not raise AttributeError
    assert len(store) == 0
    assert list(tmp_path.glob("rules.json.corrupt-*"))


def test_atomic_write_leaves_no_partial_files(tmp_path):
    path = tmp_path / "data.json"
    atomic_write_json(path, {"k": "v"})
    assert load_json_dict(path) == {"k": "v"}
    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert not leftovers, "temp files must be cleaned up or renamed"


def test_slug_collision_does_not_merge_distinct_rules(tmp_path):
    store = RuleStore(tmp_path / "rules.json")
    base = "always use dependency injection for services in the api layer x"
    r1 = store.add_rule(domain="c", rule_type="t", rule=base + " because of testability")
    r2 = store.add_rule(domain="c", rule_type="t", rule=base + " but never for repositories")
    assert r1.id != r2.id, "distinct rules silently merged (slug collision)"
    assert len(store) == 2

    # Identical text must still deduplicate into a confirmation.
    r3 = store.add_rule(domain="c", rule_type="t", rule=base + " because of testability")
    assert r3.id == r1.id
    assert r3.times_confirmed == 2


def test_punctuation_only_rules_do_not_collide(tmp_path):
    store = RuleStore(tmp_path / "rules.json")
    r1 = store.add_rule(domain="c", rule_type="t", rule="!!!???")
    r2 = store.add_rule(domain="c", rule_type="t", rule="###@@@")
    assert r1.id != r2.id


def test_reload_if_stale_sees_external_writes(tmp_path):
    path = tmp_path / "rules.json"
    writer = RuleStore(path)
    writer.add_rule(domain="c", rule_type="t", rule="first rule")

    reader = RuleStore(path)
    writer.add_rule(domain="c", rule_type="t", rule="second rule from another process")

    assert reader.reload_if_stale() is True
    assert len(reader) == 2
    assert reader.reload_if_stale() is False, "no change → no reload"


def test_confidence_is_clamped(tmp_path):
    store = RuleStore(tmp_path / "rules.json")
    high = store.add_rule(domain="c", rule_type="t", rule="too confident", confidence=99)
    low = store.add_rule(domain="c", rule_type="t", rule="not confident", confidence=-5)
    assert high.confidence == 10
    assert low.confidence == 1


def test_timeline_limit_returns_most_recent(tmp_path):
    """timeline.query(limit=N) used to return the OLDEST N entries."""
    tl = Timeline(tmp_path)
    for i in range(10):
        tl.record(
            action="learned", rule_id=f"r{i}", rule_text=f"rule {i}",
            agent="a", project="p", decision_context="ctx",
        )

    latest_three = tl.query(limit=3)
    assert [e.rule_id for e in latest_three] == ["r7", "r8", "r9"]


def test_timeline_naive_timestamp_does_not_crash(tmp_path):
    """Hand-edited naive timestamps must not raise TypeError on compare."""
    tl = Timeline(tmp_path)
    tl.record(
        action="learned", rule_id="r1", rule_text="rule", agent="a",
        project="p", decision_context="ctx",
    )
    # Inject a naive-timestamp entry, as an external tool might.
    with open(tl._path, "a") as fh:
        fh.write(json.dumps({
            "timestamp": "2026-01-01T00:00:00", "action": "learned",
            "domain": "", "rule_id": "r2", "rule_text": "naive", "agent": "a",
            "project": "p", "decision_context": "", "confidence": 5,
        }) + "\n")

    results = tl.query(date_from="2020-01-01T00:00:00+00:00")
    assert len(results) == 2

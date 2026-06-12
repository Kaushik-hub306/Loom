"""Tests for DecayManager — confidence decay over time."""

from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from loom.engine.decay_manager import DecayManager
from loom.engine.rule_store import RuleStore, Rule


# ── helpers ───────────────────────────────────────────────────────────────

def _make_rule(
    rule_id: str = "test::type_safety::use-hints",
    domain: str = "test",
    rule_type: str = "type_safety",
    rule_text: str = "Use type hints",
    confidence: int = 8,
    updated_at: str | None = None,
) -> Rule:
    """Create a Rule with given parameters."""
    return Rule(
        id=rule_id,
        domain=domain,
        rule_type=rule_type,
        rule=rule_text,
        confidence=confidence,
        updated_at=updated_at or "",
    )


def _make_store(tmp_path: Path, rules: list[Rule] | None = None) -> RuleStore:
    """Create a RuleStore in a temp directory, optionally pre-populated."""
    store_path = tmp_path / "rules.json"
    store = RuleStore(store_path)
    # Clear auto-saved empty rules
    store._store.observations.clear()
    store._store._save()
    # Re-load so store reflects empty state
    store._store._load()
    if rules:
        for rule in rules:
            obs = rule.to_observation()
            store._store.observations[obs.id] = obs
        store._store._save()
        store._store._load()
    return store


# ── tests ─────────────────────────────────────────────────────────────────


class TestApplyDecay:
    """Tests for apply_decay() — confidence decay on stale rules."""

    def test_decay_decreases_confidence_on_old_rules(self, tmp_path):
        """Rules with updated_at older than decay_days should lose confidence."""
        old_date = (
            datetime.now(timezone.utc) - timedelta(days=60)
        ).isoformat()
        rule = _make_rule(confidence=8, updated_at=old_date)
        store = _make_store(tmp_path, [rule])
        manager = DecayManager(store, decay_days=30)

        decayed = manager.apply_decay()

        assert len(decayed) == 1
        assert decayed[0].id == rule.id
        assert decayed[0].confidence < 8

    def test_recently_updated_rules_are_not_decayed(self, tmp_path):
        """Rules updated within the decay window should NOT be decayed."""
        recent_date = (
            datetime.now(timezone.utc) - timedelta(days=5)
        ).isoformat()
        rule = _make_rule(confidence=8, updated_at=recent_date)
        store = _make_store(tmp_path, [rule])
        manager = DecayManager(store, decay_days=30)

        decayed = manager.apply_decay()

        assert len(decayed) == 0
        assert store.rules[rule.id].confidence == 8

    def test_confidence_never_goes_below_floor(self, tmp_path):
        """Confidence must never drop below MIN_CONFIDENCE (1)."""
        old_date = (
            datetime.now(timezone.utc) - timedelta(days=365)
        ).isoformat()
        rule = _make_rule(confidence=2, updated_at=old_date)
        store = _make_store(tmp_path, [rule])
        manager = DecayManager(store, decay_days=30)

        manager.apply_decay()
        # Re-load from store to get the persisted value
        store._load()
        rule_after = store.rules[rule.id]

        assert rule_after.confidence >= DecayManager.MIN_CONFIDENCE

    def test_apply_decay_with_custom_decay_days(self, tmp_path):
        """A short decay_days window should cause decay on moderately old rules."""
        somewhat_old = (
            datetime.now(timezone.utc) - timedelta(days=15)
        ).isoformat()
        rule = _make_rule(confidence=8, updated_at=somewhat_old)
        store = _make_store(tmp_path, [rule])
        # Use a 10-day window — 15 days is older, so it should decay
        manager = DecayManager(store, decay_days=10)

        decayed = manager.apply_decay()

        assert len(decayed) == 1
        assert decayed[0].confidence < 8

    def test_decay_with_no_updated_at(self, tmp_path):
        """Rules with no updated_at should be skipped gracefully."""
        rule = _make_rule(confidence=8, updated_at=None)
        store = _make_store(tmp_path, [rule])
        manager = DecayManager(store, decay_days=30)

        decayed = manager.apply_decay()

        assert len(decayed) == 0
        assert store.rules[rule.id].confidence == 8

    def test_decay_skips_rule_already_at_floor(self, tmp_path):
        """A rule already at MIN_CONFIDENCE should not be decayed further."""
        old_date = (
            datetime.now(timezone.utc) - timedelta(days=365)
        ).isoformat()
        rule = _make_rule(
            confidence=DecayManager.MIN_CONFIDENCE, updated_at=old_date,
        )
        store = _make_store(tmp_path, [rule])
        manager = DecayManager(store, decay_days=30)

        decayed = manager.apply_decay()

        # Should still be at floor; the rule is already min so no decay action
        assert store.rules[rule.id].confidence == DecayManager.MIN_CONFIDENCE


class TestGetHealth:
    """Tests for get_health() — store health reporting."""

    def test_healthy_and_decaying_mix(self, tmp_path):
        """get_health should count healthy vs decaying rules correctly."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        recent_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        rules = [
            _make_rule("a::type::one", confidence=8, updated_at=old_date),
            _make_rule("a::type::two", confidence=8, updated_at=recent_date),
            _make_rule("a::type::three", confidence=8, updated_at=recent_date),
        ]
        store = _make_store(tmp_path, rules)
        manager = DecayManager(store, decay_days=30)

        health = manager.get_health()

        assert health["total"] == 3
        assert health["healthy"] == 2
        assert health["decaying"] == 1
        assert 1 <= health["avg_confidence"] <= 10

    def test_empty_store_returns_zeros(self, tmp_path):
        """get_health on an empty store should return zeros, no division error."""
        store = _make_store(tmp_path, [])
        manager = DecayManager(store)

        health = manager.get_health()

        assert health["total"] == 0
        assert health["healthy"] == 0
        assert health["decaying"] == 0
        assert health["avg_confidence"] == 0.0

    def test_all_healthy(self, tmp_path):
        """When all rules are recent, decaying count should be 0."""
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        rules = [
            _make_rule("a::type::a", updated_at=recent),
            _make_rule("a::type::b", updated_at=recent),
        ]
        store = _make_store(tmp_path, rules)
        manager = DecayManager(store, decay_days=30)

        health = manager.get_health()

        assert health["total"] == 2
        assert health["healthy"] == 2
        assert health["decaying"] == 0

    def test_rule_with_no_updated_at_is_not_counted_as_decaying(self, tmp_path):
        """Rules missing updated_at should be treated as healthy, not decaying."""
        rule = _make_rule(updated_at=None)
        store = _make_store(tmp_path, [rule])
        manager = DecayManager(store, decay_days=30)

        health = manager.get_health()

        assert health["total"] == 1
        # Rule has no updated_at → not counted as decaying
        assert health["decaying"] == 0

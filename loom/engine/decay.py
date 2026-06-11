"""Decay manager — confidence degradation and archival of stale rules."""

from datetime import datetime, timezone, timedelta
from pathlib import Path


class DecayManager:
    """Manages rule confidence decay and archival.

    Active rules that haven't been reinforced recently lose confidence.
    Rules that drop below the archival threshold are archived.
    """

    def __init__(self, decay_days: int = 30, archive_threshold: float = 2.0, decay_rate: float = 0.5):
        self.decay_days = decay_days
        self.archive_threshold = archive_threshold
        self.decay_rate = decay_rate

    def run_decay(self, store) -> int:
        """Apply decay to all active rules in the store. Returns count of archived rules."""
        from loom.engine.rule_store import RuleStatus

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self.decay_days)
        archived_count = 0

        for rule in store.rules.values():
            if rule.status == RuleStatus.ARCHIVED:
                continue
            if rule.status == RuleStatus.HARD_RULE:
                continue

            try:
                updated = datetime.fromisoformat(rule.updated_at)
            except (ValueError, TypeError):
                updated = datetime.fromisoformat(rule.created_at)

            if updated < cutoff:
                new_confidence = max(1.0, rule.confidence - self.decay_rate)
                store.update_rule(rule.id, confidence=new_confidence)

                if new_confidence <= self.archive_threshold:
                    store.archive_rule(rule.id)
                    archived_count += 1

        return archived_count

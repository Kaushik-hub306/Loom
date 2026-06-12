"""DecayManager — manages rule confidence decay over time."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from .rule_store import RuleStore, Rule


class DecayManager:
    """Decays rule confidence over time when rules aren't reinforced."""

    DEFAULT_DECAY_DAYS: int = 30  # Days before a rule starts decaying
    DECAY_RATE: int = 1  # Confidence points lost per decay period
    MIN_CONFIDENCE: int = 1

    def __init__(self, store: RuleStore, decay_days: int = DEFAULT_DECAY_DAYS) -> None:
        self.store: RuleStore = store
        self.decay_days: int = decay_days

    def apply_decay(self) -> list[Rule]:
        """Decay all rules that haven't been updated recently. Returns decayed rules.

        Rules with ``updated_at`` set to ``None``, an empty string, or an
        unparseable date are skipped gracefully rather than raising an error.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self.decay_days)
        decayed: list[Rule] = []

        for rule in list(self.store.rules.values()):
            # ── gracefully skip rules with missing or bad updated_at ──────
            if not rule.updated_at:
                continue

            try:
                updated = datetime.fromisoformat(rule.updated_at)
            except (ValueError, TypeError):
                continue

            if updated < cutoff and rule.confidence > self.MIN_CONFIDENCE:
                # Each full decay_days period past cutoff costs DECAY_RATE
                periods = (now - updated).days // self.decay_days
                decay = min(
                    periods * self.DECAY_RATE,
                    rule.confidence - self.MIN_CONFIDENCE,
                )
                if decay > 0:
                    rule.confidence -= decay
                    rule.updated_at = now.isoformat()
                    decayed.append(rule)

        if decayed:
            self.store._save()
        return decayed

    def get_health(self) -> dict[str, Any]:
        """Report on rule health across the store.

        Returns zero values (not a divide-by-zero error) when the store is
        empty.  Rules missing ``updated_at`` are excluded from the decaying
        count (they are treated as healthy).
        """
        now = datetime.now(timezone.utc)
        rules = list(self.store.rules.values())

        if not rules:
            return {
                "total": 0,
                "healthy": 0,
                "decaying": 0,
                "avg_confidence": 0.0,
            }

        decaying: int = 0
        for r in rules:
            if not r.updated_at:
                continue
            try:
                updated = datetime.fromisoformat(r.updated_at)
            except (ValueError, TypeError):
                continue
            if (now - updated).days >= self.decay_days:
                decaying += 1

        total = len(rules)
        return {
            "total": total,
            "healthy": total - decaying,
            "decaying": decaying,
            "avg_confidence": sum(r.confidence for r in rules) / total,
        }

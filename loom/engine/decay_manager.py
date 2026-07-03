"""DecayManager — manages rule confidence decay over time."""

from datetime import datetime, timedelta, timezone

from loom.timeutil import parse_iso_utc

from .rule_store import Rule, RuleStore


class DecayManager:
    """Decays rule confidence over time when rules aren't reinforced."""

    DEFAULT_DECAY_DAYS = 30  # Days before a rule starts decaying
    DECAY_RATE = 1  # Confidence points lost per decay period
    MIN_CONFIDENCE = 1

    def __init__(self, store: RuleStore, decay_days: int = DEFAULT_DECAY_DAYS):
        self.store = store
        self.decay_days = decay_days

    def apply_decay(self) -> list[Rule]:
        """Decay all rules that haven't been updated recently. Returns decayed rules."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self.decay_days)
        decayed = []

        for rule in list(self.store.rules.values()):
            if not rule.updated_at:
                continue

            updated = parse_iso_utc(rule.updated_at)
            if updated is None:
                continue

            if updated < cutoff and rule.confidence > self.MIN_CONFIDENCE:
                # Each full decay_days period past cutoff costs DECAY_RATE
                periods = (now - updated).days // self.decay_days
                decay = min(periods * self.DECAY_RATE, rule.confidence - self.MIN_CONFIDENCE)
                if decay > 0:
                    rule.confidence -= decay
                    rule.updated_at = now.isoformat()
                    decayed.append(rule)

        if decayed:
            self.store._save()
        return decayed

    def get_health(self) -> dict:
        """Report on rule health across the store."""
        now = datetime.now(timezone.utc)
        rules = list(self.store.rules.values())
        if not rules:
            return {
                "total": 0,
                "healthy": 0,
                "decaying": 0,
                "avg_confidence": 0.0,
            }

        decaying = 0
        for r in rules:
            if not r.updated_at:
                continue
            updated = parse_iso_utc(r.updated_at)
            if updated is None:
                continue
            if (now - updated).days >= self.decay_days:
                decaying += 1

        return {
            "total": len(rules),
            "healthy": len(rules) - decaying,
            "decaying": decaying,
            "avg_confidence": sum(r.confidence for r in rules) / len(rules),
        }

"""RetentionManager — tiered retention policies for organizational knowledge."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

from loom.timeutil import parse_iso_utc


class RetentionPolicy(Enum):
    """Tiered retention for learned rules.

    * PERMANENT  — Never decays. For org decisions, architecture, security.
    * LONG_TERM  — 180 days grace, 1 point per 90 days after.
    * STANDARD   — 30 days grace, 1 point per 30 days (current Loom default).
    * TRANSIENT  — 7 days grace, 2 points per 7 days (experimental patterns).
    """

    PERMANENT = "permanent"
    LONG_TERM = "long_term"
    STANDARD = "standard"
    TRANSIENT = "transient"

    @property
    def grace_days(self) -> int | None:
        """Days before decay starts (None means never)."""
        _map = {
            RetentionPolicy.PERMANENT: None,
            RetentionPolicy.LONG_TERM: 180,
            RetentionPolicy.STANDARD: 30,
            RetentionPolicy.TRANSIENT: 7,
        }
        return _map[self]

    @property
    def decay_rate(self) -> int:
        """Confidence points lost per decay period."""
        _map = {
            RetentionPolicy.PERMANENT: 0,
            RetentionPolicy.LONG_TERM: 1,
            RetentionPolicy.STANDARD: 1,
            RetentionPolicy.TRANSIENT: 2,
        }
        return _map[self]

    @property
    def decay_period_days(self) -> int:
        """Number of days per decay increment."""
        _map = {
            RetentionPolicy.PERMANENT: 0,
            RetentionPolicy.LONG_TERM: 90,
            RetentionPolicy.STANDARD: 30,
            RetentionPolicy.TRANSIENT: 7,
        }
        return _map[self]


@dataclass
class RetentionEntry:
    """A single retention-policy assignment for a rule."""

    rule_id: str
    policy: str  # RetentionPolicy value
    set_at: str = ""  # ISO timestamp
    set_by: str = ""  # Who / what set this policy
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "policy": self.policy,
            "set_at": self.set_at,
            "set_by": self.set_by,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RetentionEntry":
        return cls(
            rule_id=d.get("rule_id", ""),
            policy=d.get("policy", RetentionPolicy.STANDARD.value),
            set_at=d.get("set_at", ""),
            set_by=d.get("set_by", ""),
            reason=d.get("reason", ""),
        )


@dataclass
class ArchivedRule:
    """A rule that has been archived instead of deleted."""

    id: str
    domain: str
    rule: str
    rule_type: str = ""
    example: str = ""
    confidence: int = 5
    times_confirmed: int = 0
    times_violated: int = 0
    sources: list[str] = field(default_factory=list)
    source_type: str = ""
    created_at: str = ""
    archived_at: str = ""
    archived_by: str = ""
    archive_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "rule": self.rule,
            "rule_type": self.rule_type,
            "example": self.example,
            "confidence": self.confidence,
            "times_confirmed": self.times_confirmed,
            "times_violated": self.times_violated,
            "sources": self.sources,
            "source_type": self.source_type,
            "created_at": self.created_at,
            "archived_at": self.archived_at,
            "archived_by": self.archived_by,
            "archive_reason": self.archive_reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ArchivedRule":
        return cls(
            id=d.get("id", ""),
            domain=d.get("domain", ""),
            rule=d.get("rule", d.get("rule_text", "")),
            rule_type=d.get("rule_type", ""),
            example=d.get("example", ""),
            confidence=d.get("confidence", 5),
            times_confirmed=d.get("times_confirmed", 0),
            times_violated=d.get("times_violated", 0),
            sources=d.get("sources", []),
            source_type=d.get("source_type", ""),
            created_at=d.get("created_at", ""),
            archived_at=d.get("archived_at", ""),
            archived_by=d.get("archived_by", ""),
            archive_reason=d.get("archive_reason", ""),
        )


class RetentionManager:
    """Manages tiered retention policies so organisational knowledge is never
    lost while transient patterns gracefully decay.

    Storage
    -------
    * **retention policies** — ``{store_dir}/retention.json``
    * **archive** — ``{store_dir}/archive.json``
    """

    def __init__(self, store_dir: Path, rule_store, decay_manager):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.rule_store = rule_store
        self.decay_manager = decay_manager

        self._retention_path = self.store_dir / "retention.json"
        self._archive_path = self.store_dir / "archive.json"

        self.policies: dict[str, RetentionEntry] = {}
        self.archived: dict[str, ArchivedRule] = {}

        self._load_retention()
        self._load_archive()

    # ── helpers ─────────────────────────────────────────────────────

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── retention storage ───────────────────────────────────────────

    def _load_retention(self):
        from loom.storage.jsonio import load_entries, load_json_dict

        data = load_json_dict(self._retention_path)
        self.policies = {}
        for entry in load_entries(
            data.get("policies"), RetentionEntry.from_dict,
            source_name=self._retention_path.name,
        ):
            self.policies[entry.rule_id] = entry

    def _save_retention(self):
        from loom.storage.jsonio import atomic_write_json

        data = {"policies": [e.to_dict() for e in self.policies.values()]}
        atomic_write_json(self._retention_path, data)

    # ── archive storage ─────────────────────────────────────────────

    def _load_archive(self):
        from loom.storage.jsonio import load_entries, load_json_dict

        data = load_json_dict(self._archive_path)
        self.archived = {}
        for rule in load_entries(
            data.get("archived"), ArchivedRule.from_dict,
            source_name=self._archive_path.name,
        ):
            self.archived[rule.id] = rule

    def _save_archive(self):
        from loom.storage.jsonio import atomic_write_json

        data = {"archived": [r.to_dict() for r in self.archived.values()]}
        atomic_write_json(self._archive_path, data)

    # ── policy management ───────────────────────────────────────────

    def set_retention(
        self,
        rule_id: str,
        policy: RetentionPolicy,
        set_by: str = "",
        reason: str = "",
    ) -> RetentionEntry:
        """Set a rule's retention tier.

        Args:
            rule_id: The rule identifier.
            policy: A :class:`RetentionPolicy` member.
            set_by: Who or what is setting this policy.
            reason: Why this tier was chosen.
        """
        entry = RetentionEntry(
            rule_id=rule_id,
            policy=policy.value,
            set_at=self._now(),
            set_by=set_by,
            reason=reason,
        )
        self.policies[rule_id] = entry
        self._save_retention()
        return entry

    def get_retention(self, rule_id: str) -> RetentionPolicy:
        """Return the current retention policy for a rule.

        Defaults to :attr:`RetentionPolicy.STANDARD` if no policy has been
        explicitly set.
        """
        entry = self.policies.get(rule_id)
        if entry is None:
            return RetentionPolicy.STANDARD
        try:
            return RetentionPolicy(entry.policy)
        except ValueError:
            return RetentionPolicy.STANDARD

    def promote_to_permanent(
        self,
        rule_id: str,
        reason: str = "",
        set_by: str = "",
    ) -> RetentionEntry:
        """Mark a rule as permanent organisational knowledge.

        Permanent rules are never decayed.
        """
        return self.set_retention(
            rule_id=rule_id,
            policy=RetentionPolicy.PERMANENT,
            set_by=set_by,
            reason=reason,
        )

    def get_permanent_rules(self) -> list[str]:
        """Return the IDs of all rules that will never decay."""
        return [
            rid for rid, entry in self.policies.items()
            if entry.policy == RetentionPolicy.PERMANENT.value
        ]

    # ── decay ───────────────────────────────────────────────────────

    def apply_retention_policies(self) -> list[dict]:
        """Apply decay to each rule based on its retention tier.

        Iterates over all rules in the RuleStore, looks up each rule's
        RetentionPolicy, and decays confidence accordingly.  Permanent
        rules are always skipped.

        Returns a list of dicts describing what was decayed.
        """
        now = datetime.now(timezone.utc)
        decayed: list[dict] = []

        for rule in list(self.rule_store.rules.values()):
            policy = self.get_retention(rule.id)

            # Permanent rules never decay
            if policy == RetentionPolicy.PERMANENT:
                continue

            grace = policy.grace_days  # None only for PERMANENT, handled above
            rate = policy.decay_rate
            period_days = policy.decay_period_days

            if grace is None or rate <= 0 or period_days <= 0:
                continue

            if not rule.updated_at:
                continue

            updated = parse_iso_utc(rule.updated_at)
            if updated is None:
                continue

            age_days = (now - updated).days
            if age_days < grace:
                continue

            # Each full decay period past grace costs the decay rate
            periods = (age_days - grace) // period_days
            decay = min(periods * rate, rule.confidence - 1)
            if decay > 0:
                rule.confidence -= decay
                rule.updated_at = now.isoformat()
                decayed.append({
                    "rule_id": rule.id,
                    "domain": rule.domain,
                    "policy": policy.value,
                    "decay_applied": decay,
                    "new_confidence": rule.confidence,
                })

        if decayed:
            self.rule_store._save()

        return decayed

    def get_decay_forecast(self, days: int = 90) -> list[dict]:
        """Predict which rules will decay in the next *days* days and when.

        Returns a list of forecast dicts, ordered by predicted decay date
        (soonest first).
        """
        now = datetime.now(timezone.utc)
        forecasts: list[dict] = []

        for rule in self.rule_store.rules.values():
            policy = self.get_retention(rule.id)

            if policy == RetentionPolicy.PERMANENT:
                continue

            grace = policy.grace_days
            period_days = policy.decay_period_days

            if grace is None or period_days <= 0:
                continue

            if not rule.updated_at:
                continue

            updated = parse_iso_utc(rule.updated_at)
            if updated is None:
                continue

            # When will the next decay hit?
            decay_start = updated + timedelta(days=grace)
            if decay_start > now + timedelta(days=days):
                # Decay starts outside the forecast window
                continue

            first_decay = decay_start
            # If we're already past the first decay, find the next one
            if first_decay < now:
                periods_elapsed = (now - first_decay).days // period_days
                first_decay = first_decay + timedelta(days=(periods_elapsed + 1) * period_days)

            if first_decay > now + timedelta(days=days):
                continue

            forecasts.append({
                "rule_id": rule.id,
                "domain": rule.domain,
                "rule_text": rule.rule,
                "current_confidence": rule.confidence,
                "policy": policy.value,
                "next_decay_date": first_decay.isoformat(),
                "confidence_after_decay": max(1, rule.confidence - policy.decay_rate),
            })

        forecasts.sort(key=lambda f: f["next_decay_date"])
        return forecasts

    # ── archive ─────────────────────────────────────────────────────

    def archive_rule(
        self,
        rule_id: str,
        reason: str = "",
        archived_by: str = "",
    ) -> ArchivedRule | None:
        """Archive a rule instead of deleting it.

        The rule is removed from the active RuleStore but preserved in the
        archive so the timeline and decision trail remain intact.
        """
        rule = self.rule_store.get_rule(rule_id)
        if rule is None:
            return None

        archived_rule = ArchivedRule(
            id=rule.id,
            domain=rule.domain,
            rule=rule.rule,
            rule_type=rule.rule_type,
            example=rule.example,
            confidence=rule.confidence,
            times_confirmed=rule.times_confirmed,
            times_violated=rule.times_violated,
            sources=list(rule.sources),
            source_type=rule.source_type,
            created_at=rule.created_at,
            archived_at=self._now(),
            archived_by=archived_by,
            archive_reason=reason,
        )
        self.archived[rule.id] = archived_rule
        self._save_archive()

        self.rule_store.delete_rule(rule_id)

        return archived_rule

    def get_archived_rules(self) -> list[ArchivedRule]:
        """Return all archived rules."""
        return list(self.archived.values())

    def restore_rule(self, rule_id: str) -> bool:
        """Restore an archived rule back to the active store.

        Returns True if the rule was restored, False if it wasn't found in
        the archive.
        """
        archived = self.archived.get(rule_id)
        if archived is None:
            return False

        self.rule_store.add_rule(
            domain=archived.domain,
            rule_type=archived.rule_type,
            rule=archived.rule,
            example=archived.example,
            confidence=archived.confidence,
            sources=list(archived.sources),
            source_type=archived.source_type,
        )

        del self.archived[rule_id]
        self._save_archive()
        return True

    # ── counts ──────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self.policies)

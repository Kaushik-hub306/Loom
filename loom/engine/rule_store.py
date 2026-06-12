"""RuleStore — DEPRECATED adapter that wraps ObservationStore / Observation.

The ``Rule`` dataclass and ``RuleStore`` class are being replaced by the richer
``Observation`` / ``ObservationStore`` in Loom v2.  This module now provides
backward-compatible shims that delegate to the new classes and emit
``FutureWarning`` so callers can migrate.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

from .observation import Observation
from .observation_store import ObservationStore as _ObservationStore


# ── Deprecated Rule dataclass ────────────────────────────────────────────────
# We keep the original Rule dataclass for type compatibility, but all
# construction goes through Observation now.


@dataclass
class Rule:
    """DEPRECATED — use ``Observation`` instead."""

    id: str
    domain: str
    rule_type: str
    rule: str
    example: str = ""
    confidence: int = 5
    times_confirmed: int = 0
    times_violated: int = 0
    sources: list[str] = field(default_factory=list)
    source_type: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        warnings.warn(
            "Rule.to_dict() is deprecated; use Observation.to_dict() instead.",
            FutureWarning,
            stacklevel=2,
        )
        return {
            "id": self.id,
            "domain": self.domain,
            "rule_type": self.rule_type,
            "rule": self.rule,
            "example": self.example,
            "confidence": self.confidence,
            "times_confirmed": self.times_confirmed,
            "times_violated": self.times_violated,
            "sources": self.sources,
            "source_type": self.source_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        warnings.warn(
            "Rule.from_dict() is deprecated; use Observation.from_dict() instead.",
            FutureWarning,
            stacklevel=2,
        )
        obs = Observation.from_dict(d)
        # Merge main's sources/source_type fields
        sources = list(d.get("sources", d.get("source_urls", obs.source_urls)))
        return cls(
            id=obs.id,
            domain=obs.domain,
            rule_type=obs.category,
            rule=obs.content,
            example=obs.context.get("example", ""),
            confidence=obs.confidence,
            times_confirmed=obs.times_confirmed,
            times_violated=obs.times_violated,
            sources=sources,
            source_type=d.get("source_type", ""),
            created_at=obs.created_at,
            updated_at=obs.updated_at,
        )

    @classmethod
    def from_observation(cls, obs: Observation) -> "Rule":
        """Convert an Observation to the legacy Rule shape (no warning)."""
        return cls(
            id=obs.id,
            domain=obs.domain,
            rule_type=obs.category,
            rule=obs.content,
            example=obs.context.get("example", ""),
            confidence=obs.confidence,
            times_confirmed=obs.times_confirmed,
            times_violated=obs.times_violated,
            sources=list(obs.source_urls),
            source_type="",
            created_at=obs.created_at,
            updated_at=obs.updated_at,
        )

    def to_observation(self) -> Observation:
        """Convert this Rule to an Observation (no warning)."""
        return Observation(
            id=self.id,
            observation_type="rule",
            domain=self.domain,
            category=self.rule_type,
            content=self.rule,
            context={"example": self.example, "source_type": self.source_type} if self.source_type else {"example": self.example},
            confidence=self.confidence,
            times_confirmed=self.times_confirmed,
            times_violated=self.times_violated,
            source_urls=list(self.sources),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


# ── Deprecated RuleStore class ───────────────────────────────────────────────


class RuleStore:
    """DEPRECATED — wraps ``ObservationStore``.  Emits ``FutureWarning``."""

    def __init__(self, path: Path):
        warnings.warn(
            "RuleStore is deprecated; use ObservationStore instead.",
            FutureWarning,
            stacklevel=2,
        )
        # Point at the new store.json; ObservationStore handles migration
        store_path = Path(path)
        if store_path.name == "rules.json":
            store_path = store_path.parent / "store.json"
        self._store = _ObservationStore(store_path)

    # ── delegate properties ──────────────────────────────────────────────

    @property
    def path(self) -> Path:
        return self._store.path

    @property
    def rules(self) -> dict[str, Rule]:
        """Return observations wrapped as Rule objects."""
        return {
            oid: Rule.from_observation(obs)
            for oid, obs in self._store.observations.items()
        }

    # ── CRUD (delegates) ─────────────────────────────────────────────────

    def get_rule(self, rule_id: str) -> Rule | None:
        obs = self._store.get_observation(rule_id)
        return Rule.from_observation(obs) if obs else None

    def _make_id(self, domain: str, rule_type: str, rule_text: str) -> str:
        """Legacy ID format: domain::rule_type::slug (no observation_type prefix)."""
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", rule_text.lower().strip())[:60].strip("-")
        return f"{domain}::{rule_type}::{slug}"

    def _now(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def add_rule(
        self,
        domain: str,
        rule_type: str,
        rule: str,
        example: str = "",
        confidence: int = 5,
        source_url: str = "",
        sources: list[str] | None = None,
        source_type: str = "",
    ) -> Rule:
        """Add a rule via ObservationStore, preserving legacy Rule semantics."""
        # Build sources list: new `sources` param takes priority
        source_list = list(sources) if sources else []
        if source_url and source_url not in source_list:
            source_list.append(source_url)

        rule_id = self._make_id(domain, rule_type, rule)
        now = self._now()

        # Check for existing match via legacy ID
        if rule_id in self._store.observations:
            existing_obs = self._store.observations[rule_id]
            existing_obs.confidence = min(10, existing_obs.confidence + 1)
            existing_obs.times_confirmed += 1
            existing_obs.updated_at = now
            for src in source_list:
                if src not in existing_obs.source_urls:
                    existing_obs.source_urls.append(src)
            if source_type:
                existing_obs.context["source_type"] = source_type
            self._store._save()
            return Rule(
                id=existing_obs.id,
                domain=existing_obs.domain,
                rule_type=existing_obs.category,
                rule=existing_obs.content,
                example=existing_obs.context.get("example", ""),
                confidence=existing_obs.confidence,
                times_confirmed=existing_obs.times_confirmed,
                times_violated=existing_obs.times_violated,
                sources=list(existing_obs.source_urls),
                source_type=existing_obs.context.get("source_type", ""),
                created_at=existing_obs.created_at,
                updated_at=existing_obs.updated_at,
            )

        # New rule — create Observation manually with legacy ID
        obs = Observation(
            id=rule_id,
            observation_type="rule",
            domain=domain,
            category=rule_type,
            content=rule,
            context={
                "example": example,
                "source_type": source_type,
            },
            confidence=confidence,
            times_confirmed=1,
            source_urls=list(source_list),
            created_at=now,
            updated_at=now,
        )
        self._store.observations[rule_id] = obs
        self._store._save()

        return Rule(
            id=obs.id,
            domain=obs.domain,
            rule_type=obs.category,
            rule=obs.content,
            example=obs.context.get("example", ""),
            confidence=obs.confidence,
            times_confirmed=obs.times_confirmed,
            times_violated=obs.times_violated,
            sources=list(obs.source_urls),
            source_type=obs.context.get("source_type", ""),
            created_at=obs.created_at,
            updated_at=obs.updated_at,
        )

    def promote_rule(self, rule_id: str) -> Rule | None:
        obs = self._store.promote_observation(rule_id)
        return Rule.from_observation(obs) if obs else None

    def demote_rule(self, rule_id: str) -> Rule | None:
        obs = self._store.demote_observation(rule_id)
        return Rule.from_observation(obs) if obs else None

    def delete_rule(self, rule_id: str) -> bool:
        return self._store.delete_observation(rule_id)

    # ── queries (delegates) ──────────────────────────────────────────────

    def get_active_rules(self, min_confidence: int = 1) -> list[Rule]:
        return [
            Rule.from_observation(o)
            for o in self._store.get_active_observations(min_confidence)
        ]

    def get_rules_by_domain(
        self, domain: str, min_confidence: int = 1
    ) -> list[Rule]:
        return [
            Rule.from_observation(o)
            for o in self._store.get_by_domain(domain, min_confidence)
        ]

    def search_rules(
        self,
        query: str,
        domain: str | None = None,
        min_confidence: int = 1,
        limit: int | None = None,
        rule_type: str | None = None,
    ) -> list[Rule]:
        obs_list = self._store.search(
            query=query,
            domain=domain,
            min_confidence=min_confidence,
            limit=limit,
            category=rule_type,
        )
        # Also search sources/source_type for the old RuleStore contract
        if not obs_list:
            # Fallback: search across all observations matching source metadata
            obs_list = self._store.search(
                query="",
                domain=domain,
                min_confidence=min_confidence,
            )
            # Filter client-side for sources/source_type matches
            query_lower = query.lower()
            obs_list = [
                o for o in obs_list
                if query_lower in " ".join(o.source_urls).lower()
                or query_lower in o.context.get("source_type", "").lower()
            ][:limit] if limit else obs_list
        return [Rule.from_observation(o) for o in obs_list]

    def get_all_domain_stats(self) -> dict[str, dict]:
        """Return per-domain stats in the old format expected by callers."""
        stats: dict[str, dict] = {}
        for obs in self._store.observations.values():
            if obs.domain not in stats:
                stats[obs.domain] = {"total": 0, "by_type": {}, "avg_confidence": 0.0}
            s = stats[obs.domain]
            s["total"] += 1
            s["by_type"][obs.category] = s["by_type"].get(obs.category, 0) + 1
        for domain, s in stats.items():
            domain_obs = [
                o for o in self._store.observations.values() if o.domain == domain
            ]
            s["avg_confidence"] = (
                sum(o.confidence for o in domain_obs) / max(len(domain_obs), 1)
            )
        return stats

    def get_domain_stats(self, domain: str | None = None) -> dict:
        if domain:
            obs_list = [
                o for o in self._store.observations.values() if o.domain == domain
            ]
        else:
            obs_list = list(self._store.observations.values())

        total = len(obs_list)
        by_type: dict[str, int] = {}
        for o in obs_list:
            by_type[o.category] = by_type.get(o.category, 0) + 1

        return {
            "total": total,
            "by_type": by_type,
            "avg_confidence": sum(o.confidence for o in obs_list) / max(total, 1),
        }

    # ── internals (preserve for DecayManager compatibility) ──────────────

    def _load(self):
        self._store._load()

    def _save(self):
        self._store._save()

    def __len__(self) -> int:
        return len(self._store)

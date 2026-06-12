"""ObservationStore — persistent, searchable store of observations.

Supersedes ``RuleStore``.  Observations are the v2 knowledge unit; the store
auto-migrates from the old ``rules.json`` format on first load.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .observation import Observation, ObservationType, AccessScope

# ── file names ────────────────────────────────────────────────────────────────
OLD_RULES_FILE = "rules.json"
NEW_STORE_FILE = "store.json"
BACKUP_SUFFIX = ".bak"


class ObservationStore:
    """Persistent store of observations backed by ``.loom/store.json``.

    Mirrors ``RuleStore``'s API exactly so existing callers work unchanged, but
    operates on the richer ``Observation`` model.  On first load when
    ``rules.json`` still exists but ``store.json`` does not, the store
    auto-migrates: old data is written to ``store.json`` (v2) and
    ``rules.json`` is renamed to ``rules.json.bak``.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.observations: dict[str, Observation] = {}
        self._migrated = False
        if self.path.exists():
            self._load()
            return

        # Check for legacy rules.json in the same directory
        rules_path = self.path.parent / OLD_RULES_FILE
        if rules_path.exists():
            self._migrate(rules_path)
            self._save()  # migration always writes the new store.json
            return

        # Fresh store — create the backing file so tooling sees it exists
        self._save()

    # ── persistence ────────────────────────────────────────────────────────

    def _load(self):
        """Load observations from the JSON store file."""
        try:
            data = json.loads(self.path.read_text())
            for obs_dict in data.get("observations", []):
                obs = Observation.from_dict(obs_dict)
                self.observations[obs.id] = obs
        except (json.JSONDecodeError, KeyError):
            self.observations = {}

    def _save(self):
        """Persist observations to the JSON store file (v2 format)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 2,
            "observations": [o.to_dict() for o in self.observations.values()],
        }
        self.path.write_text(json.dumps(data, indent=2))

    def _migrate(self, rules_path: Path):
        """Migrate from legacy rules.json to store.json v2.

        Creates a ``rules.json.bak`` copy for safety, but leaves the original
        ``rules.json`` in place so existing tooling that reads it directly
        can still function while callers transition to ``ObservationStore``.
        """
        try:
            data = json.loads(rules_path.read_text())
            for rule_dict in data.get("rules", []):
                obs = Observation.from_dict(rule_dict)
                self.observations[obs.id] = obs
            # Write new store
            self._save()
            # Copy (don't move) to .bak — keep original for reference
            backup_path = rules_path.with_suffix(rules_path.suffix + BACKUP_SUFFIX)
            if not backup_path.exists():
                shutil.copy2(str(rules_path), str(backup_path))
            self._migrated = True
        except (json.JSONDecodeError, KeyError, OSError):
            self.observations = {}

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _make_id(
        domain: str,
        category: str,
        content: str,
        obs_type: ObservationType = "rule",
    ) -> str:
        """Build a deterministic, human-readable observation ID."""
        slug = re.sub(r"[^a-z0-9]+", "-", content.lower().strip())[:60].strip("-")
        return f"{domain}::{obs_type}::{category}::{slug}"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _sort_key(obs: Observation):
        """Sort by (confidence desc, times_confirmed desc)."""
        return (obs.confidence, obs.times_confirmed)

    # ── CRUD ───────────────────────────────────────────────────────────────

    def get(self, observation_id: str) -> Observation | None:
        """Return an observation by ID."""
        return self.observations.get(observation_id)

    # Long-form alias for clarity
    get_observation = get

    def add_observation(
        self,
        domain: str,
        category: str,
        content: str,
        observation_type: ObservationType = "rule",
        context: dict[str, Any] | None = None,
        confidence: int = 5,
        source_url: str = "",
        source_agent: str = "",
        source_session: str = "",
        tags: list[str] | None = None,
        access_scope: AccessScope = "team",
    ) -> Observation:
        """Add an observation (or bump confidence if it already exists)."""
        obs_id = self._make_id(domain, category, content, observation_type)
        now = self._now()

        if obs_id in self.observations:
            existing = self.observations[obs_id]
            existing.confidence = min(10, existing.confidence + 1)
            existing.times_confirmed += 1
            existing.updated_at = now
            if source_url and source_url not in existing.source_urls:
                existing.source_urls.append(source_url)
            if source_agent:
                existing.source_agent = source_agent
            if source_session:
                existing.source_session = source_session
            self._save()
            return existing

        new_obs = Observation(
            id=obs_id,
            observation_type=observation_type,
            domain=domain,
            category=category,
            content=content,
            context=context or {},
            confidence=confidence,
            times_confirmed=1,
            source_urls=[source_url] if source_url else [],
            source_agent=source_agent,
            source_session=source_session,
            tags=tags or [],
            access_scope=access_scope,
            created_at=now,
            updated_at=now,
        )
        self.observations[new_obs.id] = new_obs
        self._save()
        return new_obs

    def promote(self, observation_id: str) -> Observation | None:
        """Increase confidence (confirm) on an observation."""
        obs = self.observations.get(observation_id)
        if obs:
            obs.confidence = min(10, obs.confidence + 1)
            obs.times_confirmed += 1
            obs.updated_at = self._now()
            self._save()
        return obs

    # Long-form alias
    promote_observation = promote

    def demote(self, observation_id: str) -> Observation | None:
        """Decrease confidence (violation) on an observation."""
        obs = self.observations.get(observation_id)
        if obs:
            obs.confidence = max(1, obs.confidence - 1)
            obs.times_violated += 1
            obs.updated_at = self._now()
            self._save()
        return obs

    # Long-form alias
    demote_observation = demote

    def delete(self, observation_id: str) -> bool:
        """Delete an observation by ID. Returns True if it existed."""
        if observation_id in self.observations:
            del self.observations[observation_id]
            self._save()
            return True
        return False

    # Long-form alias
    delete_observation = delete

    # ── embedding support ─────────────────────────────────────────────────

    def store_embedding(self, observation_id: str, vector: list[float]) -> bool:
        """Attach an embedding vector to an observation (in-memory only).

        Embeddings are **not** persisted to JSON — they are held in-process
        and must be re-generated when the store is reloaded.

        Returns *True* if the observation was found, *False* otherwise.
        """
        obs = self.observations.get(observation_id)
        if obs is None:
            return False
        obs.embedding = vector
        return True

    # ── queries ────────────────────────────────────────────────────────────

    def get_active(
        self, min_confidence: int = 1
    ) -> list[Observation]:
        """Return all observations at or above *min_confidence*."""
        results = [
            o for o in self.observations.values() if o.confidence >= min_confidence
        ]
        results.sort(key=self._sort_key, reverse=True)
        return results

    # Long-form alias
    get_active_observations = get_active

    def get_by_domain(
        self, domain: str, min_confidence: int = 1
    ) -> list[Observation]:
        """Return observations for a single domain."""
        results = [
            o
            for o in self.observations.values()
            if o.domain == domain and o.confidence >= min_confidence
        ]
        results.sort(key=self._sort_key, reverse=True)
        return results

    def search(
        self,
        query: str = "",
        domain: str | None = None,
        category: str | None = None,
        observation_type: ObservationType | None = None,
        min_confidence: int = 1,
        limit: int | None = None,
        tags: list[str] | None = None,
        access_scope: AccessScope | None = None,
    ) -> list[Observation]:
        """Full-text search across observations.

        Parameters
        ----------
        query:
            Substring match against content, category, domain, or ID.
        domain:
            Optional domain filter.
        category:
            Optional category filter (exact match).
        observation_type:
            Optional observation type filter.
        min_confidence:
            Minimum confidence threshold (inclusive).
        limit:
            Cap the number of results.
        tags:
            If given, only return observations that have **all** of these tags.
        access_scope:
            If given, only return observations matching this scope.

        Results are always sorted by ``(confidence desc, times_confirmed desc)``.
        """
        query_lower = query.lower() if query else ""
        results: list[Observation] = []

        for obs in self.observations.values():
            if obs.confidence < min_confidence:
                continue
            if domain and obs.domain != domain:
                continue
            if category and obs.category != category:
                continue
            if observation_type and obs.observation_type != observation_type:
                continue
            if tags:
                obs_tag_set = set(obs.tags)
                if not obs_tag_set.issuperset(tags):
                    continue
            if access_scope and obs.access_scope != access_scope:
                continue
            if query_lower and not (
                query_lower in obs.content.lower()
                or query_lower in obs.category.lower()
                or query_lower in obs.id.lower()
                or query_lower in obs.domain.lower()
            ):
                continue
            results.append(obs)

        results.sort(key=self._sort_key, reverse=True)
        if limit:
            results = results[:limit]
        return results

    # ── stats ──────────────────────────────────────────────────────────────

    def get_stats(self, domain: str | None = None) -> dict[str, Any]:
        """Return statistics, optionally scoped to *domain*."""
        if domain:
            obs_list = [
                o for o in self.observations.values() if o.domain == domain
            ]
        else:
            obs_list = list(self.observations.values())

        total = len(obs_list)
        if total == 0:
            return {
                "total": 0,
                "by_type": {},
                "by_domain": {},
                "by_category": {},
                "avg_confidence": 0.0,
            }

        by_type: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        by_category: dict[str, int] = {}
        confidence_sum = 0

        for obs in obs_list:
            by_type[obs.observation_type] = by_type.get(obs.observation_type, 0) + 1
            by_domain[obs.domain] = by_domain.get(obs.domain, 0) + 1
            by_category[obs.category] = by_category.get(obs.category, 0) + 1
            confidence_sum += obs.confidence

        return {
            "total": total,
            "by_type": by_type,
            "by_domain": by_domain,
            "by_category": by_category,
            "avg_confidence": confidence_sum / total,
        }

    def get_all_domain_stats(self) -> dict[str, dict[str, Any]]:
        """Return per-domain statistics aggregation."""
        stats: dict[str, dict[str, Any]] = {}
        for obs in self.observations.values():
            if obs.domain not in stats:
                stats[obs.domain] = {"total": 0, "by_type": {}, "avg_confidence": 0.0}
            s = stats[obs.domain]
            s["total"] += 1
            s["by_type"][obs.category] = s["by_type"].get(obs.category, 0) + 1
        for domain, s in stats.items():
            domain_obs = [
                o for o in self.observations.values() if o.domain == domain
            ]
            s["avg_confidence"] = (
                sum(o.confidence for o in domain_obs) / max(len(domain_obs), 1)
            )
        return stats

    def __len__(self) -> int:
        return len(self.observations)

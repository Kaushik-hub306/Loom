"""JSONFileBackend — wraps ObservationStore for git-native / self-hosted mode.

This backend is single-org by design.  The ``org_id`` parameter is
accepted (to satisfy the ABC) but ignored — all observations live in
one flat file.

This is the **default** backend when no database is configured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.engine.observation import Observation
from loom.engine.observation_store import ObservationStore

from .backend import StorageBackend


class JSONFileBackend(StorageBackend):
    """File-based storage backend wrapping ``ObservationStore``.

    Ideal for single-user, self-hosted, or git-native deployments
    where a full database is unnecessary.

    Parameters
    ----------
    store_path:
        Path to the ``store.json`` file (or directory containing it).
        If a directory is given, ``store.json`` is appended automatically.
    """

    def __init__(self, store_path: Path | str):
        store_path = Path(store_path)
        if store_path.is_dir():
            store_path = store_path / "store.json"
        self._store = ObservationStore(store_path)

    # ── CRUD ─────────────────────────────────────────────────────────────

    def add_observation(self, data: dict[str, Any], org_id: str = "default") -> Observation:
        """Create (or bump) an observation.

        Maps the generic *data* dict to ``ObservationStore.add_observation``
        positional and keyword arguments.
        """
        return self._store.add_observation(
            domain=data.get("domain", "general"),
            category=data.get("category", "general"),
            content=data.get("content", ""),
            observation_type=data.get("observation_type", "rule"),
            context=data.get("context"),
            confidence=data.get("confidence", 5),
            source_url=data.get("source_url", ""),
            source_agent=data.get("source_agent", ""),
            source_session=data.get("source_session", ""),
            tags=data.get("tags"),
            access_scope=data.get("access_scope", "team"),
        )

    def get_observations(
        self,
        filters: dict[str, Any] | None = None,
        org_id: str = "default",
    ) -> list[Observation]:
        """Return observations matching *filters*."""
        filters = filters or {}
        min_confidence = filters.get("min_confidence", 1)
        limit = filters.get("limit")
        offset = filters.get("offset", 0)

        results = self._store.search(
            query=filters.get("query", ""),
            domain=filters.get("domain"),
            category=filters.get("category"),
            observation_type=filters.get("observation_type"),
            min_confidence=min_confidence,
            tags=filters.get("tags"),
            access_scope=filters.get("access_scope"),
        )

        if offset:
            results = results[offset:]
        if limit:
            results = results[:limit]
        return results

    def update_observation(
        self,
        observation_id: str,
        data: dict[str, Any],
        org_id: str = "default",
    ) -> Observation | None:
        """Update mutable fields on an observation.

        Supports partial updates: only fields present in *data* are changed.
        Returns *None* when the observation does not exist.
        """
        obs = self._store.get_observation(observation_id)
        if obs is None:
            return None

        # Mutable fields we allow updating via the API
        _update_if_present(obs, data, "content")
        _update_if_present(obs, data, "category")
        _update_if_present(obs, data, "domain")
        _update_if_present(obs, data, "observation_type")
        _update_if_present(obs, data, "confidence")
        _update_if_present(obs, data, "context")
        _update_if_present(obs, data, "tags")
        _update_if_present(obs, data, "access_scope")
        _update_if_present(obs, data, "source_urls")

        obs.updated_at = self._store._now()
        self._store._save()
        return obs

    def delete_observation(
        self,
        observation_id: str,
        org_id: str = "default",
    ) -> bool:
        """Delete an observation by ID."""
        return self._store.delete_observation(observation_id)

    def search(
        self,
        query: str,
        org_id: str = "default",
        **kwargs: Any,
    ) -> list[Observation]:
        """Keyword search with optional filters."""
        return self._store.search(
            query=query,
            domain=kwargs.get("domain"),
            category=kwargs.get("category"),
            observation_type=kwargs.get("observation_type"),
            min_confidence=kwargs.get("min_confidence", 1),
            limit=kwargs.get("limit"),
            tags=kwargs.get("tags"),
            access_scope=kwargs.get("access_scope"),
        )

    def get_stats(
        self,
        org_id: str = "default",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return aggregate statistics."""
        return self._store.get_stats(domain=kwargs.get("domain"))


# ── helpers ────────────────────────────────────────────────────────────────


def _update_if_present(obj: Any, data: dict[str, Any], key: str) -> None:
    """Set *obj.key = data[key]* only when *key* is present in *data*."""
    if key in data:
        setattr(obj, key, data[key])

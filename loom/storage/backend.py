"""Abstract base class for storage backends.

Each backend provides the same CRUD + search + stats interface.
Org isolation is handled transparently — callers always pass an
``org_id`` and each backend enforces scope however it needs to.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from loom.engine.observation import Observation


class StorageBackend(ABC):
    """Abstract base for observation storage backends.

    All methods accept an ``org_id`` parameter for multi-org isolation.
    Backends that don't support multi-tenancy (e.g. JSONFileBackend)
    ignore the parameter and treat all data as belonging to a single org.
    """

    @abstractmethod
    def add_observation(self, data: dict[str, Any], org_id: str = "default") -> Observation:
        """Create (or bump) an observation and return it.

        Parameters
        ----------
        data:
            Dict with keys matching Observation fields (domain, category,
            content, observation_type, confidence, source_url, etc.).
        org_id:
            Organisation identifier for isolation.
        """
        ...

    @abstractmethod
    def get_observations(
        self,
        filters: dict[str, Any] | None = None,
        org_id: str = "default",
    ) -> list[Observation]:
        """Return observations matching the given filters.

        Parameters
        ----------
        filters:
            Dict with optional keys: domain, category, observation_type,
            min_confidence, tags, access_scope, limit, offset.
        org_id:
            Organisation identifier for isolation.
        """
        ...

    @abstractmethod
    def update_observation(
        self,
        observation_id: str,
        data: dict[str, Any],
        org_id: str = "default",
    ) -> Observation | None:
        """Update an existing observation's mutable fields.

        Returns the updated observation, or *None* if not found.
        """
        ...

    @abstractmethod
    def delete_observation(
        self,
        observation_id: str,
        org_id: str = "default",
    ) -> bool:
        """Delete an observation by ID. Returns *True* if it existed."""
        ...

    @abstractmethod
    def search(
        self,
        query: str,
        org_id: str = "default",
        **kwargs: Any,
    ) -> list[Observation]:
        """Keyword + optional semantic search across observations.

        Parameters
        ----------
        query:
            Free-text search string.
        org_id:
            Organisation identifier for isolation.
        **kwargs:
            Additional filters: domain, observation_type, tags,
            min_confidence, limit.
        """
        ...

    @abstractmethod
    def get_stats(
        self,
        org_id: str = "default",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return aggregate statistics for the given org.

        Parameters
        ----------
        org_id:
            Organisation identifier for isolation.
        **kwargs:
            Optional filters: domain.
        """
        ...

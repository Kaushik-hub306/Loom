"""SourceTracker — records provenance for observations.

Tracks *which agent* recorded *what* observation, from *which session*, and
from *which URL(s)*.  This gives every piece of knowledge in the store a
complete audit trail.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


class SourceTracker:
    """Manages provenance tracking for observations.

    Each instance auto-generates a unique session ID on construction.  Call
    ``record_source()`` to log provenance for an observation and
    ``get_sources()`` to retrieve the audit trail.
    """

    def __init__(self):
        self._records: dict[str, list[dict[str, Any]]] = {}
        self.current_session_id = self.generate_session_id()

    # ------------------------------------------------------------------
    # IDs
    # ------------------------------------------------------------------

    @staticmethod
    def generate_session_id() -> str:
        """Generate a unique session identifier.

        Sessions are scoped to a single agent invocation.  The ID prefix
        ``sess_`` makes it recognisable in logs and metadata.
        """
        return f"sess_{uuid.uuid4().hex[:12]}"

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record_source(
        self,
        observation_id: str,
        agent: str = "",
        session: str = "",
        source_url: str = "",
    ) -> dict[str, Any]:
        """Record provenance for *observation_id*.

        Multiple calls for the same observation accumulate as a list (e.g. the
        same fact observed from several independent sources).

        Returns the recorded entry as a dict.
        """
        entry: dict[str, Any] = {
            "observation_id": observation_id,
            "agent": agent,
            "session": session if session else self.current_session_id,
            "source_url": source_url,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._records.setdefault(observation_id, []).append(entry)
        return entry

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_sources(self, observation_id: str) -> list[dict[str, Any]]:
        """Return all provenance records for a given observation."""
        return self._records.get(observation_id, [])

    def get_agent_observations(self, agent: str) -> list[str]:
        """Return all observation IDs recorded by *agent*."""
        ids: set[str] = set()
        for obs_id, records in self._records.items():
            if any(r["agent"] == agent for r in records):
                ids.add(obs_id)
        return sorted(ids)

    def get_session_observations(self, session: str) -> list[str]:
        """Return all observation IDs recorded during *session*."""
        ids: set[str] = set()
        for obs_id, records in self._records.items():
            if any(r["session"] == session for r in records):
                ids.add(obs_id)
        return sorted(ids)

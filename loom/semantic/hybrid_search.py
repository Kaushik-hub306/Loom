"""HybridSearch — combine semantic (vector) and keyword search results.

Merges results from ``ObservationStore.search`` (keyword) and
``VectorStore.search`` (semantic) with weighted scoring, deduplication, and
optional filters.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from loom.engine.observation_store import ObservationStore
    from loom.engine.observation import ObservationType
    from loom.semantic.embedding_provider import EmbeddingProvider
    from loom.semantic.vector_store import VectorStore


# ── scoring weights ─────────────────────────────────────────────────────────
# Semantic similarity usually provides the strongest signal, with confidence
# and recency acting as tie-breakers.
_SEMANTIC_WEIGHT = 0.5
_CONFIDENCE_WEIGHT = 0.3
_RECENCY_WEIGHT = 0.2


class HybridSearch:
    """Combine semantic (vector) and keyword search with weighted scoring.

    Parameters
    ----------
    store:
        The ``ObservationStore`` for keyword search.
    vector_store:
        Optional ``VectorStore`` for semantic search.  If *None*, only
        keyword results are returned.
    embedding_provider:
        Optional ``EmbeddingProvider``.  Required when ``vector_store`` is
        provided (used to embed the query string).
    """

    def __init__(
        self,
        store: ObservationStore,
        vector_store: VectorStore | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self._store = store
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider

    # ── public API ───────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        domain: str | None = None,
        min_confidence: int = 1,
        limit: int | None = None,
        observation_type: ObservationType | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search across keyword and semantic indexes, returning scored results.

        Each result dict contains:

        - ``id``, ``content``, ``category``, ``domain``, ``confidence``,
          ``observation_type``, ``tags``, ``access_scope`` — from the
          Observation
        - ``score`` — the combined weighted score (0.0–1.0)

        Parameters
        ----------
        query:
            Search query string.
        domain:
            Optional domain filter.
        min_confidence:
            Minimum confidence threshold (inclusive).
        limit:
            Cap the number of returned results.
        observation_type:
            Optional observation type filter.
        tags:
            Optional tag filter (AND logic — all tags must match).

        Returns
        -------
        List of result dicts sorted by combined score (descending).
        """
        results_by_id: dict[str, dict[str, Any]] = {}

        # ── keyword search ────────────────────────────────────────────
        keyword_obs = self._store.search(
            query=query,
            domain=domain,
            observation_type=observation_type,
            min_confidence=min_confidence,
            tags=tags,
        )

        for obs in keyword_obs:
            results_by_id[obs.id] = {
                "id": obs.id,
                "content": obs.content,
                "category": obs.category,
                "domain": obs.domain,
                "confidence": obs.confidence,
                "observation_type": obs.observation_type,
                "tags": list(obs.tags),
                "access_scope": obs.access_scope,
                "created_at": obs.created_at,
                "updated_at": obs.updated_at,
                "times_confirmed": obs.times_confirmed,
                # Partial scores — semantic portion filled in below
                "score": self._compute_confidence_component(obs.confidence),
                "_semantic_score": 0.0,
            }

        # ── semantic search ───────────────────────────────────────────
        if (
            self._vector_store is not None
            and self._embedding_provider is not None
        ):
            query_vec = self._embedding_provider.embed(query)
            semantic_hits = self._vector_store.search(query_vec, k=len(self._vector_store))

            for obs_id, similarity in semantic_hits:
                obs = self._store.get(obs_id)
                if obs is None:
                    continue
                # Apply filters again (vector store doesn't track metadata)
                if domain and obs.domain != domain:
                    continue
                if observation_type and obs.observation_type != observation_type:
                    continue
                if min_confidence and obs.confidence < min_confidence:
                    continue
                if tags:
                    obs_tag_set = set(obs.tags)
                    if not obs_tag_set.issuperset(tags):
                        continue

                if obs_id in results_by_id:
                    # Merge: add semantic score to existing entry
                    results_by_id[obs_id]["_semantic_score"] = similarity
                    # Recompute combined score
                    results_by_id[obs_id]["score"] = self._compute_combined_score(
                        results_by_id[obs_id]
                    )
                else:
                    results_by_id[obs_id] = {
                        "id": obs.id,
                        "content": obs.content,
                        "category": obs.category,
                        "domain": obs.domain,
                        "confidence": obs.confidence,
                        "observation_type": obs.observation_type,
                        "tags": list(obs.tags),
                        "access_scope": obs.access_scope,
                        "created_at": obs.created_at,
                        "updated_at": obs.updated_at,
                        "times_confirmed": obs.times_confirmed,
                        "_semantic_score": similarity,
                        "score": self._compute_combined_score_no_keyword(
                            similarity, obs.confidence
                        ),
                    }

        # ── build sorted result list ───────────────────────────────────
        results = list(results_by_id.values())
        results.sort(key=lambda r: r["score"], reverse=True)

        # Clean up internal fields
        for r in results:
            r.pop("_semantic_score", None)

        if limit:
            results = results[:limit]
        return results

    # ── scoring helpers ─────────────────────────────────────────────────

    @staticmethod
    def _compute_confidence_component(confidence: int) -> float:
        """Normalise confidence to a 0–1 scale."""
        return confidence / 10.0

    @staticmethod
    def _compute_recency_component(created_at: str) -> float:
        """Compute a recency score (0.0–1.0) from an ISO-8601 timestamp string.

        Older observations get lower scores.  This is a soft decay — the score
        drops by 0.1 per year of age, bottoming at 0.0.
        """
        if not created_at:
            return 0.5  # neutral for observations without timestamps
        try:
            from datetime import datetime, timezone

            dt = datetime.fromisoformat(created_at)
            now = datetime.now(timezone.utc)
            # Make naive datetimes timezone-aware for comparison
            if dt.tzinfo is None:
                from datetime import timezone as tz
                dt = dt.replace(tzinfo=tz.utc)
            age_days = (now - dt).days
            age_years = age_days / 365.25
            # Linear decay: 1.0 at age 0, 0.0 at age 10+ years
            return max(0.0, 1.0 - 0.1 * age_years)
        except (ValueError, TypeError):
            return 0.5

    @classmethod
    def _compute_combined_score(cls, entry: dict[str, Any]) -> float:
        """Compute weighted score for an entry that has both keyword and semantic hits."""
        c_conf = cls._compute_confidence_component(entry["confidence"])
        c_rec = cls._compute_recency_component(entry.get("created_at", ""))
        return (
            _SEMANTIC_WEIGHT * entry.get("_semantic_score", 0.0)
            + _CONFIDENCE_WEIGHT * c_conf
            + _RECENCY_WEIGHT * c_rec
        )

    @classmethod
    def _compute_combined_score_no_keyword(
        cls, similarity: float, confidence: int
    ) -> float:
        """Compute combined score for a semantic-only hit (no keyword match)."""
        c_conf = cls._compute_confidence_component(confidence)
        return (
            _SEMANTIC_WEIGHT * similarity
            + _CONFIDENCE_WEIGHT * c_conf
            + _RECENCY_WEIGHT * 0.5  # neutral recency
        )

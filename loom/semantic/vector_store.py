"""VectorStore — in-process vector storage with cosine-similarity search.

A lightweight, pure-Python store for dense embedding vectors.  No external
dependencies beyond the standard library.  Cosine similarity is computed with
``math.sqrt`` and generator expressions.
"""

from __future__ import annotations

import math
from typing import ItemsView


class VectorStore:
    """In-process storage for embedding vectors with cosine-similarity search.

    Thread-safe for concurrent reads; writes (``add``, ``remove``, ``clear``)
    should be serialised externally if needed.

    Examples
    --------
    >>> vs = VectorStore()
    >>> vs.add("doc-1", [1.0, 0.0, 0.0])
    >>> vs.add("doc-2", [0.0, 1.0, 0.0])
    >>> results = vs.search([1.0, 0.0, 0.0], k=1)
    >>> results[0]
    ('doc-1', 1.0)
    """

    def __init__(self):
        self._vectors: dict[str, list[float]] = {}
        # Pre-computed norms for faster similarity computation
        self._norms: dict[str, float] = {}

    # ── CRUD ────────────────────────────────────────────────────────────

    def add(self, id: str, vector: list[float]) -> None:
        """Store an embedding vector under *id*.

        Overwrites any existing vector for the same *id*.
        """
        norm = math.sqrt(sum(v * v for v in vector))
        self._vectors[id] = list(vector)
        self._norms[id] = norm

    def remove(self, id: str) -> None:
        """Remove the vector stored under *id* (no-op if absent)."""
        self._vectors.pop(id, None)
        self._norms.pop(id, None)

    def clear(self) -> None:
        """Remove all stored vectors."""
        self._vectors.clear()
        self._norms.clear()

    # ── search ───────────────────────────────────────────────────────────

    def search(self, vector: list[float], k: int = 10) -> list[tuple[str, float]]:
        """Return the top-*k* results sorted by cosine similarity (descending).

        Parameters
        ----------
        vector:
            Query vector.
        k:
            Maximum number of results to return.

        Returns
        -------
        list of ``(id, similarity_score)`` tuples, sorted highest-first.
        Similarity scores range from -1.0 to 1.0 (in practice 0.0-1.0 for
        common embedding models).
        """
        query_norm = math.sqrt(sum(v * v for v in vector))
        if query_norm == 0.0:
            return []

        scores: list[tuple[str, float]] = []
        for doc_id, doc_vec in self._vectors.items():
            doc_norm = self._norms.get(doc_id, 0.0)
            if doc_norm == 0.0:
                score = 0.0
            else:
                dot = sum(q * d for q, d in zip(vector, doc_vec))
                score = dot / (query_norm * doc_norm)
            scores.append((doc_id, score))

        # Sort descending by score, take top-k
        scores.sort(key=lambda pair: pair[1], reverse=True)
        return scores[:k]

    # ── info ─────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        """Return the number of stored vectors."""
        return len(self._vectors)

    def __contains__(self, id: str) -> bool:
        """Return True if *id* is present."""
        return id in self._vectors

    def get(self, id: str) -> list[float] | None:
        """Return the stored vector for *id*, or *None*."""
        return self._vectors.get(id)

    def items(self) -> ItemsView[str, list[float]]:
        """Iterate over ``(id, vector)`` pairs (for debugging)."""
        return self._vectors.items()

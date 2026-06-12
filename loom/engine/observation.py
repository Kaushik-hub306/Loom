"""Observation — generalized dataclass replacing Rule with richer provenance and taxonomy.

Observations are the central unit of knowledge in Loom.  They subsume the old
"Rule" concept while adding support for facts, decisions, context, and technique
observations — each with access-scoping, tagging, and provenance tracking.

Observations have a fixed lifecycle:
- created → confirmed (times_confirmed > 0)
- confirmed multiple times → confidence rises toward 10
- violated → confidence falls toward 1
- confidence reaches 0 → may be pruned (tombstoned)
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ObservationType = Literal["rule", "fact", "decision", "context", "technique"]
AccessScope = Literal["public", "team", "org", "private"]


@dataclass
class Observation:
    """A single observation — rule, fact, decision, context, or technique."""

    id: str
    observation_type: ObservationType
    domain: str
    category: str
    content: str
    context: dict[str, Any] = field(default_factory=dict)
    confidence: int = 5
    times_confirmed: int = 0
    times_violated: int = 0
    source_urls: list[str] = field(default_factory=list)
    source_agent: str = ""
    source_session: str = ""
    tags: list[str] = field(default_factory=list)
    access_scope: AccessScope = "team"
    created_at: str = ""
    updated_at: str = ""
    embedding: list[float] | None = None

    def __post_init__(self):
        """Deep-copy mutable defaults so instances don't share state."""
        self.context = copy.deepcopy(self.context) if self.context else {}
        self.source_urls = copy.deepcopy(self.source_urls) if self.source_urls else []
        self.tags = copy.deepcopy(self.tags) if self.tags else []

    def to_dict(self, include_embedding: bool = False) -> dict[str, Any]:
        """Serialize to a plain dict for JSON persistence.

        Parameters
        ----------
        include_embedding:
            If *True*, include the ``embedding`` vector in the output.
            Defaults to *False* because embedding vectors are large and
            in-memory only — they are not persisted to JSON.
        """
        result: dict[str, Any] = {
            "id": self.id,
            "observation_type": self.observation_type,
            "domain": self.domain,
            "category": self.category,
            "content": self.content,
            "context": self.context,
            "confidence": self.confidence,
            "times_confirmed": self.times_confirmed,
            "times_violated": self.times_violated,
            "source_urls": self.source_urls,
            "source_agent": self.source_agent,
            "source_session": self.source_session,
            "tags": self.tags,
            "access_scope": self.access_scope,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_embedding and self.embedding is not None:
            result["embedding"] = self.embedding
        return result

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Observation":
        """Deserialize from a plain dict, with backward compat for old Rule format.

        Supports three input shapes:

        1.  New Observation format (store.json v2)::

            {"observation_type": "rule", "category": "type_safety", "content": "…"}

        2.  Old Rule format (rules.json v1)::

            {"rule_type": "type_safety", "rule": "…"}

        3.  Oldest format that used ``"pattern"`` instead of ``"rule"``.
        """
        embedding = d.get("embedding")  # optional in-memory only

        # ---- version-detect: old Rule uses "rule_type" / "rule" ----
        if "rule_type" in d:
            return cls(
                id=d.get("id", str(uuid.uuid4())),
                observation_type="rule",
                domain=d.get("domain", "general"),
                category=d.get("rule_type", d.get("category", "general")),
                content=d.get("rule", d.get("pattern", d.get("content", ""))),
                context=d.get("context", {}),
                confidence=d.get("confidence", 5),
                times_confirmed=d.get("times_confirmed", 0),
                times_violated=d.get("times_violated", 0),
                source_urls=d.get("source_urls", []),
                source_agent=d.get("source_agent", ""),
                source_session=d.get("source_session", ""),
                tags=d.get("tags", []),
                access_scope=d.get("access_scope", "team"),
                created_at=d.get("created_at", ""),
                updated_at=d.get("updated_at", ""),
                embedding=embedding,
            )

        # ---- current Observation format ----
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            observation_type=d.get("observation_type", "rule"),
            domain=d.get("domain", "general"),
            category=d.get("category", "general"),
            content=d.get("content", ""),
            context=d.get("context", {}),
            confidence=d.get("confidence", 5),
            times_confirmed=d.get("times_confirmed", 0),
            times_violated=d.get("times_violated", 0),
            source_urls=d.get("source_urls", []),
            source_agent=d.get("source_agent", ""),
            source_session=d.get("source_session", ""),
            tags=d.get("tags", []),
            access_scope=d.get("access_scope", "team"),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            embedding=embedding,
        )

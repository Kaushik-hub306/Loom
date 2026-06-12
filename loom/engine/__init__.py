"""Loom engine — ObservationStore, CategoryRegistry, SourceTracker,
KnowledgeGraph, GraphStore, DecayManager, LLMExtractor.

Loom v2 adds the generalized ``Observation`` model alongside the new
``ObservationStore``, ``CategoryRegistry``, ``SourceTracker``,
``KnowledgeGraph``, and ``GraphStore``.  The older ``Rule`` / ``RuleStore`` are
kept as deprecated aliases for backward compatibility.
"""

# New (v2) public API
from .observation import Observation
from .observation_store import ObservationStore
from .category_registry import CategoryRegistry
from .source_tracker import SourceTracker
from .knowledge_graph import KnowledgeGraph
from .graph_store import GraphStore

# Legacy (deprecated) — kept for backward compat
from .rule_store import RuleStore, Rule
from .domain_extractor import DomainExtractor
from .decay_manager import DecayManager
from .llm_extractor import LLMExtractor, ExtractedRule

__all__ = [
    # v2
    "Observation",
    "ObservationStore",
    "CategoryRegistry",
    "SourceTracker",
    "KnowledgeGraph",
    "GraphStore",
    # legacy (deprecated)
    "Rule",
    "RuleStore",
    # existing
    "DomainExtractor",
    "DecayManager",
    "LLMExtractor",
    "ExtractedRule",
]

"""Loom semantic engine — LLM-powered observation extraction and vector search.

Provides optional semantic capabilities that layer on top of the keyword-based
observation engine.  Everything works without API keys (keyword + bag-of-words
fallback); importing optional packages (sentence-transformers, openai) unlocks
higher-quality embeddings.
"""

from __future__ import annotations

from .embedding_provider import (
    EmbeddingProvider,
    KeywordFallbackProvider,
    SentenceTransformersProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)
from .llm_extractor import LLMExtractor
from .vector_store import VectorStore
from .hybrid_search import HybridSearch

__all__ = [
    "EmbeddingProvider",
    "KeywordFallbackProvider",
    "SentenceTransformersProvider",
    "OpenAIEmbeddingProvider",
    "get_embedding_provider",
    "LLMExtractor",
    "VectorStore",
    "HybridSearch",
]

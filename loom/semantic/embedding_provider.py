"""Embedding providers — convert text to dense vector representations.

All providers implement the ``EmbeddingProvider`` abstract base class.  The
factory function ``get_embedding_provider`` selects the best available
implementation, falling back to bag-of-words keyword vectors when no optional
package is installed.

Available providers
-------------------
- ``KeywordFallbackProvider`` — always-available bag-of-words vectors
- ``SentenceTransformersProvider`` — local sentence-transformers (no API key)
- ``OpenAIEmbeddingProvider`` — OpenAI embeddings API
"""

from __future__ import annotations

import math
import os
import warnings
from abc import ABC, abstractmethod
from typing import Sequence


# ── Shared vocabulary used by KeywordFallbackProvider ───────────────────────
# These are common technical terms across programming languages and domains.
# The vocabulary is deliberately small (150 terms) so vectors are compact.
_VOCABULARY: list[str] = [
    # -- general coding --
    "type", "safety", "hints", "annotation", "check", "infer", "cast", "alias",
    "union", "optional", "generic", "protocol", "interface", "abstract",
    "function", "method", "class", "module", "package", "import", "export",
    "variable", "constant", "immutable", "mutable", "instance", "static",
    "error", "exception", "handle", "catch", "raise", "throw", "panic",
    "test", "assert", "mock", "stub", "fixture", "coverage", "benchmark",
    "pattern", "match", "regex", "parse", "tokenize", "compile", "link",
    "build", "deploy", "ci", "cd", "pipeline", "artifact", "release",
    "version", "dependency", "lock", "resolve", "conflict", "compatible",
    "lint", "format", "style", "convention", "idiom", "standard", "guide",
    "document", "comment", "docstring", "readme", "changelog", "api",
    "rest", "graphql", "grpc", "websocket", "http", "route", "endpoint",
    "middleware", "auth", "token", "session", "cookie", "jwt", "oauth",
    "database", "query", "index", "migrate", "seed", "backup", "restore",
    "schema", "table", "column", "row", "join", "transaction", "lock",
    "cache", "invalidate", "evict", "prefix", "key", "expire", "redis",
    "queue", "message", "broker", "publish", "subscribe", "consumer",
    "producer", "topic", "partition", "offset", "commit", "rebalance",
    "log", "monitor", "trace", "span", "metric", "alert", "dashboard",
    "container", "image", "orchestrate", "scale", "service", "cluster",
    "node", "pod", "helm", "terraform", "provision", "configure",
    "security", "encrypt", "decrypt", "hash", "salt", "sign", "verify",
    "sanitize", "escape", "validate", "permission", "role", "policy",
    "async", "await", "promise", "callback", "event", "stream", "batch",
    "python", "javascript", "typescript", "rust", "go", "ruby",
    "react", "vue", "angular", "django", "flask", "fastapi", "next",
    "sql", "nosql", "postgres", "mysql", "sqlite", "mongo",
]

# Build an efficient lookup: term → index in vocabulary
_VOCAB_INDEX: dict[str, int] = {word: i for i, word in enumerate(_VOCABULARY)}
_VOCAB_SIZE: int = len(_VOCABULARY)


# ── Abstract base ───────────────────────────────────────────────────────────

class EmbeddingProvider(ABC):
    """Abstract base for embedding providers.

    Subclasses must implement at least ``embed``.  ``embed_batch`` has a
    default implementation that calls ``embed`` in a loop; providers may
    override it for batch efficiency.
    """

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return an embedding vector for *text*."""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for multiple texts."""
        return [self.embed(t) for t in texts]


# ── Keyword (bag-of-words) fallback ─────────────────────────────────────────

class KeywordFallbackProvider(EmbeddingProvider):
    """Bag-of-words embedding using a fixed technical vocabulary.

    No external dependencies, always available.  Each embedding dimension
    corresponds to a term in the shared vocabulary; the value is 1.0 if the
    term appears (as a whole word) in the input text, otherwise 0.0.

    The resulting vectors are sparse binary vectors in a compact list-of-floats
    representation.  They work surprisingly well for domain-specific semantic
    search because the vocabulary is tuned for developer conversations.
    """

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Extract lowercase alphanumeric tokens from *text*."""
        # Split on non-alphanumeric boundaries, keep only alpha tokens
        parts = text.lower().split()
        tokens: set[str] = set()
        for part in parts:
            # Strip leading/trailing punctuation
            word = "".join(ch for ch in part if ch.isalpha())
            if word:
                tokens.add(word)
        return tokens

    def embed(self, text: str) -> list[float]:
        """Produce a bag-of-words vector for *text*."""
        tokens = self._tokenize(text)
        vector = [0.0] * _VOCAB_SIZE
        for token in tokens:
            idx = _VOCAB_INDEX.get(token)
            if idx is not None:
                vector[idx] = 1.0
        # L2-normalize so cosine similarity is comparable across documents
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Produce bag-of-words vectors for multiple texts."""
        return [self.embed(t) for t in texts]


# ── Sentence-Transformers provider ──────────────────────────────────────────

class SentenceTransformersProvider(EmbeddingProvider):
    """Local embeddings via sentence-transformers (no API key required).

    Uses the ``all-MiniLM-L6-v2`` model by default, which produces 384-
    dimensional embeddings and runs quickly on CPU.  Falls back to
    ``KeywordFallbackProvider`` at construction time if the package is
    not installed.
    """

    _DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: str | None = None, device: str | None = None):
        """Initialise the sentence-transformers provider.

        Parameters
        ----------
        model_name:
            HuggingFace model name.  Defaults to ``all-MiniLM-L6-v2``.
        device:
            Torch device string (``"cpu"``, ``"cuda"``, …).  Defaults to
            ``"cpu"`` for safe fallback.
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            warnings.warn(
                "sentence-transformers is not installed. "
                "Falling back to KeywordFallbackProvider."
            )
            self._fallback: KeywordFallbackProvider | None = KeywordFallbackProvider()
            self._model: object | None = None
            return

        self._fallback = None
        self._model_name = model_name or self._DEFAULT_MODEL
        self._device = device or "cpu"
        try:
            self._model = SentenceTransformer(self._model_name, device=self._device)
        except Exception as exc:
            warnings.warn(
                f"Failed to load sentence-transformers model '{self._model_name}': {exc}. "
                f"Falling back to KeywordFallbackProvider."
            )
            self._fallback = KeywordFallbackProvider()
            self._model = None

    @property
    def model_name(self) -> str:
        """Return the model name (or empty string when using fallback)."""
        if self._model is not None:
            return self._model_name
        return ""

    def embed(self, text: str) -> list[float]:
        """Produce an embedding for *text*."""
        if self._fallback is not None:
            return self._fallback.embed(text)
        from sentence_transformers import SentenceTransformer
        assert isinstance(self._model, SentenceTransformer)
        result = self._model.encode([text], show_progress_bar=False)
        # result is a numpy array; convert to list[float]
        return result[0].tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Produce embeddings for multiple texts in a single model pass."""
        if not texts:
            return []
        if self._fallback is not None:
            return self._fallback.embed_batch(texts)
        from sentence_transformers import SentenceTransformer
        assert isinstance(self._model, SentenceTransformer)
        result = self._model.encode(texts, show_progress_bar=False)
        return result.tolist()


# ── OpenAI embeddings provider ──────────────────────────────────────────────

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embeddings via the OpenAI API.

    Requires the ``OPENAI_API_KEY`` environment variable.  Uses
    ``text-embedding-3-small`` by default (1536 dimensions, $0.02 per 1M tokens).
    """

    _DEFAULT_MODEL = "text-embedding-3-small"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        org: str | None = None,
    ):
        """Initialise the OpenAI embedding provider.

        Parameters
        ----------
        api_key:
            OpenAI API key.  If *None*, reads from ``OPENAI_API_KEY`` env var.
        model:
            Embedding model name.  Defaults to ``text-embedding-3-small``.
        org:
            Optional OpenAI organisation ID.
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model or self._DEFAULT_MODEL
        self._org = org or os.environ.get("OPENAI_ORG_ID", "")

    @property
    def model(self) -> str:
        """Return the embedding model name."""
        return self._model

    def _is_available(self) -> bool:
        """Return True if the API key is configured."""
        return bool(self._api_key)

    def embed(self, text: str) -> list[float]:
        """Produce an embedding for *text* via the OpenAI API."""
        import json
        import urllib.request

        if not self._is_available():
            raise RuntimeError(
                "OPENAI_API_KEY is not set.  Set the environment variable "
                "or pass api_key= to OpenAIEmbeddingProvider()."
            )

        body = json.dumps({
            "input": text,
            "model": self._model,
        }).encode("utf-8")

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        if self._org:
            headers["OpenAI-Organization"] = self._org

        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"OpenAI embeddings API returned HTTP {exc.code}: {exc.reason}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Failed to call OpenAI embeddings API: {exc}"
            ) from exc

        # data["data"][0]["embedding"] is a list of floats
        return list(data["data"][0]["embedding"])

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Produce embeddings for multiple texts via the OpenAI API."""
        import json
        import urllib.request

        if not texts:
            return []

        if not self._is_available():
            raise RuntimeError(
                "OPENAI_API_KEY is not set.  Set the environment variable "
                "or pass api_key= to OpenAIEmbeddingProvider()."
            )

        body = json.dumps({
            "input": texts,
            "model": self._model,
        }).encode("utf-8")

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        if self._org:
            headers["OpenAI-Organization"] = self._org

        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"OpenAI embeddings API returned HTTP {exc.code}: {exc.reason}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Failed to call OpenAI embeddings API: {exc}"
            ) from exc

        # data["data"] is a list of {"embedding": [...], "index": N}
        embeddings: list[list[float]] = [list() for _ in texts]
        for item in data["data"]:
            embeddings[item["index"]] = list(item["embedding"])
        return embeddings


# ── Factory ─────────────────────────────────────────────────────────────────

def get_embedding_provider(provider: str = "auto") -> EmbeddingProvider:
    """Select the best available embedding provider.

    Parameters
    ----------
    provider:
        One of ``"auto"``, ``"keyword"``, ``"sentence-transformers"``,
        ``"openai"``, or ``"none"``.

        - ``"auto"`` — tries sentence-transformers, falls back to keyword
        - ``"none"`` / ``"keyword"`` — always KeywordFallbackProvider

    """
    provider = provider.lower()

    if provider in ("auto",):
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            return KeywordFallbackProvider()
        return SentenceTransformersProvider()

    if provider in ("sentence-transformers", "sentence_transformers"):
        return SentenceTransformersProvider()

    if provider in ("openai",):
        return OpenAIEmbeddingProvider()

    # "none", "keyword", or anything else
    return KeywordFallbackProvider()

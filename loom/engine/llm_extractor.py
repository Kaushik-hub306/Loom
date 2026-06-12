"""LLMExtractor — uses pluggable LLM providers for nuanced rule extraction.

Supports Anthropic, DeepSeek, and Gemini via the provider abstraction in
``loom.llm``.  When no provider is configured (no API key), falls back to
keyword-based extraction via ``DomainExtractor`` — the zero-cost default.
"""

from pathlib import Path
from typing import Any

from loom.llm.base import BaseLLMProvider, ExtractedRule
from loom.llm.factory import get_provider


class LLMExtractor:
    """Uses a pluggable LLM provider to extract convention rules from text.

    Parameters
    ----------
    provider:
        A :class:`BaseLLMProvider` instance.  When ``None`` (the default),
        the extractor auto-detects a provider from environment variables
        via :func:`loom.llm.factory.get_provider`.
    max_input_chars:
        Maximum characters of input text sent to the LLM.
    """

    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(
        self,
        provider: BaseLLMProvider | None = None,
        max_input_chars: int = 8000,
    ):
        self._provider = provider
        self.max_input_chars = max_input_chars

    @property
    def provider(self) -> BaseLLMProvider | None:
        """The active provider (lazy-loaded from env vars if not injected)."""
        if self._provider is None:
            self._provider = get_provider()
        return self._provider

    @property
    def is_available(self) -> bool:
        """True when a provider is configured and ready to use."""
        p = self.provider
        return p is not None and bool(p.api_key)

    @property
    def active_provider_name(self) -> str:
        """Human-readable name of the active provider, or 'none'."""
        p = self.provider
        return p.provider_name if p else "none"

    async def extract(
        self,
        text: str,
        domain: str = "general",
        domain_config: Any | None = None,
    ) -> list[ExtractedRule]:
        """Extract convention rules from *text* using the configured LLM provider.

        Returns an empty list when no provider is available or no rules
        are found — callers should fall back to keyword-based extraction.
        """
        p = self.provider
        if p is None:
            return []

        description = "General conventions and preferences"
        rule_types: list[str] | None = None
        if domain_config is not None:
            description = getattr(domain_config, "description", description)
            rule_types = getattr(domain_config, "rule_types", None)

        return await p.extract(
            text=text,
            domain=domain,
            domain_description=description,
            rule_types=rule_types,
            max_input_chars=self.max_input_chars,
        )

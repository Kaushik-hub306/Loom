"""Provider factory — auto-detects which LLM provider to use."""

import os
import sys

from loom.llm.base import BaseLLMProvider

_KNOWN_PROVIDERS = ("anthropic", "deepseek", "gemini")


def _model_override() -> str | None:
    """Optional model ID override (``LOOM_LLM_MODEL``)."""
    return os.environ.get("LOOM_LLM_MODEL") or None


def get_provider() -> BaseLLMProvider | None:
    """Return the configured LLM provider, or None if no provider is set.

    Detection order:
    1. ``LOOM_LLM_PROVIDER`` env var — explicit choice
       (``anthropic``, ``deepseek``, ``gemini``)
    2. ``ANTHROPIC_API_KEY`` — auto-detect Anthropic
    3. ``LOOM_DEEPSEEK_API_KEY`` — auto-detect DeepSeek
    4. ``GEMINI_API_KEY`` — auto-detect Gemini

    ``LOOM_LLM_MODEL`` optionally overrides the provider's default model.

    Returns None when no API key is set — caller should use keyword extraction.
    """
    explicit = os.environ.get("LOOM_LLM_PROVIDER", "").lower().strip()
    model = _model_override()

    if explicit == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if key:
            from loom.llm.anthropic import AnthropicProvider
            return AnthropicProvider(api_key=key, model=model)
        print(
            "[loom] LOOM_LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not "
            "set. Falling back to keyword extraction.",
            file=sys.stderr,
        )

    elif explicit == "deepseek":
        key = os.environ.get("LOOM_DEEPSEEK_API_KEY", "")
        if key:
            from loom.llm.deepseek import DeepSeekProvider
            return DeepSeekProvider(api_key=key, model=model)
        print(
            "[loom] LOOM_LLM_PROVIDER=deepseek but LOOM_DEEPSEEK_API_KEY is "
            "not set. Falling back to keyword extraction.",
            file=sys.stderr,
        )

    elif explicit == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "")
        if key:
            from loom.llm.gemini import GeminiProvider
            return GeminiProvider(api_key=key, model=model)
        print(
            "[loom] LOOM_LLM_PROVIDER=gemini but GEMINI_API_KEY is not set. "
            "Falling back to keyword extraction.",
            file=sys.stderr,
        )

    elif explicit == "":
        # Auto-detect: check for API keys in order of preference
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if anthropic_key:
            from loom.llm.anthropic import AnthropicProvider
            return AnthropicProvider(api_key=anthropic_key, model=model)

        deepseek_key = os.environ.get("LOOM_DEEPSEEK_API_KEY", "")
        if deepseek_key:
            from loom.llm.deepseek import DeepSeekProvider
            return DeepSeekProvider(api_key=deepseek_key, model=model)

        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        if gemini_key:
            from loom.llm.gemini import GeminiProvider
            return GeminiProvider(api_key=gemini_key, model=model)

    else:
        # A typo here used to silently disable LLM extraction with no
        # signal anywhere — make it loud (on stderr, never stdout).
        print(
            f"[loom] Unknown LOOM_LLM_PROVIDER={explicit!r} "
            f"(valid: {', '.join(_KNOWN_PROVIDERS)}). "
            f"Falling back to keyword extraction.",
            file=sys.stderr,
        )

    return None

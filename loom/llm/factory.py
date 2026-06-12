"""Provider factory — auto-detects which LLM provider to use."""

import os
from loom.llm.base import BaseLLMProvider


def get_provider() -> BaseLLMProvider | None:
    """Return the configured LLM provider, or None if no provider is set.

    Detection order:
    1. ``LOOM_LLM_PROVIDER`` env var — explicit choice
       (``anthropic``, ``deepseek``, ``gemini``)
    2. ``ANTHROPIC_API_KEY`` — auto-detect Anthropic
    3. ``LOOM_DEEPSEEK_API_KEY`` — auto-detect DeepSeek
    4. ``GEMINI_API_KEY`` — auto-detect Gemini

    Returns None when no API key is set — caller should use keyword extraction.
    """
    explicit = os.environ.get("LOOM_LLM_PROVIDER", "").lower()

    if explicit == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if key:
            from loom.llm.anthropic import AnthropicProvider
            return AnthropicProvider(api_key=key)

    elif explicit == "deepseek":
        key = os.environ.get("LOOM_DEEPSEEK_API_KEY", "")
        if key:
            from loom.llm.deepseek import DeepSeekProvider
            return DeepSeekProvider(api_key=key)

    elif explicit == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "")
        if key:
            from loom.llm.gemini import GeminiProvider
            return GeminiProvider(api_key=key)

    elif explicit == "":
        # Auto-detect: check for API keys in order of preference
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if anthropic_key:
            from loom.llm.anthropic import AnthropicProvider
            return AnthropicProvider(api_key=anthropic_key)

        deepseek_key = os.environ.get("LOOM_DEEPSEEK_API_KEY", "")
        if deepseek_key:
            from loom.llm.deepseek import DeepSeekProvider
            return DeepSeekProvider(api_key=deepseek_key)

        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        if gemini_key:
            from loom.llm.gemini import GeminiProvider
            return GeminiProvider(api_key=gemini_key)

    else:
        # Unknown explicit value — log warning? For now, fall through to None.
        pass

    return None

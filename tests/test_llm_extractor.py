"""Tests for LLMExtractor — provider-agnostic extraction, availability, fallback."""

from loom.engine.llm_extractor import LLMExtractor
from loom.llm.base import ExtractedRule
from loom.llm.anthropic import AnthropicProvider
from loom.llm.deepseek import DeepSeekProvider


def test_extractor_not_available_without_key():
    e = LLMExtractor()
    assert not e.is_available


def test_extractor_available_with_anthropic_provider():
    provider = AnthropicProvider(api_key="sk-ant-fake")
    e = LLMExtractor(provider=provider)
    assert e.is_available
    assert e.active_provider_name == "anthropic"


def test_extractor_available_with_deepseek_provider():
    provider = DeepSeekProvider(api_key="sk-ds-fake")
    e = LLMExtractor(provider=provider)
    assert e.is_available
    assert e.active_provider_name == "deepseek"


def test_extractor_available_with_env_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-key")
    e = LLMExtractor()
    assert e.is_available
    assert e.active_provider_name == "anthropic"


def test_extractor_deepseek_env_key(monkeypatch):
    monkeypatch.setenv("LOOM_DEEPSEEK_API_KEY", "sk-ds-env")
    e = LLMExtractor()
    assert e.is_available
    assert e.active_provider_name == "deepseek"


def test_extractor_default_model():
    e = LLMExtractor()
    # Without a provider, active_provider_name is "none"
    assert e.active_provider_name == "none"


def test_extractor_provider_model():
    provider = AnthropicProvider(api_key="sk-ant-fake")
    assert provider.default_model == "claude-sonnet-4-6"
    provider2 = DeepSeekProvider(api_key="sk-ds-fake")
    assert provider2.default_model == "deepseek-chat"


def test_extracted_rule_defaults():
    r = ExtractedRule(rule_type="test", rule="do this")
    assert r.example == ""
    assert r.confidence == 5


def test_extract_returns_empty_when_not_available():
    """extract() returns [] when no provider is configured."""
    import asyncio
    e = LLMExtractor()  # no provider
    result = asyncio.run(e.extract("some text"))
    assert result == []


def test_max_input_chars_default():
    e = LLMExtractor()
    assert e.max_input_chars == 8000

"""Tests for LLMExtractor — availability, fallback, and basic behavior."""

from loom.engine.llm_extractor import LLMExtractor, ExtractedRule


def test_llm_extractor_not_available_without_key():
    e = LLMExtractor()
    assert not e.is_available


def test_llm_extractor_available_with_key():
    e = LLMExtractor(api_key="sk-ant-fake")
    assert e.is_available


def test_llm_extractor_available_with_env_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-key")
    e = LLMExtractor()
    assert e.is_available


def test_llm_extractor_default_model():
    e = LLMExtractor()
    assert e.model == "claude-sonnet-4-6"


def test_llm_extractor_custom_model():
    e = LLMExtractor(model="claude-opus-4-8")
    assert e.model == "claude-opus-4-8"


def test_extracted_rule_defaults():
    r = ExtractedRule(rule_type="test", rule="do this")
    assert r.example == ""
    assert r.confidence == 5


def test_extract_returns_empty_when_not_available():
    """extract() returns [] when no API key is set."""
    import asyncio
    e = LLMExtractor()  # no key
    result = asyncio.run(e.extract("some text"))
    assert result == []


def test_max_input_chars_default():
    e = LLMExtractor()
    assert e.max_input_chars == 8000

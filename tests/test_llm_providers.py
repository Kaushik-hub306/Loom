"""LLM provider contract tests — the prompt builder and response parser.

The audit found extraction was broken for every provider (a NameError in
the shared prompt builder that blanket exception handlers swallowed
silently). These tests make that class of failure loud.
"""

import asyncio

from loom.llm.anthropic import AnthropicProvider
from loom.llm.base import BaseLLMProvider, ExtractedRule
from loom.llm.deepseek import DeepSeekProvider
from loom.llm.factory import get_provider
from loom.llm.gemini import GeminiProvider

ALL_PROVIDERS = [
    AnthropicProvider(api_key="sk-test"),
    DeepSeekProvider(api_key="sk-test"),
    GeminiProvider(api_key="test-key"),
]


def test_build_prompt_never_raises():
    """Regression: _build_prompt referenced an undefined name and raised
    NameError on every call, killing extraction for all providers."""
    for provider in ALL_PROVIDERS:
        prompt = provider._build_prompt(
            text="we always use tabs " * 1000,
            domain="style",
            domain_description="formatting conventions",
            rule_types=["formatting"],
            max_input_chars=500,
        )
        assert "we always use tabs" in prompt
        assert len(prompt) < 2000, "max_input_chars truncation must apply"
        assert "json" in prompt.lower(), "prompt must demand JSON output"


def test_parse_rules_json_happy_path():
    raw = '{"rules": [{"rule_type": "t", "rule": "do x", "example": "e", "confidence": 8}]}'
    rules = BaseLLMProvider._parse_rules_json(raw)
    assert len(rules) == 1
    assert rules[0] == ExtractedRule(rule_type="t", rule="do x", example="e", confidence=8)


def test_parse_rules_json_strips_markdown_fences():
    raw = '```json\n{"rules": [{"rule_type": "t", "rule": "do x", "confidence": 5}]}\n```'
    assert len(BaseLLMProvider._parse_rules_json(raw)) == 1


def test_parse_rules_json_finds_object_in_prose():
    raw = 'Sure! Here are the rules:\n{"rules": [{"rule_type": "t", "rule": "do x", "confidence": 5}]}\nHope that helps!'
    assert len(BaseLLMProvider._parse_rules_json(raw)) == 1


def test_parse_rules_json_clamps_confidence():
    raw = '{"rules": [{"rule_type": "t", "rule": "a", "confidence": 99}, {"rule_type": "t", "rule": "b", "confidence": -3}]}'
    rules = BaseLLMProvider._parse_rules_json(raw)
    assert rules[0].confidence == 10
    assert rules[1].confidence == 1


def test_parse_rules_json_garbage_returns_empty():
    for raw in ["", "not json", '{"rules": "nope"}', '{"other": 1}',
                '{"rules": [null, {"no_rule_key": true}, "str"]}']:
        assert BaseLLMProvider._parse_rules_json(raw) == []


def test_extract_returns_empty_without_sdk_installed():
    """When the vendor SDK isn't importable, extract() degrades to []."""
    for provider in ALL_PROVIDERS:
        result = asyncio.run(provider.extract("we always use tabs here"))
        assert result == []


def test_factory_returns_none_without_keys():
    assert get_provider() is None


def test_factory_detects_each_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    assert get_provider().provider_name == "anthropic"
    monkeypatch.delenv("ANTHROPIC_API_KEY")

    monkeypatch.setenv("LOOM_DEEPSEEK_API_KEY", "sk-ds-x")
    assert get_provider().provider_name == "deepseek"
    monkeypatch.delenv("LOOM_DEEPSEEK_API_KEY")

    monkeypatch.setenv("GEMINI_API_KEY", "g-x")
    assert get_provider().provider_name == "gemini"


def test_factory_unknown_provider_warns_and_returns_none(monkeypatch, capsys):
    monkeypatch.setenv("LOOM_LLM_PROVIDER", "antropic")  # typo
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    assert get_provider() is None
    err = capsys.readouterr().err
    assert "Unknown LOOM_LLM_PROVIDER" in err


def test_factory_model_override(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("LOOM_LLM_MODEL", "claude-opus-4-8")
    assert get_provider().model == "claude-opus-4-8"


def test_providers_have_timeouts():
    for provider in ALL_PROVIDERS:
        assert provider.timeout > 0

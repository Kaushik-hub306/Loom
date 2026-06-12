"""Tests for DomainExtractor — legacy keyword-based feedback extraction."""

import pytest

from loom.engine.domain_extractor import DomainExtractor, DomainConfig


# ── helpers ───────────────────────────────────────────────────────────────


def _make_extractor(domains: dict | None = None) -> DomainExtractor:
    """Create a DomainExtractor, optionally pre-configured with domains."""
    extractor = DomainExtractor()
    if domains:
        extractor.domains = domains
    return extractor


def _coding_domain():
    return DomainConfig(
        name="coding",
        keywords=["type hint", "test", "python", "code", "function", "api"],
        rule_types=["type_safety", "testing", "naming"],
    )


def _support_domain():
    return DomainConfig(
        name="support",
        keywords=["customer", "help", "support", "escalation", "ticket"],
        rule_types=["escalation"],
    )


# ── detect_domain tests ───────────────────────────────────────────────────


class TestDetectDomain:
    """Tests for detect_domain() — domain keyword matching."""

    def test_matches_coding_keywords(self):
        """detect_domain returns 'coding' when feedback has coding keywords."""
        extractor = _make_extractor({"coding": _coding_domain()})

        result = extractor.detect_domain(
            "Please add type hints to all function signatures"
        )

        assert result == "coding"

    def test_returns_none_when_no_keywords_match(self):
        """detect_domain returns None for unrecognized feedback."""
        extractor = _make_extractor({"coding": _coding_domain()})

        result = extractor.detect_domain("The weather is nice today")

        assert result is None

    def test_matches_support_keywords(self):
        """detect_domain returns 'support' when feedback has support keywords."""
        extractor = _make_extractor({
            "coding": _coding_domain(),
            "support": _support_domain(),
        })

        result = extractor.detect_domain(
            "Customer escalation needs immediate attention"
        )

        assert result == "support"

    def test_returns_first_matching_domain(self):
        """When multiple domains match, the first one (by insertion order) wins."""
        extractor = _make_extractor({
            "coding": _coding_domain(),
            "support": _support_domain(),
        })

        # 'help' matches coding keywords? No. But 'Customer' matches support.
        result = extractor.detect_domain("Customer code needs help")

        assert result == "coding"  # 'code' in 'Customer code' matches coding first

    def test_case_insensitive_matching(self):
        """Keyword matching is case-insensitive."""
        extractor = _make_extractor({"coding": _coding_domain()})

        result = extractor.detect_domain("Use TYPE HINTS everywhere")

        assert result == "coding"


# ── extract_rules tests ───────────────────────────────────────────────────


class TestExtractRules:
    """Tests for extract_rules() — rule type extraction from feedback."""

    def test_extracts_type_safety_from_type_hint_feedback(self):
        """Feedback about type hints should yield type_safety rules."""
        extractor = _make_extractor()

        rules = extractor.extract_rules(
            "Please add type annotations to all function parameters"
        )

        rule_types = {r["rule_type"] for r in rules}
        assert "type_safety" in rule_types
        type_safety_rule = next(
            r for r in rules if r["rule_type"] == "type_safety"
        )
        assert isinstance(type_safety_rule["rule"], str)
        assert len(type_safety_rule["rule"]) > 0
        assert type_safety_rule["confidence"] == 5

    def test_extracts_testing_rules_from_test_feedback(self):
        """Feedback about tests should yield testing rules."""
        extractor = _make_extractor()

        rules = extractor.extract_rules(
            "Make sure to add unit tests for the new endpoint"
        )

        rule_types = {r["rule_type"] for r in rules}
        assert "testing" in rule_types

    def test_extracts_multiple_rule_types_from_complex_feedback(self):
        """A single complex feedback may trigger multiple rule types."""
        extractor = _make_extractor()

        rules = extractor.extract_rules(
            "Add type annotations to all functions and include docstrings "
            "for every public method. Also add unit tests."
        )

        rule_types = {r["rule_type"] for r in rules}
        assert "type_safety" in rule_types
        assert "testing" in rule_types
        assert "documentation" in rule_types

    def test_does_not_duplicate_rule_type(self):
        """Multiple keyword matches for the same rule_type only produce one rule."""
        extractor = _make_extractor()

        rules = extractor.extract_rules(
            "Add type hints and type annotations. Use typing module and return types."
        )

        type_rules = [r for r in rules if r["rule_type"] == "type_safety"]
        assert len(type_rules) == 1

    def test_returns_empty_list_for_no_matches(self):
        """Feedback with no keyword matches yields no rules."""
        extractor = _make_extractor()

        rules = extractor.extract_rules(
            "Everything looks good, ship it!"
        )

        assert rules == []


# ── _extract_rule_sentence tests ──────────────────────────────────────────


class TestExtractRuleSentence:
    """Tests for _extract_rule_sentence() — best sentence extraction."""

    def test_extracts_correct_sentence(self):
        """Should extract the sentence containing the matched keyword."""
        extractor = _make_extractor()

        sentence = extractor._extract_rule_sentence(
            "Great work. Please add type hints to all functions. Also update docs.",
            "type hints",
        )

        assert "type hints" in sentence.lower()
        assert sentence == "Please add type hints to all functions"

    def test_falls_back_to_truncated_full_text(self, keyword=None):
        """When keyword is not in any sentence, return truncated full text."""
        extractor = _make_extractor()

        sentence = extractor._extract_rule_sentence(
            "Please add type hints to all function signatures and return types",
            "bananas",
        )

        # Keyword not found; falls back to full text truncated to 200 chars
        assert sentence == "Please add type hints to all function signatures and return types"

    def test_truncates_long_sentences(self):
        """Extracted sentence is truncated to 200 characters."""
        extractor = _make_extractor()
        long_text = "x" * 250

        sentence = extractor._extract_rule_sentence(long_text, "x")

        assert len(sentence) <= 200
        assert sentence == "x" * 200

    def test_handles_multiple_sentence_endings(self):
        """Various sentence-ending punctuation is handled."""
        extractor = _make_extractor()

        sentence = extractor._extract_rule_sentence(
            "Fix bug. Add tests! Why no coverage? Do it now.",
            "coverage",
        )

        assert "coverage" in sentence.lower()

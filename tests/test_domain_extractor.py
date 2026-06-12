"""Tests for DomainExtractor and DomainConfig."""

import tempfile
from pathlib import Path

import pytest
import yaml

from loom.engine.domain_extractor import DomainConfig, DomainExtractor


# ── DomainConfig ────────────────────────────────────────────────────


def test_domain_config_from_yaml():
    tmp = Path(tempfile.mkdtemp()) / "test.yml"
    tmp.write_text(yaml.dump({
        "name": "test_domain",
        "description": "A test domain",
        "keywords": ["test"],
        "rule_types": ["type_a", "type_b"],
        "patterns": {
            "type_a": ["keyword_a"],
            "type_b": ["keyword_b"],
        },
        "use_llm": True,
    }))
    cfg = DomainConfig.from_yaml(tmp)
    assert cfg.name == "test_domain"
    assert cfg.description == "A test domain"
    assert cfg.rule_types == ["type_a", "type_b"]
    assert cfg.patterns == {"type_a": ["keyword_a"], "type_b": ["keyword_b"]}
    assert cfg.use_llm is True


def test_domain_config_defaults():
    tmp = Path(tempfile.mkdtemp()) / "minimal.yml"
    tmp.write_text(yaml.dump({"name": "minimal"}))
    cfg = DomainConfig.from_yaml(tmp)
    assert cfg.keywords == []
    assert cfg.rule_types == []
    assert cfg.patterns == {}
    assert cfg.use_llm is False


# ── DomainExtractor ─────────────────────────────────────────────────


@pytest.fixture
def domains_dir():
    """Create a temp dir with a couple test domain configs."""
    d = Path(tempfile.mkdtemp())
    (d / "test_a.yml").write_text(yaml.dump({
        "name": "test_a",
        "keywords": ["alpha", "first"],
        "rule_types": ["pattern_a"],
        "patterns": {"pattern_a": ["alpha trigger"]},
    }))
    (d / "test_b.yml").write_text(yaml.dump({
        "name": "test_b",
        "keywords": ["beta", "second"],
        "rule_types": ["pattern_b"],
        "patterns": {"pattern_b": ["beta trigger"]},
    }))
    return d


def test_extractor_loads_domains(domains_dir):
    e = DomainExtractor(domains_dir)
    assert "test_a" in e.domains
    assert "test_b" in e.domains


def test_extractor_empty_dir_works():
    e = DomainExtractor(Path(tempfile.mkdtemp()))
    assert len(e.domains) == 0
    # Should still extract using fallback patterns
    rules = e.extract_rules("add type hints", "coding")
    assert len(rules) > 0


def test_detect_domain(domains_dir):
    e = DomainExtractor(domains_dir)
    assert e.detect_domain("this is an alpha project") == "test_a"
    assert e.detect_domain("use the beta approach") == "test_b"
    assert e.detect_domain("nothing matches here") is None


def test_extract_rules_uses_domain_patterns(domains_dir):
    e = DomainExtractor(domains_dir)
    rules = e.extract_rules("alpha trigger is important", "test_a")
    assert len(rules) == 1
    assert rules[0]["rule_type"] == "pattern_a"


def test_extract_rules_fallback_when_no_domain(domains_dir):
    e = DomainExtractor(domains_dir)
    rules = e.extract_rules("add type hints and unit tests", "nonexistent")
    # Falls back to built-in fallback patterns
    assert len(rules) > 0


def test_extract_rules_fallback_when_domain_has_no_patterns(domains_dir):
    # Add a domain with no patterns block
    e = DomainExtractor(domains_dir)
    e.domains["empty"] = DomainConfig("empty")
    rules = e.extract_rules("add type hints", "empty")
    # Falls back to built-in patterns
    assert len(rules) > 0


def test_extract_rules_no_match(domains_dir):
    e = DomainExtractor(domains_dir)
    rules = e.extract_rules("nothing relevant here at all", "test_a")
    assert len(rules) == 0

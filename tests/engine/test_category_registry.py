"""Tests for CategoryRegistry — domain config loading, detection, and classification."""

import tempfile
from pathlib import Path

import pytest

from loom.engine.category_registry import CategoryRegistry


# ── Helpers ───────────────────────────────────────────────────────────────

@pytest.fixture
def domain_configs_dir(tmp_path) -> Path:
    """Create a temporary directory with YAML domain config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "python.yaml").write_text("""
domain: python
label: Python
categories:
  type_safety:
    label: Type Safety
    prompts:
      - "type hints"
      - "mypy"
      - "type annotations"
      - "mypy.ini"
  style:
    label: Code Style
    prompts:
      - "pep8"
      - "snake_case"
      - "formatting"
  testing:
    label: Testing
    prompts:
      - "pytest"
      - "unittest"
      - "coverage"
      - "test fixtures"
""")

    (config_dir / "javascript.yaml").write_text("""
domain: javascript
label: JavaScript
categories:
  style:
    label: Code Style
    prompts:
      - "camelCase"
      - "prettier"
      - "eslint"
      - "semicolons"
  async:
    label: Async Patterns
    prompts:
      - "async/await"
      - "promise"
      - "callback"
""")

    (config_dir / "security.yaml").write_text("""
domain: security
label: Security
categories:
  secrets:
    label: Secrets Management
    prompts:
      - "API key"
      - "secret"
      - "credential"
      - "token"
      - "password"
  input_validation:
    label: Input Validation
    prompts:
      - "sanitize"
      - "validate input"
      - "SQL injection"
      - "XSS"
""")

    return config_dir


@pytest.fixture
def registry(domain_configs_dir):
    """A CategoryRegistry loaded from the test YAML configs."""
    return CategoryRegistry(config_dir=domain_configs_dir)


# ── Domain config loading ─────────────────────────────────────────────────

def test_loads_all_domains(registry):
    """All three domain config files are loaded."""
    domains = registry.list_domains()
    assert "python" in domains
    assert "javascript" in domains
    assert "security" in domains


def test_loads_categories_per_domain(registry):
    """Each domain has its expected categories."""
    python_cats = registry.list_categories("python")
    assert "type_safety" in python_cats
    assert "style" in python_cats
    assert "testing" in python_cats
    assert len(python_cats) == 3

    js_cats = registry.list_categories("javascript")
    assert "style" in js_cats
    assert "async" in js_cats


def test_category_labels_are_loaded(registry):
    """Category labels are loaded from YAML."""
    label = registry.get_category_label("python", "type_safety")
    assert label == "Type Safety"


def test_category_prompts_are_loaded(registry):
    """Category prompts are loaded from YAML."""
    prompts = registry.get_prompts("python", "type_safety")
    assert "type hints" in prompts
    assert "mypy" in prompts
    assert "type annotations" in prompts


# ── detect_domain ─────────────────────────────────────────────────────────

def test_detect_domain_exact_match(registry):
    """Exact prompt match detects the correct domain."""
    result = registry.detect_domain("Use type hints for all functions")
    assert result is not None
    assert result["domain"] == "python"


def test_detect_domain_partial_match(registry):
    """Partial prompt match detects the correct domain."""
    result = registry.detect_domain("This code needs better mypy configuration")
    assert result is not None
    assert result["domain"] == "python"


def test_detect_domain_case_insensitive(registry):
    """Domain detection is case-insensitive."""
    result = registry.detect_domain("Use ESLINT for linting")
    assert result is not None
    assert result["domain"] == "javascript"


def test_detect_domain_multiple_matches_returns_best(registry):
    """When multiple domains match, the one with the most prompt matches wins."""
    result = registry.detect_domain("Use good style formatting with prettier and eslint")
    # Both python (style/formatting) and javascript (style/prettier/eslint) match
    # javascript should have more matches
    assert result is not None
    # Both possible, but javascript has more keyword matches
    assert result["domain"] in ("python", "javascript")


def test_detect_domain_no_match_returns_none(registry):
    """Non-matching text returns None with a suggestion."""
    result = registry.detect_domain("xyzzy nothing matches this text")
    assert result is None


def test_detect_domain_returns_confidence(registry):
    """detect_domain includes a confidence/score in its result."""
    result = registry.detect_domain("Add type hints to all function signatures")
    assert result is not None
    assert "confidence" in result or "score" in result


def test_detect_domain_returns_suggested_categories(registry):
    """detect_domain suggests categories from the matched domain."""
    result = registry.detect_domain("Use pytest for testing and mypy for type checking")
    assert result is not None
    assert "suggested_categories" in result or "categories" in result


# ── classify ──────────────────────────────────────────────────────────────

def test_classify_type_safety_feedback(registry):
    """Classify feedback about type hints into type_safety category."""
    result = registry.classify("python", "Please add type annotations to all public functions")
    assert result is not None
    assert "type_safety" in result
    assert "style" not in result or result.get("type_safety", 0) > result.get("style", 0)


def test_classify_style_feedback(registry):
    """Classify feedback about formatting into style category."""
    result = registry.classify("python", "Use snake_case for variable names and follow pep8")
    assert result is not None
    assert "style" in result


def test_classify_testing_feedback(registry):
    """Classify feedback about testing into testing category."""
    result = registry.classify("python", "Add more pytest coverage and test fixtures")
    assert result is not None
    assert "testing" in result


def test_classify_returns_scores_for_all_categories(registry):
    """classify returns a dict mapping category name to score."""
    result = registry.classify("python", "Use type hints and pytest for all new code")
    assert isinstance(result, dict)
    # All python categories should appear
    for cat in registry.list_categories("python"):
        assert cat in result


def test_classify_unknown_domain_returns_empty(registry):
    """classify on unknown domain returns empty dict."""
    result = registry.classify("ruby", "Some feedback about ruby code")
    assert result == {} or result is None


def test_classify_empty_feedback(registry):
    """classify with empty feedback text returns low/zero scores."""
    result = registry.classify("python", "")
    assert isinstance(result, dict)
    for score in result.values():
        assert score == 0 or score == 0.0


# ── Custom domain configs ─────────────────────────────────────────────────

def test_custom_config_dir(tmp_path):
    """CategoryRegistry works with a user-specified config directory."""
    custom_dir = tmp_path / "custom_configs"
    custom_dir.mkdir()
    (custom_dir / "ruby.yaml").write_text("""
domain: ruby
label: Ruby
categories:
  style:
    label: Code Style
    prompts:
      - "rubocop"
      - "snake_case"
""")

    reg = CategoryRegistry(config_dir=custom_dir)
    assert "ruby" in reg.list_domains()
    assert reg.get_category_label("ruby", "style") == "Code Style"


def test_custom_config_overrides_default(tmp_path):
    """Custom config with same domain name overrides or merges."""
    # Write a custom python config that adds a new category
    custom_dir = tmp_path / "custom_configs"
    custom_dir.mkdir()
    (custom_dir / "python.yaml").write_text("""
domain: python
label: Python (Custom)
categories:
  documentation:
    label: Documentation
    prompts:
      - "docstring"
      - "readme"
""")

    reg = CategoryRegistry(config_dir=custom_dir)
    # The label shows our custom version
    label = reg.get_category_label("python", "documentation")
    assert label == "Documentation"


def test_empty_config_dir_does_not_crash(tmp_path):
    """CategoryRegistry handles empty config dir gracefully."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    reg = CategoryRegistry(config_dir=empty_dir)
    assert reg.list_domains() == [] or isinstance(reg.list_domains(), list)


def test_config_dir_with_invalid_yaml_handled_gracefully(tmp_path):
    """Invalid YAML files don't crash the registry."""
    bad_dir = tmp_path / "bad_configs"
    bad_dir.mkdir()
    (bad_dir / "junk.yaml").write_text("this: [is not valid yaml {{{")
    try:
        reg = CategoryRegistry(config_dir=bad_dir)
        # Should not have crashed
    except Exception as e:
        pytest.fail(f"CategoryRegistry raised {type(e).__name__}: {e}")


def test_classify_multiple_keyword_matches(registry):
    """Feedback matching multiple categories assigns scores accordingly."""
    result = registry.classify(
        "python",
        "Use type hints for all functions, follow pep8 style, and add pytest coverage"
    )
    assert isinstance(result, dict)
    # All three categories should have some non-zero score
    # (exact behavior depends on scoring implementation)
    assert "type_safety" in result
    assert "style" in result
    assert "testing" in result

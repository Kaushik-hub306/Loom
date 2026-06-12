"""Tests for v1→v2 migration: old rules.json → store.json with Observations."""

import json
import shutil
from pathlib import Path

import pytest

from loom.engine.observation_store import ObservationStore


# ── Helpers ───────────────────────────────────────────────────────────────

@pytest.fixture
def old_rules_json_content() -> list[dict]:
    """Sample old-format rules matching the Rule dataclass shape."""
    return [
        {
            "id": "python::type_safety::use-type-hints",
            "domain": "python",
            "rule_type": "type_safety",
            "rule": "Always use type hints in function signatures",
            "example": "def foo(x: int) -> str: ...",
            "confidence": 8,
            "times_confirmed": 4,
            "times_violated": 1,
            "source_urls": ["https://peps.python.org/pep-0484/"],
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-03-01T00:00:00Z",
        },
        {
            "id": "python::style::use-snake-case",
            "domain": "python",
            "rule_type": "style",
            "rule": "Use snake_case for variable and function names",
            "example": "my_variable = 42",
            "confidence": 9,
            "times_confirmed": 6,
            "times_violated": 0,
            "source_urls": ["https://peps.python.org/pep-0008/"],
            "created_at": "2025-01-02T00:00:00Z",
            "updated_at": "2025-04-01T00:00:00Z",
        },
        {
            "id": "javascript::style::use-camel-case",
            "domain": "javascript",
            "rule_type": "style",
            "rule": "Use camelCase for variable and function names",
            "example": "const myVariable = 42;",
            "confidence": 7,
            "times_confirmed": 3,
            "times_violated": 2,
            "source_urls": [],
            "created_at": "2025-02-01T00:00:00Z",
            "updated_at": "2025-05-01T00:00:00Z",
        },
    ]


@pytest.fixture
def loom_dir_with_old_rules(tmp_path, old_rules_json_content):
    """Create a temporary .loom/ directory containing old rules.json and domain configs."""
    loom_dir = tmp_path / "loom_data"
    loom_dir.mkdir()
    rules_path = loom_dir / "rules.json"
    rules_path.write_text(json.dumps({"rules": old_rules_json_content}))

    # Also create a small domain config so the store dir looks realistic
    config_dir = loom_dir / "config"
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
  style:
    label: Code Style
    prompts:
      - "snake_case"
      - "pep8"
""")

    return loom_dir


# ── Migration tests ───────────────────────────────────────────────────────

def test_migration_creates_store_json_with_version_2(loom_dir_with_old_rules):
    """After init, store.json is created containing version 2."""
    store_path = loom_dir_with_old_rules / "store.json"
    assert not store_path.exists()

    store = ObservationStore(path=store_path)

    # store.json should exist with data migrated
    assert store_path.exists()
    data = json.loads(store_path.read_text())
    assert data["version"] == 2


def test_migration_creates_rules_json_bak(loom_dir_with_old_rules):
    """Migration creates a rules.json.bak backup."""
    backup_path = loom_dir_with_old_rules / "rules.json.bak"
    assert not backup_path.exists()

    store_path = loom_dir_with_old_rules / "store.json"
    ObservationStore(path=store_path)

    assert backup_path.exists()
    backup_data = json.loads(backup_path.read_text())
    assert "rules" in backup_data
    assert len(backup_data["rules"]) == 3


def test_migration_does_not_delete_old_rules_json(loom_dir_with_old_rules):
    """Old rules.json is NOT deleted after migration — kept for reference."""
    rules_path = loom_dir_with_old_rules / "rules.json"
    assert rules_path.exists()

    store_path = loom_dir_with_old_rules / "store.json"
    ObservationStore(path=store_path)

    assert rules_path.exists()
    data = json.loads(rules_path.read_text())
    assert "rules" in data


def test_migration_all_rules_converted(loom_dir_with_old_rules):
    """All 3 rules from old format are migrated to observations."""
    store_path = loom_dir_with_old_rules / "store.json"
    store = ObservationStore(path=store_path)

    assert len(store) == 3
    data = json.loads(store_path.read_text())
    assert len(data["observations"]) == 3


def test_migration_rule_type_becomes_category(loom_dir_with_old_rules):
    """Old rule_type field is mapped to category."""
    store_path = loom_dir_with_old_rules / "store.json"
    store = ObservationStore(path=store_path)

    all_obs = store.search(query="")
    categories = {o.category for o in all_obs}
    assert "type_safety" in categories
    assert "style" in categories


def test_migration_rule_becomes_content(loom_dir_with_old_rules):
    """Old rule field is mapped to content."""
    store_path = loom_dir_with_old_rules / "store.json"
    store = ObservationStore(path=store_path)

    obs = store.search(query="type hints")[0]
    assert obs.content == "Always use type hints in function signatures"


def test_migration_observation_type_set_to_rule(loom_dir_with_old_rules):
    """All migrated observations have observation_type='rule'."""
    store_path = loom_dir_with_old_rules / "store.json"
    store = ObservationStore(path=store_path)

    all_obs = store.search(query="")
    for obs in all_obs:
        assert obs.observation_type == "rule", f"{obs.id} has type {obs.observation_type}"


def test_migration_preserves_confidence_and_times(loom_dir_with_old_rules):
    """Confidence, times_confirmed, times_violated are preserved after migration."""
    store_path = loom_dir_with_old_rules / "store.json"
    store = ObservationStore(path=store_path)

    py_obs = store.search(query="type hints")[0]
    assert py_obs.confidence == 8
    assert py_obs.times_confirmed == 4
    assert py_obs.times_violated == 1


def test_migration_preserves_source_urls(loom_dir_with_old_rules):
    """source_urls are preserved through migration."""
    store_path = loom_dir_with_old_rules / "store.json"
    store = ObservationStore(path=store_path)

    py_obs = store.search(query="type hints")[0]
    assert "https://peps.python.org/pep-0484/" in py_obs.source_urls


def test_migration_preserves_domain(loom_dir_with_old_rules):
    """domain field is preserved across migration."""
    store_path = loom_dir_with_old_rules / "store.json"
    store = ObservationStore(path=store_path)

    domains = {o.domain for o in store.search(query="")}
    assert "python" in domains
    assert "javascript" in domains


def test_migration_new_fields_get_sensible_defaults(loom_dir_with_old_rules):
    """New fields (tags, access_scope, source_agent, source_session) get defaults."""
    store_path = loom_dir_with_old_rules / "store.json"
    store = ObservationStore(path=store_path)

    for obs in store.search(query=""):
        assert obs.tags == []
        assert obs.access_scope == "team"
        assert obs.source_agent == ""
        assert obs.source_session == ""
        assert obs.context == {}


def test_migration_idempotent_does_not_create_duplicates(loom_dir_with_old_rules):
    """Calling ObservationStore twice on the same directory doesn't create duplicates."""
    store_path = loom_dir_with_old_rules / "store.json"

    # First load triggers migration
    store1 = ObservationStore(path=store_path)
    assert len(store1) == 3

    # Second load reads existing store.json, doesn't re-migrate
    store2 = ObservationStore(path=store_path)
    assert len(store2) == 3


def test_migration_no_rules_json_starts_empty(tmp_path):
    """When no rules.json exists, the store starts empty (no crash)."""
    store_path = tmp_path / "fresh_store.json"
    store = ObservationStore(path=store_path)
    assert len(store) == 0
    assert store_path.exists()


def test_migration_corrupted_rules_json_handled_gracefully(tmp_path):
    """Corrupt rules.json doesn't crash — store starts empty."""
    loom_dir = tmp_path / "loom_data"
    loom_dir.mkdir()
    (loom_dir / "rules.json").write_text("this is not valid json {{{")

    store_path = loom_dir / "store.json"
    store = ObservationStore(path=store_path)
    assert len(store) == 0


def test_migration_empty_rules_json_creates_empty_store(tmp_path):
    """Empty rules.json (rules array empty) creates an empty store."""
    loom_dir = tmp_path / "loom_data"
    loom_dir.mkdir()
    (loom_dir / "rules.json").write_text('{"rules": []}')

    store_path = loom_dir / "store.json"
    store = ObservationStore(path=store_path)
    assert len(store) == 0
    data = json.loads(store_path.read_text())
    assert data["observations"] == []


def test_migration_backup_matches_original_content(loom_dir_with_old_rules, old_rules_json_content):
    """The .bak file is an exact copy of the original rules.json content."""
    store_path = loom_dir_with_old_rules / "store.json"
    ObservationStore(path=store_path)

    original = json.loads((loom_dir_with_old_rules / "rules.json").read_text())
    backup = json.loads((loom_dir_with_old_rules / "rules.json.bak").read_text())
    assert original == backup


def test_migration_preserves_timestamps(loom_dir_with_old_rules):
    """created_at and updated_at are preserved through migration."""
    store_path = loom_dir_with_old_rules / "store.json"
    store = ObservationStore(path=store_path)

    py_obs = store.search(query="type hints")[0]
    assert py_obs.created_at == "2025-01-01T00:00:00Z"
    assert py_obs.updated_at == "2025-03-01T00:00:00Z"

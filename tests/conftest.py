"""Shared pytest fixtures for the Loom test suite."""

import json
import tempfile
from pathlib import Path

import pytest

from loom.engine.observation import Observation
from loom.engine.observation_store import ObservationStore


# ── Directory fixtures ────────────────────────────────────────────────────

@pytest.fixture
def tmp_loom_dir(tmp_path):
    """Temporary .loom/ directory with domain configs and no pre-existing store."""
    loom_dir = tmp_path / "loom_data"
    loom_dir.mkdir()

    # Domain configs
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
      - "type annotations"
  style:
    label: Code Style
    prompts:
      - "pep8"
      - "snake_case"
      - "black"
  testing:
    label: Testing
    prompts:
      - "pytest"
      - "coverage"
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
  async:
    label: Async Patterns
    prompts:
      - "async/await"
      - "promises"
""")

    return loom_dir


@pytest.fixture
def tmp_store(tmp_loom_dir):
    """ObservationStore pointed at a temp directory, with domain configs available."""
    store_path = tmp_loom_dir / "store.json"
    return ObservationStore(path=store_path)


# ── Observation fixtures ──────────────────────────────────────────────────

@pytest.fixture
def sample_observations():
    """A list of sample Observations covering multiple types, domains, and scopes."""
    return [
        Observation(
            id="python::type_safety::use-type-hints",
            observation_type="rule",
            domain="python",
            category="type_safety",
            content="Always use type hints in function signatures",
            confidence=8,
            times_confirmed=4,
            times_violated=1,
            source_urls=["https://peps.python.org/pep-0484/"],
            source_agent="claude-opus",
            source_session="sess-001",
            tags=["best-practice", "linting"],
            access_scope="team",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-03-01T00:00:00Z",
        ),
        Observation(
            id="python::style::snake-case",
            observation_type="rule",
            domain="python",
            category="style",
            content="Use snake_case for variable and function names",
            confidence=9,
            times_confirmed=6,
            times_violated=0,
            source_urls=["https://peps.python.org/pep-0008/"],
            source_agent="claude-opus",
            source_session="sess-001",
            tags=["best-practice"],
            access_scope="team",
            created_at="2025-01-02T00:00:00Z",
            updated_at="2025-04-01T00:00:00Z",
        ),
        Observation(
            id="python::fact::garbage-collection",
            observation_type="fact",
            domain="python",
            category="language",
            content="Python uses reference counting with cycle-detecting GC",
            confidence=10,
            times_confirmed=8,
            times_violated=0,
            source_urls=["https://docs.python.org/3/library/gc.html"],
            source_agent="claude-sonnet",
            source_session="sess-002",
            tags=["language", "internals"],
            access_scope="public",
            created_at="2025-02-01T00:00:00Z",
            updated_at="2025-02-01T00:00:00Z",
        ),
        Observation(
            id="javascript::style::camel-case",
            observation_type="rule",
            domain="javascript",
            category="style",
            content="Use camelCase for variable and function names",
            confidence=7,
            times_confirmed=3,
            times_violated=2,
            source_urls=[],
            source_agent="claude-haiku",
            source_session="sess-003",
            tags=["style"],
            access_scope="public",
            created_at="2025-02-15T00:00:00Z",
            updated_at="2025-05-01T00:00:00Z",
        ),
        Observation(
            id="team::decision::use-pytest",
            observation_type="decision",
            domain="team",
            category="testing",
            content="Use pytest for all Python testing",
            context={"decided_by": "eng-team", "date": "2025-01-15"},
            confidence=10,
            times_confirmed=2,
            times_violated=0,
            source_urls=[],
            source_agent="claude-opus",
            source_session="sess-001",
            tags=["testing", "decision"],
            access_scope="org",
            created_at="2025-01-15T00:00:00Z",
            updated_at="2025-01-15T00:00:00Z",
        ),
    ]


@pytest.fixture
def populated_store_from_fixtures(tmp_loom_dir, sample_observations):
    """ObservationStore pre-loaded with sample_observations via direct serialization."""
    store_path = tmp_loom_dir / "store.json"
    data = {
        "version": 2,
        "observations": [o.to_dict() for o in sample_observations],
    }
    store_path.write_text(json.dumps(data, indent=2))
    return ObservationStore(path=store_path)

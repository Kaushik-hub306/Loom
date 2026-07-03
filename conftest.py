"""Root conftest — keeps the test suite hermetic.

Ambient environment (a developer's real ANTHROPIC_API_KEY, a CI runner's
LOOM_* settings) must never change test behavior. Every test runs with
these variables cleared unless it sets them explicitly via monkeypatch.
"""

import pytest

_ISOLATED_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "LOOM_DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "LOOM_LLM_PROVIDER",
    "LOOM_LLM_MODEL",
    "LOOM_PROJECT_ROOT",
    "LOOM_STORAGE_BACKEND",
    "LOOM_DATABASE_URL",
    "LOOM_ORG_STORE",
    "LOOM_PRIVATE_MODE",
    "LOOM_STORE_DIR",
    "LOOM_AGENT_ID",
    "LOOM_AGENT_ROLE",
    "LOOM_AGENT_TEAMS",
    "LOOM_PROXY_TARGETS",
]


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for var in _ISOLATED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield

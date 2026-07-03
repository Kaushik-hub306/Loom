"""Hook-layer tests — the behaviors that make Loom's headline claims true.

Every test here calls ``call_tool`` — the same path the FastMCP wrappers
now dispatch through — so what passes here is what real MCP clients get.
"""

import asyncio

import pytest

from loom.mcp.server import create_loom_server
from loom.security.rbac import ClearanceLevel


def _run(coro):
    return asyncio.run(coro)


def _text(results) -> str:
    return "\n".join(r.text for r in results)


@pytest.fixture()
def server(tmp_path):
    return create_loom_server(tmp_path)


def test_teach_redacts_secrets_before_storage(server, tmp_path):
    _run(server.call_tool("teach", {
        "domain": "security", "rule_type": "secrets",
        "rule": "Never hardcode sk-ant-api03-AbCdEf123456-7890XyZabcdKLMNO anywhere",
        "confidence": 9,
    }))
    stored = (tmp_path / ".loom" / "rules.json").read_text()
    assert "sk-ant-api03" not in stored
    assert "[REDACTED:api-key]" in stored


def test_learn_redacts_secrets_before_storage(server, tmp_path):
    _run(server.call_tool("learn", {
        "context": "reviewing deploy scripts",
        "observation": "found token ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789 "
                       "committed — always use env vars for tokens",
        "lesson": "Never commit GitHub tokens; load them from the environment",
        "domain": "security",
    }))
    stored = (tmp_path / ".loom" / "rules.json").read_text()
    assert "ghp_AbCdEfGh" not in stored


def test_auto_observe_fires_for_write_tools(server):
    _run(server.call_tool("teach", {
        "domain": "coding", "rule_type": "style", "rule": "use guard clauses",
    }))
    assert server.auto_observer.buffer_size >= 1


def test_private_mode_blocks_writes_allows_reads(server, monkeypatch):
    monkeypatch.setenv("LOOM_PRIVATE_MODE", "1")
    blocked = _text(_run(server.call_tool("teach", {
        "domain": "coding", "rule_type": "x", "rule": "should not be stored",
    })))
    assert "Private Mode" in blocked
    assert len(server.store) == 0

    read = _text(_run(server.call_tool("recall_memory", {"query": "anything"})))
    assert "Private Mode" not in read


def test_rbac_clearance_enforced_on_recall_and_export(server):
    _run(server.call_tool("teach", {
        "domain": "security", "rule_type": "secrets",
        "rule": "rotate credentials quarterly", "confidence": 9,
    }))
    rule_id = next(iter(server.store.rules))

    _run(server.call_tool("set_clearance", {
        "rule_id": rule_id, "clearance": "restricted", "allowed_roles": [],
    }))

    recall = _text(_run(server.call_tool("recall_memory", {"query": "rotate"})))
    assert "rotate credentials" not in recall

    export = _text(_run(server.call_tool("export", {"format": "compact"})))
    assert "rotate credentials" not in export


def test_rbac_allowed_agent_still_sees_rule(server):
    _run(server.call_tool("teach", {
        "domain": "security", "rule_type": "secrets",
        "rule": "rotate credentials quarterly", "confidence": 9,
    }))
    rule_id = next(iter(server.store.rules))
    server.rbac.set_clearance(
        rule_id=rule_id, clearance=ClearanceLevel.RESTRICTED,
        allowed_agents=["agent"], allowed_roles=[], allowed_teams=[],
    )
    recall = _text(_run(server.call_tool("recall_memory", {"query": "rotate"})))
    assert "rotate credentials" in recall


def test_succession_capture_before_start_reports_failure(server):
    text = _text(_run(server.call_tool("succession", {
        "member": "jane", "role": "staff-eng", "action": "capture",
        "title": "why we chose postgres", "detail": "evaluated 3 options...",
    })))
    assert "Nothing Captured" in text
    assert "start" in text


def test_succession_full_flow_works(server):
    _run(server.call_tool("succession", {
        "member": "jane", "role": "staff-eng", "action": "start",
    }))
    captured = _text(_run(server.call_tool("succession", {
        "member": "jane", "role": "staff-eng", "action": "capture",
        "title": "why we chose postgres", "detail": "evaluated 3 options...",
        "importance": 9,
    })))
    assert "Captured" in captured and "Nothing" not in captured
    finalized = _text(_run(server.call_tool("succession", {
        "member": "jane", "role": "staff-eng", "action": "finalize",
    })))
    assert "postgres" in finalized.lower()


def test_first_call_injects_context_without_task(tmp_path):
    """The 'context pre-loaded on first tool call' promise — even when the
    first call has no task argument."""
    seed = create_loom_server(tmp_path)
    _run(seed.call_tool("teach", {
        "domain": "coding", "rule_type": "type_safety",
        "rule": "All public functions must have type hints", "confidence": 9,
    }))

    fresh = create_loom_server(tmp_path)  # new session, same project
    first = _text(_run(fresh.call_tool("get_stats", {})))
    assert "Top Reminders" in first or "AUTO_CONTEXT" in first


def test_error_in_handler_returns_message_not_crash(server):
    text = _text(_run(server.call_tool("teach", {})))  # missing required args
    assert "Error in tool 'teach'" in text


def test_unknown_tool_reports_cleanly(server):
    text = _text(_run(server.call_tool("does_not_exist", {})))
    assert "Unknown tool" in text


def test_observe_invalid_sensitivity_falls_back(server):
    text = _text(_run(server.call_tool("observe", {
        "context": "test", "content": "we always squash-merge to main",
        "sensitivity": "bogus-level",
    })))
    assert "Observed" in text


def test_onboard_accepts_all_documented_roles(server):
    from loom.onboarding.packs import ROLE_DOMAIN_MAP

    for role in ROLE_DOMAIN_MAP:
        text = _text(_run(server.call_tool("onboard", {"role": role})))
        assert "Unknown role" not in text, f"role rejected: {role}"

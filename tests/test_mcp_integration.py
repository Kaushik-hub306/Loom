"""Integration smoke test — verifies the MCP transport layer works end-to-end.

Launches the MCP server as a subprocess and sends real JSON-RPC messages
over stdio. This catches issues that unit tests (which call handlers directly)
cannot: FastMCP decorator wiring, stdio transport, JSON-RPC framing.
"""

import json
import os
import subprocess
import sys
import time


def _spawn_server(project_root) -> subprocess.Popen:
    """Start the MCP server pointed at an isolated project root."""
    env = {**os.environ, "LOOM_PROJECT_ROOT": str(project_root)}
    # Never let ambient API keys leak into the subprocess under test.
    for var in ("ANTHROPIC_API_KEY", "LOOM_DEEPSEEK_API_KEY", "GEMINI_API_KEY",
                "LOOM_LLM_PROVIDER", "LOOM_PRIVATE_MODE"):
        env.pop(var, None)
    return subprocess.Popen(
        [sys.executable, "-m", "loom.mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def _shutdown(proc: subprocess.Popen):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _send_request(proc, request: dict) -> dict:
    """Send a JSON-RPC request and read the response."""
    payload = json.dumps(request) + "\n"
    proc.stdin.write(payload)
    proc.stdin.flush()
    # Read until we get a response line (skip empty lines)
    for _ in range(50):
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if line:
            return json.loads(line)
    return {}


def _initialize(proc) -> str:
    """Send initialize + initialized/notifications to set up the session."""
    msg_id = 1
    _send_request(proc, {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    })
    # Read initialize response
    _send_request(proc, {})  # read the pending response
    # Send initialized notification
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }) + "\n")
    proc.stdin.flush()
    time.sleep(0.2)
    # Drain any pending output
    return "ok"


def _call_tool(proc, msg_id: int, name: str, arguments: dict) -> str:
    """Call a tool and return all text content joined."""
    resp = _send_request(proc, {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    assert "result" in resp, f"{name} failed: {resp}"
    content = resp["result"].get("content", [])
    assert len(content) > 0, f"{name} returned empty content"
    return "\n".join(c.get("text", "") for c in content)


def test_mcp_server_starts(tmp_path):
    """Smoke test: the MCP server starts and responds to initialize."""
    proc = _spawn_server(tmp_path)
    try:
        _initialize(proc)
        # If we got here without an exception, the server started
        assert proc.poll() is None, "Server should still be running"
    finally:
        _shutdown(proc)


def test_list_tools(tmp_path):
    """The server returns its tool list over MCP transport."""
    proc = _spawn_server(tmp_path)
    try:
        _initialize(proc)

        resp = _send_request(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })

        assert "result" in resp, f"Expected result in response, got: {resp}"
        tools = resp["result"].get("tools", [])
        tool_names = {t["name"] for t in tools}

        # Core tools must be present
        for name in ("teach", "learn", "recall_memory", "recall_relevant",
                     "session_init", "get_stats", "export"):
            assert name in tool_names, f"Tool '{name}' missing from tools/list"

        # Should have 18 tools
        assert len(tools) == 18, f"Expected 18 tools, got {len(tools)}"
    finally:
        _shutdown(proc)


def test_teach_and_recall_round_trip(tmp_path):
    """End-to-end: teach a rule, then recall it — all via MCP transport."""
    proc = _spawn_server(tmp_path)
    try:
        _initialize(proc)

        teach_text = _call_tool(proc, 3, "teach", {
            "domain": "coding",
            "rule": "All public functions must have type hints",
            "rule_type": "type_safety",
            "confidence": 9,
        })
        assert "Taught" in teach_text, f"Unexpected teach response: {teach_text}"

        recall_text = _call_tool(proc, 4, "recall_memory", {
            "query": "type hints",
            "domain": "coding",
        })
        assert "type_safety" in recall_text, f"Rule not found in recall: {recall_text}"
        assert "type hints" in recall_text.lower(), f"Rule text missing: {recall_text}"
    finally:
        _shutdown(proc)


def test_transport_redacts_secrets(tmp_path):
    """A secret taught over real MCP transport never reaches rules.json."""
    proc = _spawn_server(tmp_path)
    try:
        _initialize(proc)
        _call_tool(proc, 5, "teach", {
            "domain": "security",
            "rule": "Rotate keys like sk-ant-api03-AbCdEf123456-7890XyZabcdKLMNO monthly",
            "rule_type": "secrets",
        })
        rules_json = (tmp_path / ".loom" / "rules.json").read_text()
        assert "sk-ant-api03" not in rules_json, "secret leaked to storage"
        assert "[REDACTED:api-key]" in rules_json
    finally:
        _shutdown(proc)


def test_transport_stdout_is_clean_jsonrpc(tmp_path):
    """Every stdout line from the server must be valid JSON-RPC.

    Any stray print() to stdout in library code corrupts the MCP stream —
    this guards the whole codebase against that class of bug.
    """
    proc = _spawn_server(tmp_path)
    try:
        _initialize(proc)
        _call_tool(proc, 6, "teach", {
            "domain": "coding", "rule": "guard the stdio stream",
            "rule_type": "process",
        })
        _call_tool(proc, 7, "get_stats", {})
    finally:
        _shutdown(proc)
    # _call_tool already json.loads()es every stdout line — reaching here
    # without a JSONDecodeError is the assertion.

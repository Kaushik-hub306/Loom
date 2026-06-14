"""Integration smoke test — verifies the MCP transport layer works end-to-end.

Launches the MCP server as a subprocess and sends real JSON-RPC messages
over stdio. This catches issues that unit tests (which call handlers directly)
cannot: FastMCP decorator wiring, stdio transport, JSON-RPC framing.
"""

import json
import subprocess
import sys
import time
from pathlib import Path


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
    resp = _send_request(proc, {})  # read the pending response
    # Send initialized notification
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }) + "\n")
    proc.stdin.flush()
    time.sleep(0.2)
    # Drain any pending output
    return "ok"


def test_mcp_server_starts():
    """Smoke test: the MCP server starts and responds to initialize."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "loom.mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _initialize(proc)
        # If we got here without an exception, the server started
        assert proc.poll() is None, "Server should still be running"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_list_tools():
    """The server returns its tool list over MCP transport."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "loom.mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _initialize(proc)

        # Send tools/list
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
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_teach_and_recall_round_trip():
    """End-to-end: teach a rule, then recall it — all via MCP transport."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "loom.mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        # Use a temp dir for isolation
        env={**__import__("os").environ, "LOOM_PROJECT_ROOT": "/tmp/loom-test-integration"},
    )
    try:
        _initialize(proc)

        # Teach a rule
        resp = _send_request(proc, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "teach",
                "arguments": {
                    "domain": "coding",
                    "rule": "All public functions must have type hints",
                    "rule_type": "type_safety",
                    "confidence": 9,
                },
            },
        })

        assert "result" in resp, f"teach failed: {resp}"
        content = resp["result"].get("content", [])
        assert len(content) > 0, "teach returned empty content"
        teach_text = content[0].get("text", "")
        assert "Taught" in teach_text, f"Unexpected teach response: {teach_text}"

        # Recall the rule
        resp = _send_request(proc, {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "recall_memory",
                "arguments": {
                    "query": "type hints",
                    "domain": "coding",
                },
            },
        })

        assert "result" in resp, f"recall_memory failed: {resp}"
        content = resp["result"].get("content", [])
        assert len(content) > 0, "recall_memory returned empty content"
        recall_text = content[0].get("text", "")
        assert "type_safety" in recall_text, f"Rule not found in recall: {recall_text}"
        assert "type hints" in recall_text.lower(), f"Rule text missing: {recall_text}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        # Clean up test dir
        import shutil
        shutil.rmtree("/tmp/loom-test-integration", ignore_errors=True)

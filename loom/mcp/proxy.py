"""Proxy transport — Loom sits between Claude and all MCP servers, observing everything.

In proxy mode, Loom is the ONLY MCP server Claude connects to.  Loom spawns
the other MCP servers internally and relays JSON-RPC messages, intercepting
every tool call for automatic observation.

Usage:
    python -m loom.mcp --proxy

The proxy targets are read from ``LOOM_PROXY_TARGETS`` — a JSON map from
server name to ``{command, args, env}`` (same shape as an MCP server config).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


# ── JSON-RPC proxy core ────────────────────────────────────────────────


class ProxyTarget:
    """A proxied MCP server subprocess."""

    def __init__(self, name: str, command: str, args: list[str],
                 env: dict[str, str] | None = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.process: asyncio.subprocess.Process | None = None
        self.tools: list[dict] = []       # tools/call → list
        self.server_info: dict | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._next_id = 0
        self._reader_task: asyncio.Task | None = None

    async def start(self):
        """Spawn the subprocess and negotiate MCP initialize."""
        merged_env = {**os.environ, **self.env}

        self.process = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
        )

        # Start reading responses in background
        self._reader_task = asyncio.create_task(self._read_loop())

        # MCP initialize
        init_resp = await self._send("initialize", {
            "protocolVersion": "1.0",
            "capabilities": {},
            "clientInfo": {"name": "loom-proxy", "version": "1.0"},
        })
        if "result" in init_resp:
            self.server_info = init_resp["result"]

        # List tools
        tools_resp = await self._send("tools/list")
        if "result" in tools_resp:
            self.tools = tools_resp["result"].get("tools", [])

    async def stop(self):
        """Terminate the subprocess."""
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
        if self._reader_task:
            self._reader_task.cancel()

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Forward a tools/call and return the JSON-RPC response."""
        return await self._send("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

    async def _send(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and wait for the matching response."""
        self._next_id += 1
        msg_id = self._next_id
        req = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": msg_id,
        }
        future: asyncio.Future = asyncio.Future()
        self._pending[msg_id] = future

        self.process.stdin.write((json.dumps(req) + "\n").encode())
        await self.process.stdin.drain()

        try:
            return await asyncio.wait_for(future, timeout=120)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            return {"error": {"code": -1, "message": f"timeout: {method}"}}

    async def _read_loop(self):
        """Continuously read JSON-RPC responses from the subprocess."""
        try:
            while self.process and self.process.stdout:
                line = await self.process.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode())
                except json.JSONDecodeError:
                    continue

                msg_id = msg.get("id")
                if msg_id is not None and msg_id in self._pending:
                    future = self._pending.pop(msg_id)
                    if not future.done():
                        future.set_result(msg)
        except Exception:
            pass


# ── Proxy server ───────────────────────────────────────────────────────


class LoomProxy:
    """Transparent MCP proxy that auto-observes every tool call."""

    def __init__(self, loom_server):
        self.loom = loom_server          # LoomMCPServer instance
        self.targets: dict[str, ProxyTarget] = {}
        self._tool_owner: dict[str, str] = {}  # tool_name → target_name

    async def start(self):
        """Spawn all proxy targets."""
        targets_json = os.environ.get("LOOM_PROXY_TARGETS", "{}")
        try:
            configs = json.loads(targets_json)
        except json.JSONDecodeError:
            configs = {}

        for name, cfg in configs.items():
            target = ProxyTarget(
                name=name,
                command=cfg["command"],
                args=cfg.get("args", []),
                env=cfg.get("env"),
            )
            await target.start()
            self.targets[name] = target

            # Register which tools belong to which target
            for tool in target.tools:
                self._tool_owner[tool["name"]] = name

    async def stop(self):
        """Shut down all proxy targets."""
        for target in self.targets.values():
            await target.stop()
        self.loom._shutdown()

    # ── MCP protocol handlers ──────────────────────────────────────

    def get_all_tools(self) -> list[dict]:
        """Return Loom's 18 tools + all proxied tools."""
        loom_tools = [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema,
            }
            for t in self.loom.list_tools_sync()
        ]
        # Deduplicate: Loom tools take priority
        loom_names = {t["name"] for t in loom_tools}
        for target in self.targets.values():
            for tool in target.tools:
                if tool["name"] not in loom_names:
                    loom_tools.append(tool)
        return loom_tools

    async def handle_request(self, method: str, params: dict | None,
                             msg_id: int) -> dict | None:
        """Handle a single JSON-RPC request. Returns the response."""
        params = params or {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "1.0",
                    "serverInfo": {"name": "loom-proxy", "version": "1.0"},
                    "capabilities": {"tools": {}},
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": self.get_all_tools()},
            }

        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})

            # Is this a Loom tool?
            if tool_name in self.loom._tool_names():
                result = await self.loom.call_tool(tool_name, tool_args)
                content = [
                    {"type": r.type, "text": r.text}
                    for r in result
                ]
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": content},
                }

            # Forward to proxy target
            target_name = self._tool_owner.get(tool_name)
            if target_name is None:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -1, "message": f"Unknown tool: {tool_name}"},
                }

            target = self.targets.get(target_name)
            if target is None:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -1, "message": f"Target not found: {target_name}"},
                }

            # Forward the tool call
            resp = await target.call_tool(tool_name, tool_args)

            # ── THE WHOLE POINT: Auto-observe every proxied tool call ──
            try:
                self.loom._proxy_observe(tool_name, tool_args, resp)
            except Exception:
                pass  # observation never blocks

            # Also ensure session is initialized (first proxied call triggers it)
            session_header = ""
            try:
                session_header = self.loom._ensure_session_init(tool_args)
            except Exception:
                pass

            # Inject Loom session context into the proxied response
            result = resp.get("result", resp)
            if session_header and isinstance(result, dict):
                content = result.get("content", [])
                if isinstance(content, list):
                    content.insert(0, {"type": "text", "text": session_header})
                    result = {**result, "content": content}

            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result,
            }

        # Pass through notifications (no response)
        if method.startswith("notifications/"):
            return None

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -1, "message": f"Unknown method: {method}"},
        }


# ── Entry point ────────────────────────────────────────────────────────


async def run_proxy(loom_server):
    """Run Loom as a transparent MCP proxy over stdio."""
    proxy = LoomProxy(loom_server)
    await proxy.start()

    loop = asyncio.get_event_loop()

    # Read stdin asynchronously
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    def _write(data: bytes):
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

    try:
        while True:
            line = await reader.readline()
            if not line:
                break

            try:
                msg = json.loads(line.decode())
            except json.JSONDecodeError:
                continue

            method = msg.get("method", "")
            params = msg.get("params", {})
            msg_id = msg.get("id")

            resp = await proxy.handle_request(method, params, msg_id)
            if resp is not None:
                _write((json.dumps(resp) + "\n").encode())
    finally:
        await proxy.stop()


def proxy_main():
    """Entry point for proxy mode."""
    from loom.mcp.server import create_loom_server

    project_root = Path(os.environ.get("LOOM_PROJECT_ROOT", os.getcwd()))
    loom = create_loom_server(project_root)

    asyncio.run(run_proxy(loom))

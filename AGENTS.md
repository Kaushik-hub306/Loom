# Loom — Agent & Contributor Guide

Loom (`loom-learn` on PyPI) is an MCP server + CLI that gives AI agents a
shared, persistent memory layer. This file orients agents and contributors
working on the codebase itself.

## Commands

```bash
pip install -e ".[dev]"        # install with dev tools
python -m pytest               # run all 159 tests (hermetic — no API keys needed)
ruff check loom/ tests/ conftest.py   # lint (must be clean)
mypy loom/                     # type check (must be clean)
python -m build                # build sdist + wheel
```

## Architecture

- `loom/mcp/server.py` — the MCP server. ALL tools must dispatch through
  `LoomMCPServer.call_tool()` — that is where the hook layer lives (auto
  session-init, auto-observe, secret redaction, private-mode gate, error
  wrapping). Never wire a FastMCP tool directly to a `_handle_*` method.
- `loom/mcp/proxy.py` — proxy mode (`python -m loom.mcp --proxy`); forwards
  to servers configured in `LOOM_PROXY_TARGETS`.
- `loom/engine/` — rule store, org store, auto-observer, context loader,
  timeline, retention/decay, extractors.
- `loom/llm/` — pluggable providers (Anthropic, DeepSeek, Gemini). Shared
  prompt + JSON parsing live in `base.py`.
- `loom/security/` — redactor (runs on EVERY write path), RBAC, private
  mode, audit, integrity.
- `loom/storage/` — `jsonio.py` (atomic writes, locks, corruption-safe
  loads — use it for ALL JSON persistence), Postgres backend + adapters.
- `loom/onboarding/packs.py` — the SINGLE source of truth for the
  role → domain map. Never redefine role maps elsewhere.

## Hard rules

1. **Never `print()` to stdout in library/server code** — this is an MCP
   stdio server; stdout is the JSON-RPC stream. Diagnostics go to
   `sys.stderr`. A transport test enforces this.
2. **All JSON persistence goes through `loom/storage/jsonio.py`** — atomic
   write + lock + quarantine-on-corruption. Never `Path.write_text()` a
   store file directly.
3. **Every write path must redact** — anything user-provided that can reach
   storage passes through `loom.security.redactor.redact_text` (the server
   handlers use `self._redact`).
4. **Timestamps**: produce with `loom.timeutil.utc_now_iso()`, parse with
   `loom.timeutil.parse_iso_utc()` (naive inputs are assumed UTC — never
   compare naive with aware datetimes).
5. **Tests must stay hermetic** — `conftest.py` clears ambient env vars;
   use `tmp_path`, never a shared /tmp path or repo-relative state.
6. Keep `requires-python`, the `loom doctor` Python check, and README
   requirements in sync (currently 3.10+).
7. Version lives in BOTH `loom/__init__.py` and `pyproject.toml`; the
   publish workflow rejects tags that don't match both.

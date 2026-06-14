# Changelog

All notable changes to Loom will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-06-14

### Added
- 18 MCP tools: learn, teach, reflect, recall_memory, recall_relevant, observe, export, export_timeline, get_stats, store_outcome, onboard, succession, amplify, retain, set_clearance, timeline, federate, session_init
- Auto session_init hook — context injected on first tool call, no manual action needed
- Auto observe hook — teach/learn/amplify calls auto-captured as observations
- Auto flush — buffered observations extracted into rules on session end
- Onboarding packs — role-based onboarding for 16 roles (backend-engineer, frontend-dev, etc.)
- Succession capture — three-step workflow (start → capture → finalize) for departing members
- Coaching amplification — scale top performer patterns across the team
- Permanent retention — mark rules as permanent org knowledge, never decay
- Per-observation RBAC — 5 clearance levels (public, internal, confidential, restricted, secret)
- Auditable timeline — append-only org history, queryable by domain/project/agent
- Cross-project federation — ingest rules from other projects
- Multi-provider LLM extraction — Anthropic, DeepSeek, Gemini (auto-detect from env vars)
- Free keyword extraction — works without any API key
- Dual storage backends — local JSON (default, zero config) + Postgres cloud (via Supabase)
- `loom cloud setup` — provision a shared Supabase database for teams
- `loom setup` — generate ready-to-paste Claude Desktop config
- `loom doctor` — health checks for Python, Loom, storage, domains, LLM, MCP
- `loom doctor --preflight` — validates MCP config chain before restarting Claude
- `loom init` — alias for `loom setup`
- Proxy mode (`--proxy` flag) — Loom as single MCP entry point, observes all tool calls
- Security redactor — auto-strips API keys, tokens, emails, IPs from observations
- Secret cleanup — prompts user to add config file to .gitignore
- Credential safety warning on `loom cloud setup`
- GitHub Actions CI — test matrix (Python 3.10/3.11/3.12) + PyPI publish on tag

### Changed
- Stderr logging on background failures — auto-observer, timeline, coaching, onboarding errors are now visible in Claude Desktop logs
- Actionable error messages — PermissionError, ImportError, and OSError now tell the user what to do
- Signal handlers — SIGTERM/SIGINT now properly exit the process
- SQL injection hardened in Postgres `get_domain_stats`

### Fixed
- Proxy mode now correctly injects session context into proxied responses
- Migration SQL files now included in pip package
- Dead code removed from `_handle_recall_relevant`

## [0.2.0] — 2026-06 (unreleased / internal)

### Added
- LLM extraction with pluggable providers (Anthropic, DeepSeek, Gemini)
- Auto-observer with observation buffer
- Context loader for smart auto-recall by task and role
- Session manager (create, track, cleanup lifecycle)
- CLI: `loom setup` and `loom doctor` commands
- Security layer: PII/secret redactor, private mode, integrity verification, audit log, access control

## [0.1.0] — 2026-05 (unreleased / internal)

### Added
- Core rule store with JSON persistence
- Domain extractor with 8 domain YAML configs (coding, style, architecture, process, testing, security, documentation, general)
- Keyword-based rule extraction
- Basic MCP server loop with FastMCP
- Confidence scoring and decay management

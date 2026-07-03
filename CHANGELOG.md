# Changelog

All notable changes to Loom will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] — 2026-07-03

Production-readiness release: a full audit of every module, with fixes for
several bugs that silently disabled headline features. Upgrading is strongly
recommended.

### Fixed — critical
- **Auto-hooks now actually fire.** The standard `python -m loom.mcp` entry
  point wired tools directly to raw handlers, bypassing the hook layer
  entirely — auto session-init, auto-observation, and secret redaction never
  ran outside proxy mode. Every tool now routes through the hook layer.
- **LLM extraction was broken for all three providers.** The shared prompt
  builder referenced an undefined variable (`NameError` on every call),
  the Anthropic call passed an invalid `output_config` parameter, and the
  DeepSeek call used an unsupported `json_schema` response format. All
  fixed; extraction failures are now logged to stderr instead of being
  silently swallowed.
- **A single malformed entry no longer destroys the rule store.** Loading a
  rules file with one bad entry used to reset the store to empty in memory —
  and the next save made the loss permanent. Loads now skip bad entries
  individually, and corrupt files are quarantined (`*.corrupt-<timestamp>`),
  never silently discarded.
- **All store writes are now atomic** (temp file + fsync + rename) and taken
  under an advisory file lock — a crash mid-write or two concurrent Loom
  processes can no longer corrupt `rules.json` and friends.
- **RBAC clearance is now enforced at read time.** `set_clearance` used to
  store permissions that no read path ever checked. `recall_memory`,
  `recall_relevant`, `export`, `timeline`, `export_timeline`, and `onboard`
  now filter rules by the agent's identity (`LOOM_AGENT_ID` /
  `LOOM_AGENT_ROLE` / `LOOM_AGENT_TEAMS`).
- **`LOOM_PRIVATE_MODE=1` is now wired.** It blocks all write tools (teach,
  learn, observe, …) while keeping read tools available. Previously it did
  nothing.
- **Secrets are now redacted on every write path.** `teach`, `learn`,
  `reflect`, `amplify`, and `succession` could previously store raw API keys.
  The redactor also gained patterns it embarrassingly lacked: Anthropic
  `sk-ant-`, OpenAI `sk-proj-`, Stripe `sk_live_`, Slack `xox*`, GitHub
  fine-grained PATs, GitLab, Google, SendGrid, npm, PyPI, Hugging Face,
  JWTs, bearer tokens, connection-string passwords, and `key=value`
  credential assignments.
- **Redactor denial-of-service fixed.** The email pattern went quadratic on
  large inputs (a 200 KB observation could stall the server for minutes).
  All patterns now use bounded quantifiers.
- **`succession(action="capture")` before `start` no longer reports a false
  success** while silently discarding the captured knowledge.
- **`timeline`/`export_timeline` with a limit returned the OLDEST entries**
  instead of the most recent. "Key Recent Decisions" in onboarding packs was
  showing ancient history.
- **Retention/decay policies now actually run** (once per session). The
  entire decay engine was dead code — no rule ever decayed.
- Auto-observation calls passed an invalid `source=` argument (crashed and
  was silently swallowed); rule-ID slug truncation silently merged distinct
  rules (now disambiguated with a content hash); naive timestamps in stored
  data no longer raise `TypeError`; Windows crash in timeline markdown
  export (`%-d` is not portable); `loom doctor` printed a broken
  f-string placeholder and required Python 3.11 while the package supports
  3.10; four user-facing messages recommended installing the wrong package
  (`loom-agent` instead of `loom-learn`); proxy read-loop failures now mark
  the target dead and fail fast instead of hanging every call for 120 s.

### Added
- `loom version` command.
- `LOOM_LLM_MODEL` to override the extraction model, `LOOM_AGENT_ID` /
  `LOOM_AGENT_ROLE` / `LOOM_AGENT_TEAMS` for RBAC identity.
- Timeouts (30 s) on all LLM provider calls.
- First-call context injection even without a task argument — top
  conventions are pre-loaded on the session's first tool call.
- MIT license, `py.typed` marker, complete PyPI metadata, CI workflow
  (ruff + mypy + pytest on 3.10–3.13 + macOS), PyPI Trusted Publishing.
- 80 new tests (159 total): redactor formats + ReDoS guard, storage
  corruption/atomicity, hook layer, RBAC enforcement, private mode, LLM
  prompt/parser contracts, MCP transport round-trips including a
  stdout-cleanliness guard. The suite is fully hermetic.

### Changed
- Default Anthropic model is now `claude-sonnet-5` (override with
  `LOOM_LLM_MODEL`).
- The rule store is cached with staleness detection instead of re-reading
  and re-parsing the whole JSON file on every access.
- Role → domain mapping single-sourced (23 roles); the `onboard` tool now
  accepts every role that pack generation supports.
- Unknown `LOOM_LLM_PROVIDER` values warn on stderr instead of silently
  disabling LLM extraction.
- Proxy targets (`LOOM_PROXY_TARGETS`) are now documented, validated, and
  a single broken target no longer prevents startup.

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

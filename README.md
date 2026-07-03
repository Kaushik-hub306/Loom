<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?style=for-the-badge&logo=python" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/protocol-MCP-green?style=for-the-badge" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/version-0.4.0-orange?style=for-the-badge" alt="Version 0.4.0">
  <img src="https://img.shields.io/badge/license-MIT-lightgrey?style=for-the-badge" alt="MIT License">
</p>

<h1 align="center">🧠 Loom</h1>
<p align="center"><strong>Shared memory for AI agents — what any of them learns belongs to your whole org.</strong></p>
<p align="center">One <code>pip install</code>. Paste a JSON block. Every agent gets smarter with every interaction.</p>

---

## Quick Start

### Claude Desktop

```bash
pip install loom-learn    # one command
loom init                 # prints config → paste into Claude Desktop
# restart Claude Desktop  # done
```

### Claude Code (CLI)

Add to `~/.claude/settings.json` or your project's `.claude/settings.json`:

```json
{
  "mcpServers": {
    "loom": {
      "command": "python3",
      "args": ["-m", "loom.mcp"],
      "env": {
        "LOOM_PROJECT_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

Then restart Claude Code. That's it — Loom auto-injects context on your first tool call.

Loom works for free with keyword extraction. To use an LLM for smarter extraction, add your API key to the `env` block:

```json
"env": {
  "LOOM_PROJECT_ROOT": "/your/project/path",
  "ANTHROPIC_API_KEY": "sk-ant-..."
}
```

DeepSeek or Gemini? Just swap the key — Loom auto-detects the provider.

Verify:
```bash
loom doctor              # local health checks
loom doctor --preflight  # validates MCP config before restart
```

---

## What Loom Does

Loom is your team's shared memory layer. Every agent reads from and writes to the same store. When one agent discovers a convention, every agent knows it. When a senior engineer shares why a pattern matters, every new hire's agent gets that context on day one.

| Capability | What it does |
|-----------|-------------|
| **Auto-learn** | Hooks fire automatically — no agent needs to remember to call anything |
| **Auto-recall** | Relevant context injected on first tool call — agent sees Top Reminders, domain rules, coaching, org-wide knowledge |
| **Teach** | Explicitly inject conventions — agent sees a pattern, teaches it, team benefits |
| **Onboarding** | New hire's agent already knows the org — 23 built-in roles, from backend to support |
| **Succession** | Knowledge survives turnover — capture tribal knowledge before someone leaves |
| **Coaching** | Top performer patterns scale — amplify critical rules with context on why they matter |
| **Retention** | Tiered retention with real decay — permanent org knowledge never expires, transient patterns fade |
| **RBAC** | Five clearance levels, enforced on every read path — public, internal, confidential, restricted, secret |
| **Timeline** | Auditable org history — query everything learned, by domain, project, or agent |
| **Federation** | Cross-project knowledge — ingest rules from other projects into the org store |
| **Redactor** | Auto-strips secrets on every write path — API keys, tokens, credentials, emails, IPs never reach storage |
| **Private mode** | `LOOM_PRIVATE_MODE=1` blocks all memory writes while keeping recall available |
| **Cloud backend** | Postgres via Supabase — `loom cloud setup` provisions a shared database for teams |
| **Proxy mode** | Loom as single MCP entry point — observes every forwarded tool call |

---

## 18 MCP Tools

### Learning
| Tool | Description |
|------|-------------|
| `teach` | Teach a rule directly — auto-captured |
| `learn` | Learn from observation — auto-captured |
| `reflect` | Extract patterns from multiple observations |

### Recall
| Tool | Description |
|------|-------------|
| `recall_relevant` | Auto-find context for your current task |
| `recall_memory` | Search learned conventions |
| `session_init` | Pre-load context — fires automatically |
| `observe` | Passive background capture — fires automatically |

### Team Knowledge
| Tool | Description |
|------|-------------|
| `onboard` | Generate onboarding pack for any role |
| `succession` | Capture departing member's knowledge |
| `amplify` | Amplify coaching across the team |
| `retain` | Mark a rule for permanent retention |
| `set_clearance` | Per-rule access control |
| `timeline` | Query the auditable org history |
| `federate` | Import rules from other projects |

### Utilities
| Tool | Description |
|------|-------------|
| `export` | Export rules (markdown, JSON, compact) |
| `export_timeline` | Export full org history |
| `get_stats` | Statistics by domain, confidence, retention |
| `store_outcome` | Store PR review outcome |

---

## Dual Backend

**Local (free, default):** Everything stored in `.loom/` — JSON files with atomic, crash-safe writes. Zero config. Commit `rules.json` and `conventions.md` to git so your team shares conventions.

**Cloud (teams):** `loom cloud setup` provisions a Supabase Postgres database. Every agent in your org reads and writes from the same store. Real-time shared memory.

```
Free (JSON):                        Cloud (Postgres):
loom init                           loom cloud setup
→ .loom/ on disk                    → Supabase database
→ commit to git                     → team shares in real-time
→ zero cost                         → managed, scalable
```

---

## What Loom Creates

```
your-project/
└── .loom/
    ├── domains/           # 8 domain YAML configs (coding, style, architecture,
    │                      #   process, testing, security, documentation, general)
    ├── rules.json         # Learned rules with confidence scores
    ├── conventions.md     # Human-readable conventions doc
    ├── timeline.jsonl     # Auditable, append-only org history
    ├── retention.json     # Permanent-to-transient retention policies
    ├── archive.json       # Archived rules (never lost)
    ├── permissions.json   # Per-observation RBAC
    ├── onboarding/        # Role-based onboarding packs
    ├── succession/        # Departing member knowledge capture
    └── coaching/          # Coaching amplifications
```

A `.loom/.gitignore` is generated automatically so sensitive files (tokens, audit logs, permissions) never reach git while `rules.json` and `conventions.md` stay shareable.

---

## CLI Reference

```bash
loom init              # Generate config for Claude Desktop
loom setup             # Same as init
loom doctor            # Health check — Python, Loom, storage, LLM, MCP
loom doctor --preflight # Validate MCP config before restart
loom cloud setup       # Provision Supabase database for team
loom version           # Print the installed version
```

### Config locations

| Client | Config file |
|--------|-----------|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) |
| Claude Code | `~/.claude/settings.json` or `.claude/settings.json` |
| Cursor | `~/.cursor/mcp.json` |
| Codex CLI | `~/.codex/config.toml` or `~/.codex/config.json` |

---

## Example Session

```
[Agent starts coding]

First tool call → auto session_init fires:

<!-- LOOM:AUTO_CONTEXT -->
## 🔍 Relevant Conventions (from Loom)

### ⚡ Top Reminders
1. All public functions must have type hints (9/10)
2. Use async/await for all I/O operations (8/10)
3. Every new endpoint needs a test (9/10)

### By Domain
#### coding
- type_safety (9/10): All public functions must have type hints
- error_handling (8/10): Use custom exception classes

### 📢 Coaching Amplifications
- "Use async/await for all I/O" — Sarah Chen (Staff Eng)
  This is critical because sync I/O caused 3 production incidents...

### 🌐 Org-Wide Knowledge
- [api-service] error_handling: Always include request IDs
- [shared-infra] process: Squash commits before merging

[Agent continues. Every teach/learn/amplify auto-observed.
 Session ends → auto-flush extracts all observations into rules.]
```

---

## Proxy Mode

Run Loom as the **only** MCP server your client connects to. Loom spawns your other MCP servers internally, relays every JSON-RPC message, and observes every forwarded tool call — nothing to teach, nothing to remember.

```bash
python3 -m loom.mcp --proxy
```

Configure the servers to forward via `LOOM_PROXY_TARGETS` (same shape as an MCP client's server config):

```json
{
  "mcpServers": {
    "loom": {
      "command": "python3",
      "args": ["-m", "loom.mcp", "--proxy"],
      "env": {
        "LOOM_PROJECT_ROOT": "/your/project",
        "LOOM_PROXY_TARGETS": "{\"github\": {\"command\": \"npx\", \"args\": [\"-y\", \"@modelcontextprotocol/server-github\"], \"env\": {}}}"
      }
    }
  }
}
```

Loom's 18 tools plus every forwarded tool appear as one flat tool list. A target that crashes is marked dead and fails fast — it never hangs your session.

---

## Security

- **Redaction on every write path.** Before anything reaches storage, Loom strips: Anthropic/OpenAI–style keys (`sk-ant-…`, `sk-proj-…`, `sk-…`), Stripe (`sk_live_…`), AWS access + secret keys, GitHub/GitLab tokens (classic and fine-grained), Slack, Google, SendGrid, npm, PyPI, Hugging Face tokens, JWTs, bearer tokens, PEM private-key blocks, connection-string passwords, generic `api_key=…` assignments, emails, and IPv4 addresses.
- **RBAC enforced at read time.** `set_clearance` restricts who sees a rule; `recall_memory`, `recall_relevant`, `export`, `timeline`, and `onboard` all filter by the agent identity set via `LOOM_AGENT_ID` / `LOOM_AGENT_ROLE` / `LOOM_AGENT_TEAMS`.
- **Private mode.** `LOOM_PRIVATE_MODE=1` blocks every write tool while read tools keep working.
- **Crash-safe storage.** Atomic writes (temp file + fsync + rename) under advisory file locks; corrupt files are quarantined for recovery, never silently discarded.

Found a vulnerability? See [SECURITY.md](SECURITY.md).

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOOM_PROJECT_ROOT` | No | `$PWD` | Where to create `.loom/` |
| `LOOM_STORAGE_BACKEND` | No | `json` | `json` or `postgres` |
| `LOOM_DATABASE_URL` | No | — | Postgres connection string |
| `LOOM_ORG_STORE` | No | `.loom/org-store.json` | Shared org-wide memory path |
| `ANTHROPIC_API_KEY` | No | — | Anthropic LLM extraction |
| `LOOM_DEEPSEEK_API_KEY` | No | — | DeepSeek LLM extraction |
| `GEMINI_API_KEY` | No | — | Gemini LLM extraction |
| `LOOM_LLM_PROVIDER` | No | auto-detect | `anthropic`, `deepseek`, or `gemini` |
| `LOOM_LLM_MODEL` | No | provider default | Override the extraction model ID |
| `LOOM_PRIVATE_MODE` | No | `0` | `1` blocks all memory writes |
| `LOOM_AGENT_ID` | No | `agent` | Identity for RBAC checks |
| `LOOM_AGENT_ROLE` | No | `member` | Role for RBAC checks |
| `LOOM_AGENT_TEAMS` | No | — | Comma-separated teams for RBAC checks |
| `LOOM_PROXY_TARGETS` | No | — | JSON map of MCP servers to forward (proxy mode) |
| `LOOM_DB_POOL_MIN` | No | `2` | Postgres pool minimum connections |
| `LOOM_DB_POOL_MAX` | No | `20` | Postgres pool maximum connections |

---

## Requirements

| Requirement | Why |
|-------------|-----|
| **Python 3.10+** | Type hint syntax, stdlib improvements |
| **MCP-compatible client** | Claude Desktop, Claude Code, Cursor |
| **LLM API key (optional)** | Anthropic, DeepSeek, or Gemini. Free keyword extraction by default. |

---

## Troubleshooting

```bash
loom doctor              # catches most issues
loom doctor --preflight  # validates full MCP chain
```

Preflight checks: Python path in config exists, Loom is importable, MCP config is valid JSON, storage path is writable, MCP module loads without errors. Exits 0 on all green, 1 with specific fix instructions on any failure.

---

## Contributing

Bug reports, feature ideas, and PRs are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/Kaushik-hub306/Loom.git && cd Loom
pip install -e ".[dev]"
python -m pytest          # 159 tests
ruff check loom/ tests/   # lint
mypy loom/                # types
```

## License

[MIT](LICENSE)

---

<p align="center">
  <sub>Built for teams that want their AI agents to get smarter with every interaction — and never forget.</sub>
</p>

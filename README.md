<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?style=for-the-badge&logo=python" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/protocol-MCP-green?style=for-the-badge" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/version-0.3.0-orange?style=for-the-badge" alt="Version 0.3.0">
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
| **Onboarding** | New hire's agent already knows the org — roles for 16 positions, from backend to support |
| **Succession** | Knowledge survives turnover — capture tribal knowledge before someone leaves |
| **Coaching** | Top performer patterns scale — amplify critical rules with context on why they matter |
| **Retention** | Permanent org knowledge never decays — mark foundational rules as permanent |
| **RBAC** | Five clearance levels — public, internal, confidential, restricted, secret |
| **Timeline** | Auditable org history — query everything learned, by domain, project, or agent |
| **Federation** | Cross-project knowledge — ingest rules from other projects into the org store |
| **Redactor** | Auto-strips secrets — API keys, tokens, emails, IPs never reach storage |
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

**Local (free, default):** Everything stored in `.loom/` — JSON files. Zero config. Commit `rules.json` and `conventions.md` to git so your team shares conventions.

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

---

## CLI Reference

```bash
loom init              # Generate config for Claude Desktop
loom setup             # Same as init
loom doctor            # Health check — Python, Loom, storage, LLM, MCP
loom doctor --preflight # Validate MCP config before restart
loom cloud setup       # Provision Supabase database for team
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

---

## Requirements

| Requirement | Why |
|-------------|-----|
| **Python 3.10+** | Type hint syntax, stdlib improvements |
| **MCP-compatible client** | Claude Desktop, Code, Cursor |
| **LLM API key (optional)** | Anthropic, DeepSeek, or Gemini. Free keyword extraction by default. |

---

## Troubleshooting

```bash
loom doctor              # catches most issues
loom doctor --preflight  # validates full MCP chain
```

Preflight checks: Python path in config exists, Loom is importable, MCP config is valid JSON, storage path is writable, MCP module loads without errors. Exits 0 on all green, 1 with specific fix instructions on any failure.

---

<p align="center">
  <sub>Built for teams that want their AI agents to get smarter with every interaction — and never forget.</sub>
</p>

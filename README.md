<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/protocol-MCP-green?style=for-the-badge" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/license-MIT-purple?style=for-the-badge" alt="MIT License">
  <img src="https://img.shields.io/badge/version-0.3.0-orange?style=for-the-badge" alt="Version 0.3.0">
</p>

<h1 align="center">🧠 Loom</h1>
<p align="center"><strong>Shared learning for AI agents — what any of them learns belongs to your whole org</strong></p>
<p align="center">An MCP server that observes, learns, and remembers conventions from everything your AI agents do — making every agent smarter over time.</p>

---

## ✨ What Loom Does

Loom is the shared memory layer for AI agents. Every agent reads from and writes to a single store. Institutional knowledge compounds across your agent fleet rather than being siloed within individual sessions.

**New in this release:**
- **Auto session_init** — context is injected on the first tool call. The agent never needs to remember.
- **Auto observe** — teach, learn, amplify, and succession calls are auto-captured as observations.
- **Multi-provider LLM extraction** — Anthropic, DeepSeek, Gemini. Or free keyword extraction by default.

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **An MCP client** (Claude Desktop, Claude Code, Cursor, any MCP host)

### Install

```bash
git clone https://github.com/Kaushik-hub306/loom.git
cd loom
pip install -e .
```

### Configure Your MCP Client

**Claude Desktop (macOS):** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Claude Desktop (Windows):** `%APPDATA%\Claude\claude_desktop_config.json`

**Claude Code CLI:** `.mcp.json` in your project root

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

That's it. Restart your client. Loom auto-creates `.loom/` on first use.

---

## 🤖 LLM-Powered Extraction (Optional)

Loom uses **keyword extraction by default** — zero cost, zero config, works offline. Add an API key for smarter LLM-powered extraction that understands context and abstracts patterns:

### Anthropic (Claude)

```json
"env": {
  "LOOM_PROJECT_ROOT": "/path/to/your/project",
  "ANTHROPIC_API_KEY": "sk-ant-..."
}
```

### DeepSeek

```json
"env": {
  "LOOM_PROJECT_ROOT": "/path/to/your/project",
  "LOOM_LLM_PROVIDER": "deepseek",
  "LOOM_DEEPSEEK_API_KEY": "sk-..."
}
```

### Gemini

```json
"env": {
  "LOOM_PROJECT_ROOT": "/path/to/your/project",
  "LOOM_LLM_PROVIDER": "gemini",
  "GEMINI_API_KEY": "..."
}
```

Loom auto-detects which provider to use. If no key is set, keyword extraction runs free. You can switch providers any time by changing the env vars — no code changes.

---

## 🪝 How Hooks Work

Loom doesn't wait for the agent to remember to call tools. Two hooks fire automatically:

| Hook | When It Fires | What Happens |
|------|--------------|--------------|
| **Auto session_init** | First tool call of the session | ContextLoader finds all relevant conventions and injects them into the agent's context |
| **Auto observe** | Every `teach`, `learn`, `reflect`, `amplify`, `retain`, `set_clearance`, `succession`, `federate` call | The tool call is recorded as an observation in the buffer |
| **Auto flush** | When the buffer hits threshold, or on process exit | All observations are extracted into rules and written to `.loom/rules.json` |

The agent sees `<!-- LOOM:AUTO_CONTEXT -->` followed by Top Reminders, domain rules, coaching amplifications, and org-wide knowledge — injected automatically. No manual `session_init` call required.

**Tool division:**

| Auto (hooks guarantee) | Explicit (agent decides) |
|------------------------|-------------------------|
| `session_init` | `teach` |
| `observe` | `recall_memory` |
| `learn` | `export`, `export_timeline` |
| `reflect` | `get_stats` |
| `recall_relevant` | `onboard`, `succession` |
| | `amplify`, `retain` |
| | `set_clearance`, `timeline` |
| | `federate`, `store_outcome` |

---

## 🔌 18 MCP Tools

### Core Learning
| Tool | Description |
|------|-------------|
| `learn` | Learn from observation — auto-captured by hooks |
| `teach` | Teach a rule directly — auto-captured by hooks |
| `reflect` | Reflect on completed work — auto-captured by hooks |

### Recall
| Tool | Description |
|------|-------------|
| `recall_relevant` | Auto-recall everything relevant to a task |
| `recall_memory` | Search learned conventions |
| `session_init` | Pre-load context at session start — fires automatically |
| `observe` | Passive observation — fires automatically |

### Glen-Level Features
| Tool | Description |
|------|-------------|
| `onboard` | Generate onboarding pack for a new team member |
| `succession` | Capture departing member's knowledge |
| `amplify` | Amplify coaching across the team |
| `retain` | Mark a rule for permanent retention |
| `set_clearance` | Set per-observation access control (public → secret) |
| `timeline` | Query the auditable organization timeline |
| `federate` | Ingest rules from other projects |

### Essentials
| Tool | Description |
|------|-------------|
| `export` | Export rules (markdown, JSON, compact) |
| `export_timeline` | Export full org history |
| `get_stats` | Statistics including org-wide and retention data |
| `store_outcome` | Store PR review outcome (backward compat) |

---

## 📂 What Loom Creates

```
your-project/
├── .loom/
│   ├── domains/
│   │   ├── coding.yml          # Software engineering conventions
│   │   ├── style.yml           # Formatting & style conventions
│   │   ├── architecture.yml    # Design patterns & module structure
│   │   ├── process.yml         # Git workflow, CI/CD, review norms
│   │   ├── testing.yml         # Testing conventions & frameworks
│   │   ├── security.yml        # Security patterns & practices
│   │   ├── documentation.yml   # Docs, READMEs, API docs
│   │   └── general.yml         # Catch-all preferences & best practices
│   ├── rules.json              # Learned rules with confidence scores
│   ├── conventions.md          # Human-readable rules doc
│   ├── timeline.jsonl          # Auditable org history (append-only)
│   ├── retention.json          # Retention policy assignments
│   ├── archive.json            # Archived rules (never lost)
│   ├── permissions.json        # Per-observation RBAC
│   ├── onboarding/             # Role-based onboarding packs
│   ├── succession/             # Departing member knowledge capture
│   └── coaching/               # Coaching amplifications
```

Commit `.loom/rules.json` and `.loom/conventions.md` to git so your team shares the same conventions.

---

## 🔧 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOOM_PROJECT_ROOT` | No | `$PWD` | Where to create `.loom/` |
| `LOOM_ORG_STORE` | No | `.loom/org-store.json` | Shared org-wide memory path |
| `ANTHROPIC_API_KEY` | No | — | Enable Anthropic extraction |
| `LOOM_DEEPSEEK_API_KEY` | No | — | Enable DeepSeek extraction |
| `GEMINI_API_KEY` | No | — | Enable Gemini extraction |
| `LOOM_LLM_PROVIDER` | No | auto-detect | Force provider: `anthropic`, `deepseek`, or `gemini` |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│              MCP Client (Claude)             │
│  Auto session_init ──→ first tool call      │
│  Auto observe ──→ every teach/learn/amplify │
│  Explicit tools ──→ recall, export, etc.    │
└──────────────────┬──────────────────────────┘
                   │ stdio (JSON-RPC)
┌──────────────────▼──────────────────────────┐
│           FastMCP Server (loom.mcp)          │
│  Hook layer: auto session_init + observe    │
│  18 tools — learn, teach, reflect, recall,  │
│  observe, onboard, succession, amplify,     │
│  retain, timeline, federate, session_init   │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────────────────┐
    ▼              ▼              ▼           ▼
┌────────┐  ┌────────────┐  ┌──────────┐  ┌──────────┐
│ Rule   │  │  Domain    │  │  LLM      │  │  Org     │
│ Store  │  │  Extractor │  │  Extractor│  │  Store   │
│ (JSON) │  │  (YAML)    │  │ (Provider)│  │  (JSON)  │
└────────┘  └────────────┘  └──────────┘  └──────────┘
    │              │              │              │
    └──────────────┼──────────────┼──────────────┘
                   ▼              ▼
    ┌──────────┬──────────┬──────────────┬──────────┐
    │ Auto     │ Context  │  Timeline    │ Retention│
    │ Observer │ Loader   │  (JSONL)     │  Manager │
    └──────────┴──────────┴──────────────┴──────────┘
                   │
    ┌──────────────┼──────────────────────────────┐
    ▼              ▼              ▼               ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│Onboarding│ │Succession│ │ Coaching │ │  Security    │
│  Packs   │ │ Capture  │ │Amplifier│ │  Layer (5)   │
└──────────┘ └──────────┘ └──────────┘ └──────────────┘
```

---

## 📊 Example Session

```
[Agent starts coding — Loom hooks fire automatically]

First tool call → auto session_init injects:

<!-- LOOM:AUTO_CONTEXT -->
## 🔍 Relevant Conventions (from Loom)

### ⚡ Top Reminders
1. All routes must have explicit type annotations (9/10)
2. Use async/await for all I/O operations (8/10)
3. Every new endpoint needs at least one test (9/10)

### By Domain
#### coding
- type_safety (9/10): All public functions must have type hints
- error_handling (8/10): Use custom exception classes
...

### 📢 Coaching Amplifications
- "Use async/await for all I/O" — Sarah Chen (Staff Eng)
  This is critical because sync I/O caused 3 production incidents...

### 🌐 Org-Wide Knowledge
- [api-service] error_handling: Always include request IDs
- [shared-infra] process: Squash commits before merging

*Session context loaded by Loom*

[Agent continues coding. Every teach/learn/amplify auto-observed.]

Agent: teach(domain="security", rule="Hash passwords with bcrypt",
             rule_type="cryptography")

[Session ends — auto-flush extracts all observations into rules.]
```

---

## 📦 Project Structure

```
loom/
├── engine/                 # Core domain logic
│   ├── rule_store.py              # JSON-backed persistent rule store
│   ├── domain_extractor.py        # Config-driven keyword extraction (8 domains)
│   ├── llm_extractor.py           # Provider-agnostic LLM extraction
│   ├── decay_manager.py           # Confidence decay over time
│   ├── auto_observer.py           # Silent passive observation with buffer
│   ├── context_loader.py          # Smart auto-recall by task + role
│   ├── org_store.py               # Cross-project org-wide shared memory
│   ├── timeline.py                # Auditable, append-only org history
│   ├── session_manager.py         # Session lifecycle (create, track, cleanup)
│   └── retention.py               # Tiered retention (permanent → transient)
├── llm/                    # Pluggable LLM providers
│   ├── base.py                    # BaseLLMProvider ABC
│   ├── anthropic.py               # Claude via anthropic SDK
│   ├── deepseek.py                # DeepSeek via openai SDK
│   ├── gemini.py                  # Gemini via google-generativeai SDK
│   └── factory.py                 # Auto-detect provider from env vars
├── mcp/                    # MCP server implementation
│   ├── __main__.py                # Entry point: python3 -m loom.mcp
│   └── server.py                  # Hook layer + 18 tools
├── security/               # Security & governance
│   ├── redactor.py                # PII/secret redaction
│   ├── private_mode.py            # Privacy mode controls
│   ├── integrity.py               # Checksum verification
│   ├── audit.py                   # Append-only audit log
│   ├── access.py                  # Token-based access control
│   └── rbac.py                    # Per-observation RBAC (5 levels)
├── onboarding/             # Onboarding & knowledge transfer
│   ├── packs.py                   # Role-based onboarding packs
│   └── succession.py              # Departing member knowledge capture
└── coaching/               # Coaching amplification
    └── amplifier.py               # Scale top performer patterns
```

---

## 🔧 Requirements

| Requirement | Why |
|-------------|-----|
| **Python 3.11+** | Type hint syntax, stdlib improvements |
| **An MCP Client** | Claude Desktop, Claude Code, Cursor, or any MCP host |
| **LLM API key (optional)** | Anthropic, DeepSeek, or Gemini for smart extraction. Keyword extraction is free by default. |

---

<p align="center">
  <sub>Built with ❤️ for organizations that want their AI agents to get smarter with every interaction — and never forget.</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/protocol-MCP-green?style=for-the-badge" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/license-MIT-purple?style=for-the-badge" alt="MIT License">
</p>

<h1 align="center">🧠 Loom</h1>
<p align="center"><strong>The memory layer for AI agents</strong></p>
<p align="center">An MCP server that observes, learns, and remembers conventions from everything your AI agents do — making every agent smarter over time.</p>

---

## ✨ What Loom Does

Loom is the memory layer for AI coding agents. Agents learn through three paths — observation, teaching, and reflection — and recall what they've learned on future runs.

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  OBSERVE    │     │    TEACH     │     │   REFLECT     │
│             │     │              │     │               │
│ Agent       │     │ You or agent │     │ Agent reviews │
│ reports     │     │ explicitly   │     │ completed     │
│ what        │     │ teaches a    │     │ work and      │
│ happened    │     │ convention   │     │ identifies    │
│             │     │              │     │ patterns      │
└──────┬──────┘     └──────┬───────┘     └───────┬───────┘
       │                   │                     │
       └───────────────────┼─────────────────────┘
                           ▼
                   ┌───────────────┐
                   │     LOOM      │
                   │  extracts &   │
                   │   remembers   │
                   └───────┬───────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  CLAUDE.md / AGENTS.md │
              │  & .cursorrules        │
              │                        │
              │  <!-- LOOM:START -->   │
              │  Auto-learned...       │
              │  <!-- LOOM:END -->     │
              └────────────────────────┘
```

**Works with Claude Code, Codex CLI, GitHub Copilot, Cursor, and any MCP-compatible agent.**

---

## 🔌 MCP Server — Seven Powerful Tools

Loom runs as an **MCP (Model Context Protocol) server** over stdio. Your AI agents call its tools directly during coding sessions.

| Tool | Description | Example use |
|------|-------------|-------------|
| `learn` | Learn from observation — *"I did X, here's what happened"* | Agent reports outcome of a coding task |
| `teach` | Teach a rule directly — *"Remember this rule"* | "Always use async/await for I/O" |
| `reflect` | Reflect on completed work — *"Looking back, here are patterns I notice"* | Agent reviews its own PR, spots style patterns |
| `recall_memory` | Search learned conventions | Agent checks what rules apply before writing code |
| `export` | Export rules in structured formats | Get all rules as JSON for analysis |
| `get_stats` | Get statistics about learned rules | See what loom has learned across domains |
| `store_outcome` | Backward-compat PR outcome storage | Existing PR workflows keep working |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **An MCP client** (Claude Code, Continue, Cursor, etc.)

### Install

```bash
git clone https://github.com/Kaushik-hub306/loom.git
cd loom
pip install -e .
```

### Configure Your MCP Client

**Claude Desktop** — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "loom": {
      "command": "python",
      "args": ["-m", "loom.mcp"],
      "env": {
        "LOOM_PROJECT_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

**Claude Code CLI** — add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "loom": {
      "command": "python",
      "args": ["-m", "loom.mcp"]
    }
  }
}
```

That's it. On first run, Loom auto-bootstraps a `.loom/` directory with 8 domain configs and an empty rule store. Your AI agents can now call all seven tools.

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
│   └── conventions.md          # Human-readable rules doc
```

The `.loom/` directory is designed to be committed to your repo so your entire team shares the same conventions.

---

## 🧩 Feature Highlights

### 🧠 Three Learning Modes
Agents learn through **observation** (report what happened → extract conventions), **teaching** (directly inject a rule), and **reflection** (batch-extract patterns from completed work). LLM-powered extraction via Claude API is available for nuanced understanding; keyword-based extraction is the zero-cost default.

### 🌐 Eight Configurable Domains
Each domain has its own keywords (for auto-detection), rule types (for grouping), and extraction patterns — all defined in YAML. Add custom domains by dropping a `.yml` file into `.loom/domains/`.

### 📉 Confidence Decay
Rules that aren't reinforced lose confidence over time. If your team stops complaining about naming conventions, Loom stops nagging about them. Fresh feedback keeps the right rules sharp.

### 🔒 Built-in Security Layer
Five security modules protect your data:

| Module | What it does |
|--------|-------------|
| **Redactor** | Strips PII and secrets (API keys, tokens, emails, IPs) from stored feedback |
| **Private Mode** | When enabled, strips URLs and paths; skips persistent writes entirely |
| **Integrity Guard** | SHA-256 checksum verification to detect tampering with store files |
| **Audit Log** | Append-only JSONL log of every rule mutation with invariant checks |
| **Access Control** | Token-based scopes (read/write/admin) for multi-agent deployments |

### 👥 Team Sharing
Commit `.loom/` to your repo. When one developer's agent teaches Loom something new, every developer's AI agent benefits — conventions propagate across the whole team automatically.

---

## 📊 Example Session

```
Agent: learn(
  context="Building a REST API with FastAPI",
  observation="All routes should have explicit type annotations on parameters",
  domain="coding"
)
┌──────────────────────────────────────────────────────────────┐
│ ## Learned                                                   │
│                                                              │
│ Domain: coding                                               │
│ Context: Building a REST API with FastAPI                    │
│ Rules created: 1                                             │
└──────────────────────────────────────────────────────────────┘

Agent: recall_memory(query="type")
┌──────────────────────────────────────────────────────────────┐
│ ## Recall Results for "type"                                 │
│                                                              │
│ - [coding] **type_safety** (7/10): All routes should have    │
│   explicit type annotations on parameters                    │
│   ID: `coding::type_safety::all-routes...` | Confirmed: 3x   │
│ - [coding] **naming** (6/10): Use snake_case for variables   │
│   ID: `coding::naming::use-snake-case...` | Confirmed: 2x    │
└──────────────────────────────────────────────────────────────┘

Agent: teach(
  domain="style",
  rule="Use 4-space indentation everywhere",
  rule_type="formatting",
  confidence=7
)
┌──────────────────────────────────────────────────────────────┐
│ ## Taught                                                    │
│                                                              │
│ Domain: style                                                │
│ Rule type: formatting                                        │
│ Rule: Use 4-space indentation everywhere                     │
│ Confidence: 7/10                                             │
└──────────────────────────────────────────────────────────────┘

Agent: get_stats()
┌──────────────────────────────────────────────────────────────┐
│ ## Stats                                                     │
│                                                              │
│ Total: 24 rule(s)                                            │
│ Average confidence: 7.3/10                                   │
│                                                              │
│ By domain:                                                   │
│   - coding: 12 rule(s)                                       │
│   - style: 5 rule(s)                                         │
│   - testing: 4 rule(s)                                       │
│   - process: 3 rule(s)                                       │
│                                                              │
│ By type:                                                     │
│   - type_safety: 6                                           │
│   - naming: 5                                                │
│   - formatting: 4                                            │
│   - git_workflow: 3                                          │
│   - unit_test: 3                                             │
│   - error_handling: 3                                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│              MCP Client (Claude)             │
│  call_tool("learn")                         │
│  call_tool("teach")                         │
│  call_tool("reflect")                       │
│  call_tool("recall_memory")                 │
│  call_tool("export")                        │
│  call_tool("get_stats")                     │
└──────────────────┬──────────────────────────┘
                   │ stdio (JSON-RPC)
┌──────────────────▼──────────────────────────┐
│           FastMCP Server (loom.mcp)          │
│  learn │ teach │ reflect │ recall │ export   │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐  ┌────────────┐  ┌───────────┐
│ Rule   │  │  Domain    │  │  Decay    │
│ Store  │  │  Extractor │  │  Manager  │
│ (JSON) │  │  (YAML)    │  │           │
└────────┘  └────────────┘  └───────────┘
    │              │              │
    └──────────────┼──────────────┘
                   ▼
        ┌─────────────────┐
        │  Security Layer  │
        │  Redactor        │
        │  Private Mode    │
        │  Integrity Guard │
        │  Audit Log       │
        │  Access Control  │
        └─────────────────┘
```

---

## 📦 Project Structure

```
loom/
├── engine/            # Core domain logic
│   ├── rule_store.py         # JSON-backed persistent rule store
│   ├── domain_extractor.py   # Config-driven rule extraction (8 domains)
│   ├── llm_extractor.py      # Claude-powered extraction (optional)
│   └── decay_manager.py      # Confidence decay over time
├── mcp/               # MCP server implementation
│   ├── __main__.py           # Entry point: python -m loom.mcp
│   └── server.py             # FastMCP-based server with 7 tools
└── security/          # Security & governance
    ├── redactor.py           # PII/secret redaction
    ├── private_mode.py       # Privacy mode controls
    ├── integrity.py          # Checksum verification
    ├── audit.py              # Append-only audit log
    └── access.py             # Token-based access control
```

---

## 🔧 Requirements

| Requirement | Why |
|-------------|-----|
| **Python 3.11+** | Type hint syntax, stdlib improvements |
| **An MCP Client** | Claude Code, Continue, Cursor, or any MCP host |

LLM-powered extraction requires an Anthropic API key (optional — keyword-based extraction is the zero-cost default).

---

<p align="center">
  <sub>Built with ❤️ for developers who want their AI agents to get smarter with every interaction.</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/protocol-MCP-green?style=for-the-badge" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/license-MIT-purple?style=for-the-badge" alt="MIT License">
</p>

<h1 align="center">🧠 Loom</h1>
<p align="center"><strong>The memory layer for AI coding agents</strong></p>
<p align="center">An MCP server that watches your PR reviews, learns coding conventions, and makes every AI agent in your repo write better code — automatically.</p>

---

## ✨ What Loom Does

Every time a reviewer leaves feedback on a PR ("use type hints", "add tests", "snake_case please"), Loom captures that knowledge so your AI agents never make the same mistake twice.

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ You open │     │ Reviewer │     │  PR gets │     │   Loom   │
│  a PR    │────▶│ leaves   │────▶│ rejected │────▶│ extracts │
│(Claude)  │     │ feedback │     │          │     │   rules  │
└──────────┘     └──────────┘     └──────────┘     └────┬─────┘
                                                       │
                                                       ▼
                                              ┌──────────────┐
                                              │ Rules stored │
                                              │ in .loom/    │
                                              │ conventions  │
                                              └──────┬───────┘
                                                     │
                                                     ▼
                                              ┌──────────────┐
                                              │ Next agent   │
                                              │ reads rules  │
                                              │ writes better │
                                              │    code 🎯   │
                                              └──────────────┘
```

**Works with Claude Code, Codex CLI, GitHub Copilot, Cursor, and any MCP-compatible agent.**

---

## 🔌 MCP Server — Three Powerful Tools

Loom runs as an **MCP (Model Context Protocol) server** over stdio. Your AI agents call its tools directly during coding sessions.

### `recall_memory`
Search learned conventions by keyword before writing code.

```json
{ "query": "type hints" }
```
→ Returns matching rules with confidence scores, domain, and examples.

### `store_outcome`
Feed a PR outcome back to Loom so it learns from feedback.

```json
{
  "domain": "coding",
  "outcome": "rejected",
  "feedback": "Please add type annotations to all function signatures"
}
```
→ Extracts rules from the feedback, updates the store, and regenerates conventions.

### `get_stats`
Check what Loom has learned across your project.

```json
{ "domain": "coding" }
```
→ Returns total rules, average confidence, and breakdowns by domain and rule type.

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

**Claude Code** — add to `~/.claude/claude_desktop_config.json` or your project `.mcp.json`:

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

That's it. On first run, Loom auto-bootstraps a `.loom/` directory with default domain configs and an empty rule store. Your AI agents can now call `recall_memory`, `store_outcome`, and `get_stats`.

---

## 📂 What Loom Creates

```
your-project/
├── .loom/
│   ├── domains/
│   │   ├── coding.yml        # Software engineering conventions
│   │   └── support.yml       # Support/escalation conventions
│   ├── rules.json            # Learned rules with confidence scores
│   └── conventions.md        # Human-readable rules doc
```

The `.loom/` directory is designed to be committed to your repo so your entire team shares the same conventions.

---

## 🧩 Feature Highlights

### 🏷️ Smart Rule Extraction
Loom classifies feedback into 8 rule types: **type safety**, **testing**, **error handling**, **naming**, **architecture**, **documentation**, **formatting**, and **security**. Each rule tracks its confidence score (1–10) and how many times it's been confirmed.

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

### 🌐 Custom Domains
Out of the box, Loom ships with `coding` and `support` domains. Define your own by dropping a `.yml` file into `.loom/domains/`:

```yaml
name: design
description: Design system conventions
keywords:
  - design
  - CSS
  - layout
  - component
  - color
rule_types:
  - accessibility
  - responsiveness
  - consistency
```

### 👥 Team Sharing
Commit `.loom/` to your repo. When one developer's PR teaches Loom something new, every developer's AI agent benefits — conventions propagate across the whole team automatically.

---

## 📊 Example Session

```
Agent: recall_memory(query="error handling")
┌──────────────────────────────────────────────────────────────┐
│ ## Recall Results for "error handling"                       │
│                                                              │
│ - [coding] **error_handling** (9/10): Use specific exception │
│   types instead of bare except                                │
│   ID: `coding::error_handling::use-specific-exceptions`      │
│   Confirmed: 12x                                              │
│   Example: `raise ValueError("invalid input") not raise`     │
│                                                              │
│ - [coding] **error_handling** (7/10): Log all errors with    │
│   context before re-raising                                   │
│   ID: `coding::error_handling::log-errors-with-context`      │
│   Confirmed: 5x                                               │
└──────────────────────────────────────────────────────────────┘

Agent: store_outcome(
  domain="coding",
  outcome="rejected",
  feedback="Wrap external API calls in try/except with retry logic"
)
┌──────────────────────────────────────────────────────────────┐
│ ## Stored Outcome                                            │
│                                                              │
│ Domain: coding                                               │
│ Outcome: rejected                                            │
│ Rules created: 1                                             │
└──────────────────────────────────────────────────────────────┘

Agent: get_stats()
┌──────────────────────────────────────────────────────────────┐
│ ## Stats                                                     │
│                                                              │
│ Total: 24 rule(s)                                            │
│ Average confidence: 7.3/10                                   │
│                                                              │
│ By domain:                                                   │
│   - coding: 19 rule(s)                                       │
│   - support: 5 rule(s)                                       │
│                                                              │
│ By type:                                                     │
│   - error_handling: 6                                        │
│   - testing: 5                                               │
│   - naming: 4                                                │
│   - type_safety: 3                                           │
│   - architecture: 3                                          │
│   - documentation: 2                                         │
│   - formatting: 1                                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│              MCP Client (Claude)             │
│  call_tool("recall_memory")                 │
│  call_tool("store_outcome")                 │
│  call_tool("get_stats")                     │
└──────────────────┬──────────────────────────┘
                   │ stdio (JSON-RPC)
┌──────────────────▼──────────────────────────┐
│           FastMCP Server (loom.mcp)          │
│  recall_memory │ store_outcome │ get_stats   │
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
├── engine/           # Core domain logic
│   ├── rule_store.py        # JSON-backed persistent rule store
│   ├── domain_extractor.py  # Keyword-based rule extraction
│   └── decay_manager.py     # Confidence decay over time
├── mcp/              # MCP server implementation
│   ├── __main__.py          # Entry point: python -m loom.mcp
│   └── server.py            # FastMCP-based server with 3 tools
└── security/         # Security & governance
    ├── redactor.py          # PII/secret redaction
    ├── private_mode.py      # Privacy mode controls
    ├── integrity.py         # Checksum verification
    ├── audit.py             # Append-only audit log
    └── access.py            # Token-based access control
```

---

## 🔧 Requirements

| Requirement | Why |
|-------------|-----|
| **Python 3.11+** | Type hint syntax, stdlib improvements |
| **An MCP Client** | Claude Code, Continue, Cursor, or any MCP host |

No GitHub API access required — your AI agent feeds Loom directly through MCP tool calls.

---

<p align="center">
  <sub>Built with ❤️ for developers who want their AI agents to get smarter with every PR.</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/protocol-MCP-green?style=for-the-badge" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/license-MIT-purple?style=for-the-badge" alt="MIT License">
  <img src="https://img.shields.io/badge/version-0.3.0-orange?style=for-the-badge" alt="Version 0.3.0">
</p>

<h1 align="center">🧠 Loom</h1>
<p align="center"><strong>Shared learning for AI agents — what any of them learns belongs to your whole org</strong></p>
<p align="center">An MCP server that observes, learns, and remembers conventions from everything your AI agents do — making every agent smarter over time. One repository of understanding that every agent draws from.</p>

---

## ✨ What Loom Does

Loom is the shared memory layer for your organization's AI agents. Every agent reads from and writes to a single store, so institutional knowledge compounds across your entire agent fleet rather than being siloed within individual sessions.

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR ORGANIZATION                        │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Claude  │  │  Codex   │  │ Copilot  │  │ Custom Agent │  │
│  │  Code    │  │  CLI     │  │          │  │              │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
│       │             │             │               │           │
│       └─────────────┼─────────────┼───────────────┘           │
│                     │             │                            │
│                     ▼             ▼                            │
│              ┌──────────────────────────┐                      │
│              │          LOOM            │                      │
│              │                          │                      │
│              │  • Auto-capture          │                      │
│              │  • Auto-recall           │                      │
│              │  • Org-wide memory       │                      │
│              │  • Per-observation RBAC  │                      │
│              │  • Tiered retention      │                      │
│              │  • Auditable timeline    │                      │
│              │  • Instant onboarding    │                      │
│              │  • Succession capture    │                      │
│              │  • Coaching amplification│                      │
│              └──────────────────────────┘                      │
│                                                                 │
│    What one agent learns, every agent knows.                    │
│    Knowledge persists beyond sessions, beyond turnover.         │
└─────────────────────────────────────────────────────────────────┘
```

**Works with Claude Code, Codex CLI, GitHub Copilot, Cursor, and any MCP-compatible agent.**

---

## 🆚 Loom vs Glen — Feature Comparison

| Feature | Loom 0.3.0 | Glen |
|---------|:----------:|:----:|
| **Org-wide shared memory** | ✅ One store, all agents | ✅ |
| **Automatic capture** | ✅ Passive `observe` mode | ✅ |
| **Auto-recall context** | ✅ `recall_relevant` + `session_init` | ✅ |
| **Per-observation RBAC** | ✅ 5 clearance levels | ✅ |
| **Auditable timeline** | ✅ Full queryable history | ✅ |
| **Infinite retention** | ✅ Permanent + long-term tiers | ✅ |
| **Instant onboarding** | ✅ Role-based packs | ✅ |
| **Succession capture** | ✅ Full knowledge transfer | ✅ |
| **Coaching amplification** | ✅ Scale top performers | ✅ |
| **Explicit teaching** | ✅ `teach` tool for direct rules | ❌ |
| **Configurable domains** | ✅ 8 domains, add your own YAML | ❌ |
| **Dual extraction** | ✅ Keyword (free) + LLM (Claude) | ❌ |
| **Confidence decay** | ✅ Smart tiered decay | ❌ |
| **Security layer** | ✅ Redaction, integrity, audit, tokens | ❌ |
| **Open source** | ✅ MIT license, audit the code | ❌ |
| **Self-hosted** | ✅ Runs locally, no cloud dependency | ❌ |
| **Cloud optional** | ✅ Can federate to shared store | ✅ Cloud-only |
| **Pricing** | ✅ Free, forever | 🔒 Waitlist |

---

## 🔌 MCP Server — 18 Powerful Tools

Loom runs as an **MCP (Model Context Protocol) server** over stdio. Your AI agents call its tools directly during coding sessions.

### Core Learning
| Tool | Description | Glen Equivalent |
|------|-------------|-----------------|
| `learn` | Learn from observation | Automatic capture |
| `teach` | Teach a rule directly | — *(Loom exclusive)* |
| `reflect` | Reflect on completed work | — |

### Glen-Level Features
| Tool | Description | Glen Equivalent |
|------|-------------|-----------------|
| `recall_relevant` | Auto-recall everything relevant to a task | Glen's pre-loaded context |
| `observe` | Passive observation — silent background capture | "Nothing to write down" |
| `session_init` | Pre-load all relevant context at session start | Glen's auto-context |
| `onboard` | Generate onboarding pack for a new team member | Instant onboarding |
| `succession` | Capture departing member's knowledge | Knowledge retention |
| `amplify` | Amplify coaching across the team | Coaching amplification |
| `retain` | Mark a rule for permanent retention | Infinite memory |
| `set_clearance` | Set per-observation access control | Per-observation RBAC |
| `timeline` | Query the auditable organization timeline | Auditable timeline |
| `federate` | Ingest rules from other projects | Cross-project memory |
| `export_timeline` | Export full org history | — |

### Essentials
| Tool | Description |
|------|-------------|
| `recall_memory` | Search learned conventions |
| `export` | Export rules in structured formats |
| `get_stats` | Get statistics including org-wide and retention data |
| `store_outcome` | Store outcome from PR review (backward compat) |

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
        "LOOM_PROJECT_ROOT": "/path/to/your/project",
        "LOOM_ORG_STORE": "/path/to/shared/org/store"
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

That's it. On first run, Loom auto-bootstraps a `.loom/` directory with 8 domain configs, an empty rule store, and all subdirectories for onboarding, succession, coaching, and more.

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
~/.loom/
└── org-store.json              # Org-wide shared memory (all projects)
```

The `.loom/` directory is designed to be committed to your repo so your entire team shares the same conventions.

---

## 🧩 Glen-Level Feature Highlights

### 🧠 Automatic Capture — "Nothing to Write Down"
Agents don't need to remember to call tools. The `observe` tool silently captures observations in the background with configurable sensitivity (silent/normal/eager). When enough context accumulates, Loom auto-flushes and extracts conventions — no manual documentation overhead.

### 🔍 Auto-Recall — Pre-Loaded Context Every Session
Call `session_init` with your task, and Loom returns everything relevant — conventions, coaching amplifications, onboarding context, and cross-project knowledge — all formatted for injection into your agent's system prompt. No more blank slates.

### 🌐 Org-Wide Shared Memory
What any agent learns is learned by all. The org store federates rules from every project in your organization, so a decision made in the API team benefits the frontend team. Cross-project context inheritance means knowledge transfers automatically.

### 🔒 Per-Observation RBAC
Five clearance levels (PUBLIC → SECRET). At recall time, agents surface only what their user is cleared to see. Sensitive rules about compensation or security incidents are automatically filtered. Policies can auto-apply to new rules matching patterns.

### 📅 Auditable Timeline
One queryable history of the entire organization. Every learning event — who learned what, when, and why — is recorded in an append-only JSONL timeline. Full decision trails for every rule. Postmortems and audits have never been easier.

### 🔒 Tiered Retention
Four retention tiers: **Permanent** (never decays — org decisions, architecture, security), **Long-Term** (180-day grace), **Standard** (30-day grace), and **Transient** (7-day grace for experiments). Rules you care about stay forever; transient patterns gracefully fade.

### 🚀 Instant Onboarding
New hire? Their agent already knows how the org works. Generate role-based onboarding packs that include top conventions, key decisions from the timeline, captured succession knowledge, and coaching amplifications — all in one formatted document.

### 📋 Succession Capture
When someone leaves, their knowledge stays. Capture tribal knowledge, gotchas, design decisions, and process details. Auto-imports every rule they authored or confirmed. Transfers directly into onboarding packs for their replacement.

### 📢 Coaching Amplification
Top performers' judgment becomes reusable training. Amplify a rule with the coach's reasoning, real examples, and anti-patterns. Target specific roles. Track effectiveness over time. Scale the best practices across the entire team.

### 🌐 Cross-Project Federation
Ingest rules from any project's `.loom/` into the org store. Rules deduplicate automatically — same convention across projects gets higher confidence, not duplicates.

---

## 📊 Example Sessions

### Automatic Capture & Recall
```
Agent: session_init(task="Build a user profile API", role="backend-engineer")
┌──────────────────────────────────────────────────────────────┐
│ ## 🔍 Relevant Conventions (from Loom)                       │
│                                                              │
│ ### ⚡ Top Reminders                                         │
│ 1. All routes must have explicit type annotations (9/10)    │
│ 2. Use async/await for all I/O operations (8/10)             │
│ 3. Every new endpoint needs at least one test (9/10)         │
│                                                              │
│ ### By Domain                                                │
│ #### coding                                                  │
│ - type_safety (9/10): All public functions must...           │
│ - error_handling (8/10): Use custom exception classes...     │
│                                                              │
│ #### testing                                                 │
│ - unit_test (9/10): Every new endpoint needs...              │
│                                                              │
│ ### 📢 Coaching Amplifications                               │
│ - "Use async/await for all I/O" — Sarah Chen (Staff Eng)    │
│   This is critical because sync I/O caused 3 production...   │
│                                                              │
│ ### 🌐 Org-Wide Knowledge                                    │
│ - [api-service] error_handling: Always include request IDs   │
│ - [shared-infra] process: Squash commits before merging      │
│                                                              │
│ *Session context loaded by Loom*                             │
└──────────────────────────────────────────────────────────────┘

Agent: observe(context="Implementing login", 
               content="We hash passwords with bcrypt before storing")

Agent: observe(context="Implementing login",
               content="JWT tokens should expire after 24 hours max")

# After enough observations accumulate, Loom auto-flushes...

┌──────────────────────────────────────────────────────────────┐
│ ## 👁️ Observed & Learned                                    │
│                                                              │
│ Domain: security                                             │
│ Rules auto-extracted: 2                                      │
│ - Use bcrypt for password hashing (confidence: 7/10)         │
│ - JWT tokens expire within 24 hours (confidence: 6/10)       │
└──────────────────────────────────────────────────────────────┘
```

### Onboarding & Succession
```
Agent: onboard(role="backend-engineer")
┌──────────────────────────────────────────────────────────────┐
│ # 🚀 Onboarding Pack: Backend Engineer                       │
│                                                              │
│ ## 📋 Core Conventions                                       │
│ ### Coding                                                   │
│ - type_safety (9/10): All public functions must have...      │
│ - error_handling (8/10): Use custom exception classes...     │
│                                                              │
│ ### Testing                                                  │
│ - unit_test (9/10): Every new endpoint needs...              │
│                                                              │
│ ## 🧭 Key Recent Decisions                                   │
│ - 2025-03-15: Adopted FastAPI over Flask (ADR-12)            │
│ - 2025-04-01: PostgreSQL selected as primary DB (ADR-13)     │
│                                                              │
│ ## 📋 Captured Team Knowledge                                │
│ - jane-smith — Staff Engineer succession (June 2026)         │
│                                                              │
│ ## 📢 Coaching From Your Team                                │
│ - "Always use async/await" — Sarah Chen, Staff Engineer      │
└──────────────────────────────────────────────────────────────┘

Agent: succession(member="jane-smith", role="staff-engineer", action="start")
Agent: succession(member="jane-smith", role="staff-engineer", action="capture",
         title="Why we chose PostgreSQL",
         detail="We evaluated MySQL, Postgres, and Mongo in Q3 2024...",
         importance=9, category="design_decision")
Agent: succession(member="jane-smith", role="staff-engineer", action="finalize")
┌──────────────────────────────────────────────────────────────┐
│ # 📋 Succession Knowledge: Jane Smith (Staff Engineer)       │
│                                                              │
│ ## 🔴 Critical Knowledge (Must Know)                         │
│ ### Design Decisions                                         │
│ - **Why we chose PostgreSQL** (importance: 9/10)             │
│   We evaluated MySQL, Postgres, and Mongo in Q3 2024...      │
│                                                              │
│ ## Linked Rules (14 authored/confirmed by Jane)              │
│ - coding::error_handling::use-custom-exceptions (9/10)       │
│ - architecture::service_layer::new-features-as-services...   │
└──────────────────────────────────────────────────────────────┘
```

### Timeline & RBAC
```
Agent: timeline(days=90, limit=10)
┌──────────────────────────────────────────────────────────────┐
│ ## 📅 Organization Timeline                                  │
│                                                              │
│ ### 2025-06-11                                               │
│ - 14:32 🧠 Learned: Use async/await for all I/O operations   │
│   Domain: coding | Agent: claude-code | Project: api-service │
│   Context: After debugging a blocking I/O issue in prod...   │
│ - 10:15 📖 Taught: Squash commits before merging to main     │
│   Domain: process | Agent: dev-jane | Project: shared-infra  │
│ - 09:01 📢 Amplified: "Always use type annotations"          │
│   Coach: Sarah Chen (Staff Engineer)                         │
└──────────────────────────────────────────────────────────────┘

Agent: set_clearance(rule_id="security::secrets::rotate-api-keys",
         clearance="confidential",
         allowed_roles=["security-engineer", "tech-lead"],
         allowed_teams=["platform"])
┌──────────────────────────────────────────────────────────────┐
│ ## 🔐 Clearance Set                                          │
│ Clearance: confidential                                      │
│ Allowed roles: security-engineer, tech-lead                  │
│ Allowed teams: platform                                      │
│ → Agents without these roles will never see this rule        │
└──────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│              MCP Client (Claude)             │
│  call_tool("learn")                         │
│  call_tool("recall_relevant")               │
│  call_tool("session_init")                  │
│  call_tool("observe")                       │
│  call_tool("onboard")                       │
│  call_tool("succession")                    │
│  call_tool("amplify")                       │
│  call_tool("timeline")                      │
│  ... 18 tools total                         │
└──────────────────┬──────────────────────────┘
                   │ stdio (JSON-RPC)
┌──────────────────▼──────────────────────────┐
│           FastMCP Server (loom.mcp)          │
│  18 tools — learn, teach, reflect, recall,  │
│  observe, onboard, succession, amplify,     │
│  retain, timeline, federate, session_init   │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────────────────┐
    ▼              ▼              ▼           ▼
┌────────┐  ┌────────────┐  ┌──────────┐  ┌──────────┐
│ Rule   │  │  Domain    │  │  Decay   │  │  Org     │
│ Store  │  │  Extractor │  │  Manager │  │  Store   │
│ (JSON) │  │  (YAML)    │  │          │  │  (JSON)  │
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

## 📦 Project Structure

```
loom/
├── engine/                 # Core domain logic
│   ├── rule_store.py              # JSON-backed persistent rule store
│   ├── domain_extractor.py        # Config-driven rule extraction (8 domains)
│   ├── llm_extractor.py           # Claude-powered extraction (optional)
│   ├── decay_manager.py           # Confidence decay over time
│   ├── auto_observer.py           # Silent passive observation (Glen capture)
│   ├── context_loader.py          # Smart auto-recall (Glen pre-loaded context)
│   ├── org_store.py               # Cross-project org-wide shared memory
│   ├── timeline.py                # Auditable, append-only org history
│   └── retention.py               # Tiered retention (permanent → transient)
├── mcp/                    # MCP server implementation
│   ├── __main__.py                # Entry point: python -m loom.mcp
│   └── server.py                  # FastMCP-based server with 18 tools
├── security/               # Security & governance
│   ├── redactor.py                # PII/secret redaction
│   ├── private_mode.py            # Privacy mode controls
│   ├── integrity.py               # Checksum verification
│   ├── audit.py                   # Append-only audit log
│   ├── access.py                  # Token-based access control
│   └── rbac.py                    # Per-observation RBAC (Glen-style)
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
| **An MCP Client** | Claude Code, Continue, Cursor, or any MCP host |

LLM-powered extraction requires an Anthropic API key (optional — keyword-based extraction is the zero-cost default).

---

<p align="center">
  <sub>Built with ❤️ for organizations that want their AI agents to get smarter with every interaction — and never forget.</sub>
</p>

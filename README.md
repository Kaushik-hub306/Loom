# Loom — The Memory Layer for AI Agents

Loom observes, learns, and remembers conventions from everything your AI agents do — making every agent smarter over time.

**Works across Claude Code, Codex CLI, and Cursor.** Agents call Loom through MCP tools. Loom remembers. Next time, every agent writes better code.

## Quick Start

```bash
git clone https://github.com/Kaushik-hub306/loom.git
cd loom
pip install -e .
# Configure Loom as an MCP server in your agent's config.
# See SETUP.md for Claude Desktop / Codex / Cursor instructions.
```

## How It Works

Agents learn through three paths:

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

## MCP Tools

Loom exposes 7 MCP tools:

| Tool | Description | Example use |
|------|-------------|-------------|
| `learn` | Learn from observation — *"I did X, here's what happened"* | Agent reports outcome of a coding task |
| `teach` | Teach a rule directly — *"Remember this rule"* | "Always use async/await for I/O" |
| `reflect` | Reflect on completed work — *"Looking back, here are patterns I notice"* | Agent reviews its own PR, spots style patterns |
| `recall_memory` | Search learned conventions | Agent checks what rules apply before writing code |
| `export` | Export rules in structured formats | Get all rules as JSON for analysis |
| `get_stats` | Get statistics about learned rules | See what loom has learned across domains |
| `store_outcome` | Backward-compat PR outcome storage | Existing PR workflows keep working |

## What Agents See

When an agent queries `recall_memory`, it gets back relevant conventions sorted by confidence:

```markdown
## Recall Results for "type"

- [coding] **type_safety** (7/10): All function parameters must have type annotations
  ID: `coding::type_safety::all-function-parameters...` | Confirmed: 3x
- [coding] **naming** (6/10): Use snake_case for variable names, not camelCase
  ID: `coding::naming::use-snake-case...` | Confirmed: 2x
```

Rules with higher confidence (reinforced across multiple observations) rank first.

## Domains

Loom comes with 8 built-in domains. Each carries its own extraction patterns — you can customize any of them:

| Domain | What it covers |
|--------|---------------|
| `coding` | Type safety, error handling, naming, function design, performance |
| `style` | Formatting, indentation, comments, line length, quotes |
| `architecture` | Design patterns, module structure, separation of concerns |
| `process` | Git workflow, commit messages, PR process, CI/CD |
| `testing` | Unit tests, integration tests, coverage, mocking |
| `security` | Auth, input validation, secrets, cryptography |
| `documentation` | Docstrings, READMEs, API docs, changelogs |
| `general` | Catch-all preferences, conventions, best practices |

Domain configs live in `.loom/domains/*.yml`. Add your own or edit the defaults.

## LLM Extraction (Optional)

By default, Loom uses keyword-based extraction. For smarter extraction, set an API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-xxx
```

With LLM extraction, Loom understands nuanced feedback and extracts cleaner, more actionable conventions — it abstracts patterns, detects style, and generalizes from concrete examples.

## Team Use

`.loom/` files can be committed to your repo. Team members share the same conventions. When one person's agent teaches loom something, everyone's agents benefit.

```bash
git add .loom/ CLAUDE.md AGENTS.md .cursorrules
git commit -m "loom: update conventions"
git push
```

## Files Loom Manages

| File | Purpose |
|------|---------|
| `.loom/rules.json` | All learned rules with confidence scores |
| `.loom/conventions.md` | Regenerated markdown for agent consumption |
| `.loom/domains/*.yml` | Domain configurations (extensible) |

## Requirements

- Python 3.11+
- MCP-compatible agent host (Claude Desktop, Codex CLI, Cursor)

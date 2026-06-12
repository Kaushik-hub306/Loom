# Loom Setup Guide

Loom is an MCP server that acts as the memory layer for AI coding agents. Agents call loom to learn conventions from observation, teaching, and reflection — and to recall what they've learned on future runs.

## 1. Install

```bash
git clone https://github.com/Kaushik-hub306/loom.git
cd loom
pip install -e .

# Optional: LLM-powered extraction
pip install -e ".[llm]"
```

## 2. Configure Your Agent

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

### Codex CLI

Add to your Codex configuration:

```yaml
mcp_servers:
  - name: loom
    command: python
    args: ["-m", "loom.mcp"]
    env:
      LOOM_PROJECT_ROOT: /path/to/your/project
```

### Cursor

Add to Cursor's MCP settings (Settings → Features → MCP):

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

## 3. Restart Your Agent

After configuring, restart Claude Desktop / Codex / Cursor. Loom's 7 tools will be available:

- `learn` — Report what happened and extract conventions
- `teach` — Directly inject a convention rule
- `reflect` — Extract patterns from multiple observations
- `recall_memory` — Search learned conventions
- `export` — Export rules in JSON, markdown, or compact format
- `get_stats` — See what loom has learned
- `store_outcome` — Backward-compat PR outcome storage

## 4. First Run

Loom auto-bootstraps on first use — it creates `.loom/` with 8 domain configs and initializes the rule store. No manual setup needed.

## 5. LLM Extraction (Optional)

For smarter rule extraction (understands nuance, abstracts patterns), set:

```bash
export ANTHROPIC_API_KEY=sk-ant-xxx
```

Without this, loom uses keyword-based extraction from domain configs — still effective for well-scoped domains, but less nuanced.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOOM_PROJECT_ROOT` | No | `$PWD` | Project root directory |
| `ANTHROPIC_API_KEY` | No | — | API key for LLM-powered extraction |
| `LOOM_PRIVATE_MODE` | No | — | Set to `1` to block writes (privacy mode) |

## Customizing Domains

Edit `.loom/domains/*.yml` to change keywords, rule types, and extraction patterns. Each domain config:

```yaml
name: my_domain
description: What this domain covers
keywords:          # For auto-detecting which domain feedback belongs to
  - keyword1
  - keyword2
rule_types:        # For stats grouping
  - type1
  - type2
patterns:          # Keyword → rule_type mapping for extraction
  type1:
    - trigger word 1
    - trigger word 2
  type2:
    - other trigger
use_llm: false     # Set true to prefer LLM extraction for this domain
```

Add new `.yml` files for custom domains. Loom discovers them automatically.

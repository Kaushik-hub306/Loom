# Loom — One-Shot Setup

Two commands. That's it.

## 1. Install

```bash
pip install loom-learn
```

**Optional LLM extraction** (skip all of these to use free keyword extraction — no API key needed):

```bash
pip install 'loom-learn[llm]'       # Anthropic / Claude
pip install 'loom-learn[deepseek]'  # DeepSeek
pip install 'loom-learn[gemini]'    # Gemini
pip install 'loom-learn[cloud]'     # Postgres/Supabase team backend
```

**From source (contributors):**

```bash
git clone https://github.com/Kaushik-hub306/Loom.git
cd Loom
pip install -e ".[dev]"
```

## 2. Run setup

```bash
loom setup
```

This detects your Python, creates the storage folder, and prints your Claude Desktop config. Copy the JSON it outputs.

If you have an API key for LLM extraction, add it to the `"env"` block before pasting:

```json
"env": {
  "LOOM_PROJECT_ROOT": "/path/printed/by/setup",
  "ANTHROPIC_API_KEY": "sk-ant-..."
}
```

Or for DeepSeek:

```json
"env": {
  "LOOM_PROJECT_ROOT": "/path/printed/by/setup",
  "LOOM_LLM_PROVIDER": "deepseek",
  "LOOM_DEEPSEEK_API_KEY": "sk-..."
}
```

Paste into:

| OS | Config file |
|----|-----------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

## 3. Restart Claude Desktop

## 4. Verify

```bash
loom doctor
```

All checks should show `[PASS]`. If anything fails, it tells you exactly what to fix.

## What you get

- **Auto session_init** — conventions injected on first tool call, nothing to remember
- **Auto observe** — teach/learn/amplify calls auto-captured as observations
- **18 MCP tools** — teach, learn, recall, observe, amplify, succession, timeline, federate, and more
- **3 LLM providers** — Anthropic, DeepSeek, or Gemini (free keyword mode by default)
- **Zero config** — no API keys required, no servers, no Docker, no cloud

## Environment Variables

The full table lives in the [README](README.md#environment-variables). The ones you'll most likely touch:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOOM_PROJECT_ROOT` | No | `$PWD` | Where to create `.loom/` |
| `LOOM_STORAGE_BACKEND` | No | `json` | `json` or `postgres` |
| `LOOM_DATABASE_URL` | No | — | Postgres connection string (cloud mode) |
| `ANTHROPIC_API_KEY` | No | — | Enable Claude extraction |
| `LOOM_DEEPSEEK_API_KEY` | No | — | Enable DeepSeek extraction |
| `GEMINI_API_KEY` | No | — | Enable Gemini extraction |
| `LOOM_LLM_PROVIDER` | No | auto-detect | Force provider: `anthropic`, `deepseek`, `gemini` |
| `LOOM_LLM_MODEL` | No | provider default | Override the extraction model |
| `LOOM_PRIVATE_MODE` | No | `0` | `1` blocks all memory writes |

## Troubleshooting

```bash
loom doctor
```

Checks: Python version, Loom install, storage writable, domain configs, LLM provider, SDK availability, MCP protocol. Every failure prints the fix.

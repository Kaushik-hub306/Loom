# Loom — One-Shot Setup

Two commands. That's it.

## 1. Install

```bash
git clone https://github.com/Kaushik-hub306/loom.git
cd loom
pip install -e .
```

**For DeepSeek LLM extraction (optional):**
```bash
pip install openai
```

**For Anthropic/Claude extraction (optional):**
```bash
pip install anthropic
```

**For Gemini extraction (optional):**
```bash
pip install google-generativeai
```

Skip all of these to use free keyword extraction — no API key needed.

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

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOOM_PROJECT_ROOT` | No | `$PWD` | Where to create `.loom/` |
| `ANTHROPIC_API_KEY` | No | — | Enable Claude extraction |
| `LOOM_DEEPSEEK_API_KEY` | No | — | Enable DeepSeek extraction |
| `GEMINI_API_KEY` | No | — | Enable Gemini extraction |
| `LOOM_LLM_PROVIDER` | No | auto-detect | Force provider: `anthropic`, `deepseek`, `gemini` |

## Troubleshooting

```bash
loom doctor
```

Checks: Python version, Loom install, storage writable, domain configs, LLM provider, SDK availability, MCP protocol. Every failure prints the fix.

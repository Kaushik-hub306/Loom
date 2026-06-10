# Loom — AI Agents That Learn From Every PR

Loom watches your PR reviews and makes your AI coding agents smarter. Every time a reviewer rejects a PR with feedback, Loom extracts the convention and injects it into CLAUDE.md, AGENTS.md, and .cursorrules. The next time ANY agent runs, it reads those conventions and writes better code.

**Works across Claude Code, Codex CLI, and Cursor.** Zero config after setup.

## Quick Start

```bash
git clone https://github.com/Kaushik-hub306/loom.git
cd loom
pip install -e .
loom          # auto-bootstraps: sets up .loom/, injects into agent configs, auto-detects auth
```

## How It Works

```
1. You create a PR with Claude Code
2. Reviewer leaves feedback ("add type hints", "use snake_case")
3. PR gets closed (rejected)
4. Run: loom
   → Fetches all closed PRs since last run
   → Analyzes review comments
   → Extracts coding conventions
   → Updates CLAUDE.md, AGENTS.md, .cursorrules
5. Next agent run reads the conventions and writes better code
```

## Commands

```bash
loom          # auto-learn from all closed/merged PRs since last run
loom init     # manual setup (loom does this automatically on first run)
loom stats    # show learning progress and conventions
```

## What Agents See

After Loom learns, your CLAUDE.md includes:

```markdown
<!-- LOOM:START -->
## Loom Conventions

Auto-learned from PR feedback by Loom.
Last updated: 2026-06-10 01:43 UTC

- **type-annotation**: All function parameters and return values must have type annotations
- **test-location**: Tests go in tests/ directory with pytest conventions
- **naming**: Use snake_case for variable names, not camelCase
<!-- LOOM:END -->
```

Agents read this at startup. They follow it automatically.

## LLM Extraction (Optional)

By default, Loom uses keyword-based extraction. For smarter extraction, set an API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-xxx   # Claude
# or
export OPENAI_API_KEY=sk-xxx          # OpenAI
```

With LLM extraction, Loom understands nuanced feedback and extracts cleaner, more actionable conventions.

## Team Use

`.loom/` files can be committed to your repo. Team members share the same conventions. When one person's PR teaches Loom something, everyone's agents benefit.

```bash
git add .loom/ CLAUDE.md AGENTS.md .cursorrules
git commit -m "loom: update conventions from PR feedback"
git push
```

## Files Loom Manages

| File | Agent |
|------|-------|
| `CLAUDE.md` | Claude Code |
| `AGENTS.md` | Codex CLI, GitHub Copilot |
| `.cursorrules` | Cursor IDE |

All conventions are between `<!-- LOOM:START -->` and `<!-- LOOM:END -->` markers. Loom never touches anything outside these markers.

## Requirements

- Python 3.11+
- `gh` CLI authenticated (`gh auth login`)
- Git repo with a GitHub remote

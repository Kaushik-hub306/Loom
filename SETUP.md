# Loom — Setup Guide

## What Loom does

Loom is a GitHub App that watches your PRs and makes your AI coding agents smarter with every review.

1. Someone creates a PR (human or AI agent)
2. Reviewer leaves feedback ("add type hints," "tests go in tests/")
3. PR gets merged or closed
4. Loom analyzes the feedback, extracts conventions
5. Loom updates CLAUDE.md, AGENTS.md, and .cursorrules in your repo
6. The next time ANY agent runs, it reads those conventions and writes better code

**Zero commands. Zero setup beyond install. Works across Claude Code, Codex, and Cursor.**

---

## How people use it

### Step 1: Install the GitHub App (30 seconds)

Go to the Loom app page on GitHub Marketplace. Click "Install." Pick which repos to enable it on. Done.

Alternate: `https://github.com/apps/loom-agent/installations/new`

### Step 2: That's it

No CLI. No config. No commands. Loom watches all PRs on enabled repos.

### What happens next

```
Day 1:
  Claude Code creates PR #42 → Reviewer: "No type hints" → PR rejected
  Claude Code creates PR #43 → Reviewer: "type hints look good" → PR merged

  Loom updates CLAUDE.md with:
  "All functions must have type annotations (learned from PR #42 feedback)"

Day 2:
  Developer runs: loom run claude "add a new endpoint"
  Claude reads CLAUDE.md → sees the convention → writes code WITH type hints
  PR #44 created → passes review → merged ✓

Day 7:
  Loom has learned 5 team conventions from 12 PRs
  Agent PR acceptance rate climbed from 40% to 85%
  Every agent (Claude Code, Codex, Cursor) reads the same conventions
```

### What agents see

After Loom runs, your CLAUDE.md includes:

```markdown
<!-- LOOM:START -->
## Loom Conventions

Auto-learned from PR feedback by the Loom GitHub App.
Last updated: 2026-06-10 14:30 UTC

- **type-annotation**: All function parameters and return values must have type annotations
  Example: `def get_user(user_id: int) -> User:`
- **naming**: Use snake_case for variable names, not camelCase
  Example: `user_id = get_user_id()`
- **test-location**: Tests must go in tests/ directory with pytest conventions
  Example: `tests/test_users.py`
- **error-handling**: Use Flask abort() pattern, not raw dict checks
  Example: `abort(404, description="not found")`
<!-- LOOM:END -->
```

Agents (Claude Code, Codex, Cursor) read CLAUDE.md at startup. The conventions are always loaded. The agents follow them automatically.

---

## How to deploy your own instance

### Prerequisites

- A GitHub account
- An Anthropic API key (for LLM extraction) — optional, keyword fallback is free
- A server to run the app (Render/Railway free tier works)

### 1. Deploy the server

**Option A: Render (easiest, free)**

1. Go to [render.com](https://render.com) → New Web Service
2. Connect your fork of the Loom repo
3. Build command: `pip install -e .`
4. Start command: `loom-server`
5. Add environment variables (see below)

**Option B: Railway**

1. Go to [railway.app](https://railway.app) → New Project
2. Deploy from GitHub repo
3. Set start command: `loom-server`
4. Add environment variables

**Option C: Run locally with ngrok**

```bash
pip install loom-agent
ngrok http 8000
# In another terminal:
GITHUB_TOKEN=ghp_xxx ANTHROPIC_API_KEY=sk-ant-xxx loom-server
```

### 2. Set environment variables

```
GITHUB_TOKEN=ghp_xxx           # GitHub personal access token with repo scope
ANTHROPIC_API_KEY=sk-ant-xxx   # Optional — Claude API for LLM extraction
LOOM_WEBHOOK_SECRET=random     # Any random string for webhook verification
PORT=8000
```

### 3. Create a GitHub App

1. Go to GitHub → Settings → Developer Settings → GitHub Apps → New
2. Set webhook URL to `https://your-server.com/webhook`
3. Set webhook secret to the same `LOOM_WEBHOOK_SECRET` value
4. Permissions needed:
   - **Pull requests**: Read & write
   - **Contents**: Read & write (to update CLAUDE.md)
   - **Issues**: Read (to fetch PR comments)
5. Subscribe to events: **Pull request**
6. Create the app
7. Generate a private key and install the app on your repos

### 4. Verify

Create a test PR, leave a review comment, close it. Check CLAUDE.md — it should have the Loom section with extracted conventions.

---

## Pricing model (for when this becomes a business)

| Plan | Price | Features |
|------|-------|----------|
| **Free** | $0 | 5 repos, keyword extraction, public repos only |
| **Pro** | $15/month | Unlimited repos, LLM extraction, private repos, team shared memory |
| **Team** | $50/month | Everything + team dashboard, priority support, SSO |

---

## Files Loom manages

| File | Agent |
|------|-------|
| `CLAUDE.md` | Claude Code |
| `AGENTS.md` | Codex CLI, GitHub Copilot |
| `.cursorrules` | Cursor IDE |

All conventions are stored between `<!-- LOOM:START -->` and `<!-- LOOM:END -->` markers. Loom never touches anything outside these markers. Remove the markers to opt out.

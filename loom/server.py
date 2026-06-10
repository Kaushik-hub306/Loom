"""Loom GitHub App — webhook-driven, zero-touch agent memory."""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
import uvicorn

from .extraction import extract_conventions
from .github import GitHubClient
from .configs import update_agent_configs

load_dotenv()
load_dotenv(Path.cwd() / ".loom" / ".env")

app = FastAPI(title="Loom", description="The memory layer for AI coding agents")

WEBHOOK_SECRET = os.getenv("LOOM_WEBHOOK_SECRET", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
APP_ID = os.getenv("LOOM_APP_ID", "")


def _verify_signature(body: bytes, signature: str) -> bool:
    if not WEBHOOK_SECRET:
        return True
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")

    if not _verify_signature(body, signature):
        raise HTTPException(401, "Invalid signature")

    event = request.headers.get("x-github-event", "")
    payload = json.loads(body)

    if event == "pull_request" and payload.get("action") in ("closed",):
        await _handle_pr(payload)
    elif event == "ping":
        print(f"Ping from {payload.get('repository', {}).get('full_name', 'unknown')}")

    return {"ok": True}


async def _handle_pr(payload: dict):
    pr = payload["pull_request"]
    repo = payload["repository"]["full_name"]
    pr_num = pr["number"]

    merged = pr.get("merged", False)

    if merged:
        outcome = "accepted"
        print(f"PR #{pr_num} in {repo} — MERGED (accepted)")
    else:
        outcome = "rejected"
        print(f"PR #{pr_num} in {repo} — CLOSED (rejected)")

    token = GITHUB_TOKEN or _get_installation_token(payload)
    gh = GitHubClient(token, repo)

    # Fetch review comments + issue comments
    comments = await gh.get_pr_comments(pr_num)

    # Fetch PR diff
    diff = await gh.get_pr_diff(pr_num)

    # Extract conventions using LLM
    conventions = []
    if outcome == "rejected" and comments:
        conventions = await extract_conventions(comments, diff)

    # Update agent config files in the repo
    files_updated = await update_agent_configs(gh, conventions, outcome)

    print(
        f"PR #{pr_num}: {outcome} | "
        f"{len(conventions)} convention(s) extracted | "
        f"{len(files_updated)} file(s) updated"
    )


def _get_installation_token(payload: dict) -> str:
    """Exchange installation ID for an access token (GitHub App auth)."""
    # The app should cache this. Simplified for MVP.
    raise NotImplementedError("Set GITHUB_TOKEN env var or implement App auth")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

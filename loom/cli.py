"""Loom CLI — the memory layer for AI coding agents."""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

console = Console()

LOOM_DIR_NAME = ".loom"
SUPPORTED_AGENTS = ["claude", "codex"]
MAX_CONVENTIONS_CHARS = 2000


@click.group()
def main():
    """Loom — AI coding agents that get smarter with every PR."""


def _get_loom_dir() -> Path:
    return Path.cwd() / LOOM_DIR_NAME


def _require_loom() -> Path:
    p = _get_loom_dir()
    if not p.exists():
        console.print("[red]Loom not initialized. Run `loom init` first.[/red]")
        raise SystemExit(1)
    return p


def _build_prompt(loom_dir: Path, task: str) -> str:
    conventions = (loom_dir / "conventions.md").read_text().strip()
    header = "Project conventions (learned by Loom from past PRs):"
    return f"{header}\n\n{conventions}\n\n---\n\nTask: {task}"


@main.command()
def init():
    """Initialize Loom in the current project."""
    loom_dir = _get_loom_dir()

    if loom_dir.exists():
        console.print("[yellow].loom/ already exists — nothing to do.[/yellow]")
        return

    loom_dir.mkdir()

    rules = {"rules": []}
    (loom_dir / "rules.json").write_text(json.dumps(rules, indent=2))

    conventions = (
        "# Loom Conventions\n\n"
        "No conventions learned yet. Run an agent with `loom run`, "
        "then use `loom learn` to build project memory.\n"
    )
    (loom_dir / "conventions.md").write_text(conventions)

    (loom_dir / "history.jsonl").write_text("")

    console.print("[green].loom/ initialized[/green]")
    console.print("  conventions.md — injected into agent context before each run")
    console.print("  rules.json     — structured rule store with confidence scores")
    console.print("  history.jsonl  — append-only log of every PR outcome")


@main.command()
@click.argument("agent")
@click.argument("task")
def run(agent, task):
    """Run a coding agent with Loom context injected.

    AGENT: 'claude' or 'codex'
    TASK: the prompt to send (wrap in quotes)
    """
    if agent not in SUPPORTED_AGENTS:
        console.print(f"[red]Unknown agent '{agent}'. Supported: {', '.join(SUPPORTED_AGENTS)}[/red]")
        raise SystemExit(1)

    loom_dir = _require_loom()
    prompt = _build_prompt(loom_dir, task)

    # Each agent has its own CLI convention for one-shot prompts
    if agent == "claude":
        cmd = ["claude", "-p", prompt]
    elif agent == "codex":
        cmd = ["codex", "exec", prompt]

    console.print(f"[dim]Running {agent} with Loom context...[/dim]\n")
    result = subprocess.run(cmd)
    raise SystemExit(result.returncode)


@main.command()
@click.option("--pr", required=True, type=int, help="PR number to learn from")
@click.option("--outcome", required=True, type=click.Choice(["accepted", "rejected"]))
@click.option("--repo", required=True, help="GitHub repo as owner/name")
def learn(pr, outcome, repo):
    """Learn from a PR outcome — accepted or rejected."""

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        console.print("[red]GITHUB_TOKEN or GH_TOKEN env var required.[/red]")
        raise SystemExit(1)

    loom_dir = _require_loom()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    console.print(f"[dim]Fetching PR #{pr} from {repo}...[/dim]")

    with httpx.Client(headers=headers) as client:
        # Fetch PR diff and review comments
        diff_resp = client.get(
            f"https://api.github.com/repos/{repo}/pulls/{pr}",
            headers={**headers, "Accept": "application/vnd.github.diff"},
        )
        diff_resp.raise_for_status()
        diff = diff_resp.text

        comments_resp = client.get(
            f"https://api.github.com/repos/{repo}/pulls/{pr}/comments"
        )
        comments_resp.raise_for_status()
        review_comments = [c["body"] for c in comments_resp.json()]

    # Build entry
    entry = {
        "pr": pr,
        "repo": repo,
        "outcome": outcome,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "diff_size_bytes": len(diff),
        "review_comments": review_comments,
        "rules_extracted": [],
    }

    # v1 extraction: look for anti-pattern keywords in rejection comments
    if outcome == "rejected":
        rules = _extract_rules_from_comments(review_comments)
        entry["rules_extracted"] = rules
        _update_rules(loom_dir, rules)

    # Append to history
    history_path = loom_dir / "history.jsonl"
    with open(history_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Regenerate conventions.md from accumulated rules
    _regenerate_conventions(loom_dir)

    status = "[green]accepted" if outcome == "accepted" else "[red]rejected"
    console.print(f"PR #{pr} marked as {status}[/]")
    if entry["rules_extracted"]:
        console.print(f"  [dim]{len(entry['rules_extracted'])} rule(s) extracted[/dim]")


@main.command()
def stats():
    """Show PR acceptance rate and active conventions."""
    loom_dir = _require_loom()
    history_path = loom_dir / "history.jsonl"

    if not history_path.exists() or history_path.stat().st_size == 0:
        console.print("[dim]No PR history yet. Use `loom learn` to add entries.[/dim]")
        return

    entries = []
    with open(history_path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    accepted = sum(1 for e in entries if e["outcome"] == "accepted")
    rejected = sum(1 for e in entries if e["outcome"] == "rejected")
    total = len(entries)
    rate = (accepted / total * 100) if total > 0 else 0

    table = Table(title="Loom Stats")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Total PRs", str(total))
    table.add_row("Accepted", f"[green]{accepted}[/green]")
    table.add_row("Rejected", f"[red]{rejected}[/red]")
    table.add_row("Acceptance rate", f"{rate:.0f}%")

    console.print(table)

    # Show current conventions
    rules_path = loom_dir / "rules.json"
    if rules_path.exists():
        rules = json.loads(rules_path.read_text())
        active = [r for r in rules.get("rules", []) if r.get("confidence", 0) >= 3]
        if active:
            console.print("\n[bold]Active conventions:[/bold]")
            for r in sorted(active, key=lambda x: x.get("confidence", 0), reverse=True):
                console.print(
                    f"  [{r.get('type', 'convention')}] {r['pattern']} "
                    f"[dim](confidence: {r['confidence']}/10)[/dim]"
                )


def _extract_rules_from_comments(comments):
    """v1 extraction: match keywords in rejection comments to rule types."""
    patterns = {
        "type-annotation": ["type hint", "type annotation", "typing", "mypy", ": str", ": int"],
        "indent-style": ["tab", "space", "indent"],
        "import-convention": ["import", "absolute import", "relative import"],
        "test-location": ["test", "__tests__", "test file", "test directory"],
        "error-handling": ["try", "except", "error handling", "throw", "catch", "result type"],
        "naming": ["camelCase", "snake_case", "PascalCase", "naming", "rename"],
    }
    extracted = []
    seen = set()
    for comment in comments:
        lower = comment.lower()
        for rule_type, keywords in patterns.items():
            if rule_type in seen:
                continue
            for kw in keywords:
                if kw in lower:
                    extracted.append({
                        "type": rule_type,
                        "pattern": comment.strip()[:120],
                        "confidence": 1,
                        "source": "review_comment",
                        "times_confirmed": 1,
                        "times_rejected": 0,
                    })
                    seen.add(rule_type)
                    break
    return extracted


def _update_rules(loom_dir, new_rules):
    """Merge extracted rules into rules.json, updating confidence for matches."""
    rules_path = loom_dir / "rules.json"
    existing = json.loads(rules_path.read_text()) if rules_path.exists() else {"rules": []}

    for new_rule in new_rules:
        found = False
        for existing_rule in existing["rules"]:
            if existing_rule.get("type") == new_rule["type"]:
                existing_rule["confidence"] = min(10, existing_rule.get("confidence", 1) + 1)
                existing_rule["times_confirmed"] = existing_rule.get("times_confirmed", 0) + 1
                found = True
                break
        if not found:
            existing["rules"].append(new_rule)

    rules_path.write_text(json.dumps(existing, indent=2))


def _regenerate_conventions(loom_dir):
    """Rebuild conventions.md from rules.json, capped at MAX_CONVENTIONS_CHARS."""
    rules_path = loom_dir / "rules.json"
    if not rules_path.exists():
        return

    rules = json.loads(rules_path.read_text()).get("rules", [])
    active = sorted(
        [r for r in rules if r.get("confidence", 0) >= 3],
        key=lambda x: x.get("confidence", 0),
        reverse=True,
    )

    lines = ["# Loom Conventions\n"]
    if not active:
        lines.append("No high-confidence conventions yet. Keep running agents and using `loom learn`.\n")
    else:
        lines.append("These conventions were learned from PR feedback. They are injected into every agent run.\n")
        for r in active:
            lines.append(f"- **{r['type']}**: {r['pattern']} (confidence: {r['confidence']}/10)")

    # Hard cap
    body = "\n".join(lines)
    if len(body) > MAX_CONVENTIONS_CHARS:
        body = body[:MAX_CONVENTIONS_CHARS].rsplit("\n", 1)[0] + "\n"
        body += "\n*(truncated — oldest/lowest-confidence conventions removed)*\n"

    (loom_dir / "conventions.md").write_text(body)


if __name__ == "__main__":
    main()

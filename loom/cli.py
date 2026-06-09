"""Loom CLI — the memory layer for AI coding agents."""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

LOOM_DIR_NAME = ".loom"
SUPPORTED_AGENTS = ["claude", "codex"]
MAX_CONVENTIONS_CHARS = 2000


@click.group()
def main():
    """Loom — AI coding agents that get smarter with every PR."""


# ── helpers ──────────────────────────────────────────────────────────


def _loom_dir() -> Path:
    return Path.cwd() / LOOM_DIR_NAME


def _require_loom() -> Path:
    p = _loom_dir()
    if not p.exists():
        console.print("[red]Run [bold]loom init[/bold] first.[/red]")
        raise SystemExit(1)
    return p


def _detect_repo() -> str | None:
    """Extract owner/repo from the git remote."""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        # git@github.com:owner/repo.git  or  https://github.com/owner/repo.git
        for prefix in ["git@github.com:", "https://github.com/"]:
            if prefix in url:
                path = url.split(prefix)[1].removesuffix(".git")
                return path
    except subprocess.CalledProcessError:
        pass
    return None


def _github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        console.print("[red]Set [bold]GITHUB_TOKEN[/bold] or [bold]GH_TOKEN[/bold] in your environment.[/red]")
        raise SystemExit(1)
    return token


# ── commands ─────────────────────────────────────────────────────────


@main.command()
def init():
    """Initialize Loom in the current project."""
    loom_dir = _loom_dir()

    if loom_dir.exists():
        console.print("[yellow].loom/ already exists.[/yellow]")
        return

    loom_dir.mkdir()

    rules = {"rules": []}
    (loom_dir / "rules.json").write_text(json.dumps(rules, indent=2))

    (loom_dir / "conventions.md").write_text(
        "# Loom Conventions\n\n"
        "No conventions learned yet.\n"
        "Run an agent with [bold]loom run[/bold], "
        "then use [bold]loom learn[/bold] to build project memory.\n"
    )

    (loom_dir / "history.jsonl").write_text("")

    console.print(Panel.fit(
        "[green]Loom initialized[/green]\n\n"
        "  conventions.md   injected into every agent run\n"
        "  rules.json       structured rules with confidence scores\n"
        "  history.jsonl    record of every PR outcome",
        title=".loom/"
    ))


@main.command()
@click.argument("agent")
@click.argument("task")
def run(agent, task):
    """Run a coding agent with Loom conventions injected.

    AGENT: 'claude' or 'codex'
    TASK: the prompt (wrap in quotes, e.g. "fix the login bug")
    """
    if agent not in SUPPORTED_AGENTS:
        console.print(f"[red]Unknown agent '{agent}'. Supported: {', '.join(SUPPORTED_AGENTS)}[/red]")
        raise SystemExit(1)

    loom_dir = _require_loom()
    conventions = (loom_dir / "conventions.md").read_text().strip()

    header = "Project conventions (learned by Loom from past PR feedback):"
    prompt = f"{header}\n\n{conventions}\n\n---\n\nTask: {task}"

    cmd = ["claude", "-p", prompt] if agent == "claude" else ["codex", "exec", prompt]

    # Record the run for loom learn --last
    last_run = {
        "agent": agent,
        "task": task,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (loom_dir / "last-run.json").write_text(json.dumps(last_run, indent=2))

    has_conventions = "No conventions learned yet" not in conventions
    ctx_note = "[green]conventions injected[/green]" if has_conventions else "[dim]no conventions yet[/dim]"
    console.print(f"[dim]Running {agent} ({ctx_note})...[/dim]\n")

    result = subprocess.run(cmd)
    code = result.returncode

    console.print(f"\n[dim]Agent exited with code {code}.[/dim]")
    if code == 0:
        repo = _detect_repo()
        repo_flag = f"--repo {repo}" if repo else "--repo owner/name"
        console.print(
            f"[yellow]If this created a PR, run:[/yellow]\n"
            f"  [bold]loom learn --pr <number> --outcome accepted {repo_flag}[/bold]\n"
            f"  [bold]loom learn --pr <number> --outcome rejected {repo_flag}[/bold]"
        )
    raise SystemExit(code)


@main.command()
@click.option("--pr", type=int, required=True, help="PR number")
@click.option("--outcome", type=click.Choice(["accepted", "rejected"]), required=True)
@click.option("--repo", default=None, help="GitHub repo as owner/name (auto-detected if omitted)")
@click.option("--comments/--no-comments", default=True, help="Fetch review comments (default: yes)")
def learn(pr, outcome, repo, comments):
    """Learn from a PR — update conventions from accept/reject feedback."""
    token = _github_token()

    if repo is None:
        repo = _detect_repo()
        if repo is None:
            console.print("[red]Could not detect repo. Pass [bold]--repo owner/name[/bold].[/red]")
            raise SystemExit(1)

    loom_dir = _require_loom()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "loom-agent",
    }

    console.print(f"[dim]Fetching PR #{pr} from {repo}...[/dim]")

    with httpx.Client(headers=headers) as client:
        # PR diff
        diff_resp = client.get(
            f"https://api.github.com/repos/{repo}/pulls/{pr}",
            headers={**headers, "Accept": "application/vnd.github.diff"},
        )
        if diff_resp.status_code == 404:
            console.print(f"[red]PR #{pr} not found in {repo}.[/red]")
            raise SystemExit(1)
        diff_resp.raise_for_status()
        diff = diff_resp.text

        # Review comments
        review_comments = []
        if comments:
            try:
                cmt_resp = client.get(f"https://api.github.com/repos/{repo}/pulls/{pr}/comments")
                cmt_resp.raise_for_status()
                review_comments = [c["body"] for c in cmt_resp.json()]
            except httpx.HTTPError:
                console.print("[dim]Could not fetch review comments.[/dim]")

    # Build history entry
    entry = {
        "pr": pr,
        "repo": repo,
        "outcome": outcome,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "diff_size_bytes": len(diff),
        "review_comments": review_comments,
        "rules_extracted": [],
    }

    # Extraction
    if outcome == "rejected" and review_comments:
        rules = _extract_rules(review_comments)
        entry["rules_extracted"] = rules
        _update_rules(loom_dir, rules)
    elif outcome == "accepted":
        _boost_accepted_patterns(loom_dir)

    # Append history
    history_path = loom_dir / "history.jsonl"
    with open(history_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Regenerate conventions
    _regenerate_conventions(loom_dir)

    status = "[green]accepted" if outcome == "accepted" else "[red]rejected"
    console.print(f"PR #{pr} → {status}[/]")
    if entry["rules_extracted"]:
        for r in entry["rules_extracted"]:
            console.print(f"  + {r['type']}: {r['pattern'][:80]}")
    console.print(f"  [dim]Total PRs learned: {_count_history(loom_dir)}[/dim]")


@main.command()
def stats():
    """Show PR acceptance trend and active conventions."""
    loom_dir = _require_loom()
    history_path = loom_dir / "history.jsonl"

    if not history_path.exists() or history_path.stat().st_size == 0:
        console.print("[dim]No PR history. Use [bold]loom learn[/bold] to add entries.[/dim]")
        return

    entries = _read_history(loom_dir)
    accepted = sum(1 for e in entries if e["outcome"] == "accepted")
    rejected = sum(1 for e in entries if e["outcome"] == "rejected")
    total = len(entries)
    rate = (accepted / total * 100) if total > 0 else 0

    table = Table(title="PR History")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")
    table.add_row("Total PRs", str(total))
    table.add_row("Accepted", f"[green]{accepted}[/green]")
    table.add_row("Rejected", f"[red]{rejected}[/red]")
    table.add_row("Acceptance rate", f"{rate:.0f}%")

    # Trend: split into first half vs second half
    if total >= 4:
        mid = total // 2
        first = entries[:mid]
        second = entries[mid:]
        first_rate = sum(1 for e in first if e["outcome"] == "accepted") / len(first) * 100
        second_rate = sum(1 for e in second if e["outcome"] == "accepted") / len(second) * 100
        trend = "[green]↑[/green]" if second_rate > first_rate else "[red]↓[/red]" if second_rate < first_rate else "[dim]→[/dim]"
        table.add_row(
            f"Trend (first {len(first)} vs last {len(second)})",
            f"{first_rate:.0f}% → {second_rate:.0f}% {trend}",
        )

    console.print(table)

    # Active conventions
    rules_path = loom_dir / "rules.json"
    if rules_path.exists():
        rules = json.loads(rules_path.read_text()).get("rules", [])
        active = sorted(
            [r for r in rules if r.get("confidence", 0) >= 3],
            key=lambda x: x.get("confidence", 0),
            reverse=True,
        )
        if active:
            console.print("\n[bold]Active conventions (confidence ≥ 3):[/bold]")
            for r in active:
                bar = "█" * r["confidence"]
                console.print(
                    f"  [{r.get('type', '?')}] {r['pattern'][:80]}\n"
                    f"     confidence: [green]{bar}[/green] {r['confidence']}/10"
                )

    # Show all rules including low-confidence
    if rules_path.exists():
        rules = json.loads(rules_path.read_text()).get("rules", [])
        learning = [r for r in rules if r.get("confidence", 0) < 3]
        if learning:
            console.print(f"\n[dim]Learning ({len(learning)} patterns need more confirmations):[/dim]")
            for r in learning:
                console.print(f"  [dim][{r.get('type', '?')}] {r['pattern'][:60]} (confidence: {r['confidence']}/10)[/dim]")


@main.command()
def conventions():
    """Show current conventions that will be injected."""
    loom_dir = _require_loom()
    content = (loom_dir / "conventions.md").read_text()
    console.print(Panel.fit(content, title=".loom/conventions.md"))


# ── extraction engine (v1 — keyword-based) ──────────────────────────


RULE_PATTERNS = {
    "type-annotation": ["type hint", "type annotation", "typing", "mypy", ": str", ": int", "return type"],
    "indent-style": ["tab", "space", "indent", "formatting"],
    "import-convention": ["absolute import", "relative import", "import order", "isort"],
    "test-location": ["__tests__", "test file", "test directory", "conftest", "test alongside"],
    "error-handling": ["error handling", "result type", "try-except", "unwrap", "panic"],
    "naming": ["camelCase", "snake_case", "PascalCase", "naming convention", "rename"],
}


def _extract_rules(comments):
    extracted = []
    seen = set()
    for comment in comments:
        lower = comment.lower()
        for rule_type, keywords in RULE_PATTERNS.items():
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


def _boost_accepted_patterns(loom_dir):
    """When a PR is accepted, slightly boost all active rules — the patterns worked."""
    rules_path = loom_dir / "rules.json"
    if not rules_path.exists():
        return
    existing = json.loads(rules_path.read_text())
    for rule in existing.get("rules", []):
        if rule.get("confidence", 0) >= 3:
            rule["confidence"] = min(10, rule["confidence"] + 1)
    rules_path.write_text(json.dumps(existing, indent=2))


def _regenerate_conventions(loom_dir):
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
        lines.append(
            "No high-confidence conventions yet (need 3+ confirmations per pattern).\n"
            "Keep running agents and using `loom learn`.\n"
        )
    else:
        lines.append(
            "These conventions were learned from PR feedback.\n"
            "They are injected into every agent run.\n"
        )
        for r in active:
            lines.append(f"- **{r['type']}**: {r['pattern']} (confidence: {r['confidence']}/10, confirmed {r.get('times_confirmed', '?')}x)")

    body = "\n".join(lines)
    if len(body) > MAX_CONVENTIONS_CHARS:
        body = body[:MAX_CONVENTIONS_CHARS].rsplit("\n", 1)[0] + "\n"
        body += "\n*(truncated — oldest/lowest-confidence conventions removed)*\n"

    (loom_dir / "conventions.md").write_text(body)


def _read_history(loom_dir):
    entries = []
    history_path = loom_dir / "history.jsonl"
    if history_path.exists():
        with open(history_path) as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    return entries


def _count_history(loom_dir):
    return len(_read_history(loom_dir))


if __name__ == "__main__":
    main()

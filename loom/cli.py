"""Loom — AI coding agents that learn from every PR. One command after setup."""

import asyncio
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

from .configs import update_agent_configs, AGENT_FILES
from .extraction import extract_conventions, _extract_with_keywords
from .github import GitHubClient

console = Console()
LOOM_DIR = ".loom"
AUTH_FILE = Path.home() / ".loom" / "auth.json"


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """Loom — AI coding agents that get smarter with every PR.

    Run without arguments to auto-learn from closed PRs.
    """
    if ctx.invoked_subcommand is None:
        asyncio.run(_auto())


# ── auto mode ──────────────────────────────────────────────────────


async def _auto():
    repo = _detect_repo()
    token = _get_token()

    if not _loom_dir().exists():
        _bootstrap()
        return

    with console.status("[dim]Checking for PRs to learn from...[/dim]"):
        gh = GitHubClient(token, repo)
        count = await _auto_learn(gh, repo)

    if count:
        console.print(f"[green]Learned from {count} new PR(s).[/green]\n")
    else:
        console.print("[dim]Nothing new to learn.[/dim]\n")

    _show_state()

    if not _read_history():
        console.print(
            "[dim]Create a PR with Claude Code, review it, then run [bold]loom[/bold] again.[/dim]"
        )


async def _auto_learn(gh, repo):
    if not repo:
        return 0

    loom_dir = _loom_dir()
    known = _known_prs()

    try:
        async with httpx.AsyncClient(headers=gh._headers, timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo}/pulls",
                params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 20},
            )
            resp.raise_for_status()
            prs = resp.json()
    except Exception:
        return 0

    count = 0
    for pr in prs:
        pr_num = pr["number"]
        if pr_num in known:
            continue

        if pr["merged_at"]:
            outcome = "accepted"
        elif pr["state"] == "closed":
            outcome = "rejected"
        else:
            continue

        comments = await gh.get_pr_comments(pr_num)
        diff = ""
        try:
            diff = await gh.get_pr_diff(pr_num)
        except Exception:
            pass

        conventions = []
        if outcome == "rejected" and comments:
            conventions = await extract_conventions(comments, diff)

        _save_pr_entry(pr_num, repo, outcome, comments, conventions)
        count += 1

    # Update local agent config files with all accumulated conventions
    if count:
        _update_local_configs()

    return count


# ── bootstrap ──────────────────────────────────────────────────────


def _bootstrap():
    console.print("[bold]Welcome to Loom![/bold]\n")

    loom_dir = _loom_dir()
    loom_dir.mkdir(exist_ok=True)

    (loom_dir / "rules.json").write_text(json.dumps({"rules": []}, indent=2))
    (loom_dir / "history.jsonl").write_text("")
    (loom_dir / "conventions.md").write_text(
        "# Loom Conventions\n\n"
        "Not learned yet. Run agents, review PRs, then run `loom`.\n"
    )

    # Auth
    token = _get_token()

    # Inject into CLAUDE.md if it exists
    claude_md = Path.cwd() / "CLAUDE.md"
    if claude_md.exists():
        from .configs import _build_section
        section = _build_section([])
        content = claude_md.read_text()
        if "LOOM:START" not in content:
            claude_md.write_text(content.rstrip() + "\n\n" + section + "\n")
            console.print("[dim]Injected conventions section into CLAUDE.md[/dim]")

    console.print(Panel.fit(
        "[green]Loom is ready.[/green]\n\n"
        f"  Conventions injected into: {', '.join(AGENT_FILES)}\n"
        "  Loom learns from every PR. No extra commands.\n\n"
        "  1. Create a PR with Claude Code or Codex\n"
        "  2. Review it — leave comments if you reject it\n"
        "  3. Run [bold]loom[/bold]\n\n"
        "That's it. Conventions auto-injected into agent configs.",
        title="Done"
    ))


# ── commands ───────────────────────────────────────────────────────


@main.command()
def init():
    """Set up Loom — one command, then agents learn from every PR."""
    if _loom_dir().exists():
        console.print("[yellow]Already set up. Run [bold]loom[/bold].[/yellow]")
        return
    _bootstrap()


@main.command()
def stats():
    """Show what Loom has learned."""
    _show_state()


# ── auth ───────────────────────────────────────────────────────────


def _load_token():
    if AUTH_FILE.exists():
        try:
            return json.loads(AUTH_FILE.read_text()).get("token")
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def _save_token(token):
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(
        {"token": token, "saved_at": datetime.now(timezone.utc).isoformat()}, indent=2
    ))
    AUTH_FILE.chmod(0o600)


def _get_token():
    t = _load_token() or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if t:
        return t
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            _save_token(result.stdout.strip())
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    console.print("[red]Run [bold]gh auth login[/bold] or set GITHUB_TOKEN.[/red]")
    raise SystemExit(1)


# ── helpers ────────────────────────────────────────────────────────


def _loom_dir():
    return Path.cwd() / LOOM_DIR


def _detect_repo():
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        for prefix in ["git@github.com:", "https://github.com/"]:
            if prefix in url:
                return url.split(prefix)[1].removesuffix(".git")
    except subprocess.CalledProcessError:
        pass
    return None


def _known_prs():
    history = _loom_dir() / "history.jsonl"
    if not history.exists():
        return set()
    known = set()
    for line in history.read_text().splitlines():
        if line.strip():
            try:
                known.add(json.loads(line)["pr"])
            except (json.JSONDecodeError, KeyError):
                pass
    return known


def _save_pr_entry(pr_num, repo, outcome, comments, conventions):
    entry = {
        "pr": pr_num, "repo": repo, "outcome": outcome,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "review_comments": comments,
        "conventions": conventions,
    }
    with open(_loom_dir() / "history.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")


def _read_history():
    history = _loom_dir() / "history.jsonl"
    if not history.exists():
        return []
    entries = []
    for line in history.read_text().splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


def _update_local_configs():
    """Update CLAUDE.md, AGENTS.md, .cursorrules locally with all learned conventions."""
    from .configs import _build_section, LOOM_START, LOOM_END
    import re

    history = _read_history()
    all_conventions = []
    for e in history:
        all_conventions.extend(e.get("conventions", []))

    # Deduplicate by rule text
    seen = set()
    unique = []
    for c in all_conventions:
        rule = c.get("rule", "")
        if rule and rule not in seen:
            seen.add(rule)
            unique.append(c)

    section = _build_section(unique)

    for filename in AGENT_FILES:
        path = Path.cwd() / filename
        if path.exists():
            content = path.read_text()
            if LOOM_START in content:
                content = re.sub(
                    re.escape(LOOM_START) + r".*?" + re.escape(LOOM_END),
                    section, content, flags=re.DOTALL
                )
            else:
                content = content.rstrip() + "\n\n" + section + "\n"
        else:
            content = section + "\n"

        path.write_text(content)

    if unique:
        console.print(f"[dim]Updated {len(AGENT_FILES)} agent config files with {len(unique)} conventions[/dim]")


def _show_state():
    history = _read_history()
    if not history:
        console.print("[dim]No PRs learned from yet.[/dim]")
        return

    accepted = sum(1 for e in history if e["outcome"] == "accepted")
    rejected = sum(1 for e in history if e["outcome"] == "rejected")
    total = len(history)
    rate = accepted / total * 100 if total else 0

    table = Table(title="Learning Progress")
    table.add_column("", style="dim")
    table.add_column("", justify="right")
    table.add_row("PRs learned from", str(total))
    table.add_row("Accepted", f"[green]{accepted}[/green]")
    table.add_row("Rejected", f"[red]{rejected}[/red]")
    table.add_row("Acceptance rate", f"{rate:.0f}%")

    if total >= 4:
        mid = total // 2
        first_rate = sum(1 for e in history[:mid] if e["outcome"] == "accepted") / mid * 100
        second_rate = sum(1 for e in history[mid:] if e["outcome"] == "accepted") / (total - mid) * 100
        trend = "↑" if second_rate > first_rate else "↓" if second_rate < first_rate else "→"
        color = "green" if second_rate >= first_rate else "red"
        table.add_row(f"Trend", f"{first_rate:.0f}% → {second_rate:.0f}% [{color}]{trend}[/{color}]")
    console.print(table)

    # Show conventions learned
    all_conventions = []
    for e in history:
        all_conventions.extend(e.get("conventions", []))

    if all_conventions:
        console.print(f"\n[bold]Conventions learned ({len(all_conventions)} total):[/bold]")
        seen = set()
        for c in all_conventions:
            rule = c.get("rule", c.get("pattern", ""))
            if rule and rule not in seen:
                seen.add(rule)
                console.print(f"  - {rule[:100]}")


if __name__ == "__main__":
    main()

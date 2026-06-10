"""Update agent config files (CLAUDE.md, AGENTS.md, .cursorrules) with conventions."""

import re
from datetime import datetime, timezone

from .github import GitHubClient

LOOM_START = "<!-- LOOM:START -->"
LOOM_END = "<!-- LOOM:END -->"

AGENT_FILES = [
    "CLAUDE.md",      # Claude Code
    "AGENTS.md",      # Codex CLI, GitHub Copilot
    ".cursorrules",   # Cursor IDE
]


def _build_section(conventions: list[dict]) -> str:
    if not conventions:
        return (
            f"{LOOM_START}\n"
            f"## Loom Conventions\n\n"
            f"Auto-learned from PR feedback. Nothing yet — keep reviewing PRs.\n"
            f"{LOOM_END}"
        )

    lines = [
        LOOM_START,
        "## Loom Conventions",
        "",
        "Auto-learned from PR feedback by the Loom GitHub App.",
        "These conventions are injected into every agent run.",
        f"Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]
    for c in conventions:
        lines.append(f"- **{c['type']}**: {c['rule']}")
        if c.get("example"):
            lines.append(f"  Example: `{c['example']}`")
    lines.append("")
    lines.append(LOOM_END)
    return "\n".join(lines)


async def update_agent_configs(
    gh: GitHubClient, conventions: list[dict], outcome: str
) -> list[str]:
    """Update CLAUDE.md, AGENTS.md, and .cursorrules with Loom conventions.

    Returns list of files that were updated.
    """
    section = _build_section(conventions)
    updated = []

    for filename in AGENT_FILES:
        try:
            content, sha = await gh.read_file(filename)

            if content and LOOM_START in content:
                # Replace existing section
                new_content = re.sub(
                    re.escape(LOOM_START) + r".*?" + re.escape(LOOM_END),
                    section,
                    content,
                    flags=re.DOTALL,
                )
            elif content:
                # Append to existing file
                new_content = content.rstrip() + "\n\n" + section + "\n"
            else:
                # Create new file
                new_content = section + "\n"

            if new_content != content:
                verb = "accepted" if outcome == "accepted" else "rejected"
                success = await gh.write_file(
                    filename,
                    new_content,
                    sha,
                    f"loom: learn from {verb} PR — update conventions",
                )
                if success:
                    updated.append(filename)
        except Exception as e:
            print(f"Failed to update {filename}: {e}")

    return updated

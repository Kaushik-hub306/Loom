"""Loom MCP server — three-tool memory layer for AI coding agents.

Tools:
  recall_memory  — Search shared memory for rules, conventions, and lessons
  store_outcome  — Record an outcome event, extract conventions, update store
  get_stats      — Memory store health dashboard
"""

from pathlib import Path

from mcp.server import Server
from mcp.types import Tool, TextContent

from loom.engine.rule_store import RuleStore, Rule
from loom.engine.extractor import DomainExtractor
from loom.engine.decay import DecayManager

# ---------------------------------------------------------------------------
# Domain config YAML templates (bundled; 3 of 6 domains have templates)
# ---------------------------------------------------------------------------

CODING_YML_TEMPLATE = """\
domain: coding
description: Software development conventions and best practices
confidence_thresholds:
  hard_rule: 9
  active: 3
  archive: 2
extractors:
  - type-annotation
  - naming
  - test-location
  - error-handling
  - import-style
  - formatting
  - architecture
  - documentation
keywords:
  - code
  - pr
  - review
  - test
  - type
  - bug
  - fix
  - refactor
  - deploy
  - lint
"""

SUPPORT_YML_TEMPLATE = """\
domain: support
description: Customer support and incident response patterns
confidence_thresholds:
  hard_rule: 9
  active: 3
  archive: 2
extractors:
  - escalation
  - resolution
  - communication
  - documentation
keywords:
  - ticket
  - customer
  - issue
  - incident
  - sla
  - escalation
  - runbook
  - pager
  - oncall
  - root-cause
"""

SALES_YML_TEMPLATE = """\
domain: sales
description: Sales process and deal management conventions
confidence_thresholds:
  hard_rule: 9
  active: 3
  archive: 2
extractors:
  - follow-up
  - qualification
  - objection
  - closing
keywords:
  - deal
  - prospect
  - pipeline
  - close
  - demo
  - qualification
  - followup
  - objection
  - contract
  - commit
"""

# ---------------------------------------------------------------------------
# Tool input schemas
# ---------------------------------------------------------------------------

RECALL_MEMORY_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "What to search for — a keyword, phrase, or topic",
        },
        "domain": {
            "type": "string",
            "enum": ["coding", "support", "sales", "oncall", "hiring", "design"],
            "description": "Limit search to one domain",
        },
        "min_confidence": {
            "type": "number",
            "description": "Minimum confidence score (1-10, default 1)",
        },
        "limit": {
            "type": "integer",
            "description": "Max results to return (default 10)",
        },
    },
    "required": ["query"],
}

STORE_OUTCOME_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {
            "type": "string",
            "enum": ["coding", "support", "sales", "oncall", "hiring", "design"],
            "description": "Domain this outcome belongs to",
        },
        "outcome": {
            "type": "string",
            "enum": ["accepted", "rejected", "resolved", "reopened", "won", "lost", "hired", "passed", "deployed", "rolled_back"],
            "description": "Result of the event",
        },
        "feedback": {
            "type": "string",
            "description": "Review comments, retrospective notes, or lessons learned",
        },
        "context": {
            "type": "string",
            "description": "Additional context (e.g. PR number, ticket ID, deal name)",
        },
    },
    "required": ["domain", "outcome", "feedback"],
}

GET_STATS_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {
            "type": "string",
            "enum": ["coding", "support", "sales", "oncall", "hiring", "design"],
            "description": "Filter stats to one domain",
        },
    },
    "required": [],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_store(project_root: Path) -> RuleStore:
    return RuleStore(project_root / ".loom")


def _ensure_bootstrapped(project_root: Path):
    """Create .loom/ with bundled coding, support, and sales domain configs on first use."""
    loom_dir = project_root / ".loom"
    if loom_dir.exists():
        return

    loom_dir.mkdir(parents=True, exist_ok=True)
    domains_dir = loom_dir / "domains"
    domains_dir.mkdir(exist_ok=True)

    (domains_dir / "coding.yml").write_text(CODING_YML_TEMPLATE)
    (domains_dir / "support.yml").write_text(SUPPORT_YML_TEMPLATE)
    (domains_dir / "sales.yml").write_text(SALES_YML_TEMPLATE)

    (loom_dir / "conventions.md").write_text(
        "<!-- Loom: no active conventions yet. Use store_outcome to build memory. -->\n"
    )


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------

def create_loom_server(project_root: Path) -> Server:
    """Create a configured Loom MCP server bound to *project_root*.

    The server lazily bootstraps ``.loom/`` on the first tool call.
    """
    server = Server("loom-memory")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="recall_memory",
                description=(
                    "Search shared memory for rules, conventions, and lessons "
                    "learned from past outcomes. Returns confidence-scored results "
                    "with source traces. Domain-filterable."
                ),
                inputSchema=RECALL_MEMORY_SCHEMA,
            ),
            Tool(
                name="store_outcome",
                description=(
                    "Record an outcome event (PR merged/rejected, ticket "
                    "resolved/reopened, deal won/lost). The engine extracts "
                    "conventions, updates confidence scores, and regenerates "
                    "the active conventions file."
                ),
                inputSchema=STORE_OUTCOME_SCHEMA,
            ),
            Tool(
                name="get_stats",
                description=(
                    "Get memory store health: total rules, by domain, "
                    "confidence distribution, recent archival activity. "
                    "No query needed — returns full dashboard."
                ),
                inputSchema=GET_STATS_SCHEMA,
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        _ensure_bootstrapped(project_root)
        store = _get_store(project_root)
        extractor = DomainExtractor()
        decay = DecayManager()
        conventions_path = project_root / ".loom" / "conventions.md"

        # ---- recall_memory ----
        if name == "recall_memory":
            query = arguments.get("query", "")
            domain = arguments.get("domain")
            min_conf = arguments.get("min_confidence", 1)
            limit = arguments.get("limit", 10)

            results = store.search_rules(query, domain=domain)
            results = [r for r in results if r.confidence >= min_conf][:limit]

            if not results:
                return [TextContent(
                    type="text",
                    text=f"No rules found for query '{query}'."
                )]

            lines = [f"## Results for '{query}'\n"]
            for rule in results:
                badge = "HARD" if rule.status == "hard_rule" else f"{rule.confidence:.0f}/10"
                lines.append(f"- **[{badge}] [{rule.domain}]** {rule.rule}")
                if rule.example:
                    lines.append(f"  - _Example:_ `{rule.example}`")
                if rule.source_traces:
                    for trace in rule.source_traces[-3:]:
                        lines.append(f"  - Source: {trace}")
                lines.append("")
            return [TextContent(type="text", text="\n".join(lines))]

        # ---- store_outcome ----
        elif name == "store_outcome":
            domain = arguments.get("domain", "")
            outcome = arguments.get("outcome", "")
            feedback = arguments.get("feedback", "")
            context = arguments.get("context", "")

            result = extractor.extract(feedback, domain)
            created = 0
            updated = 0

            source_trace = f"{domain}:{outcome}"
            if context:
                source_trace += f" ({context})"

            for conv in result.conventions:
                existing = store.find_similar_rule(domain, conv.type, conv.rule)
                if existing:
                    new_conf = min(10.0, existing.confidence + 1.0)
                    traces = existing.source_traces + [source_trace]
                    new_status = "hard_rule" if new_conf >= 9.0 else existing.status
                    store.update_rule(
                        existing.id,
                        confidence=new_conf,
                        source_traces=traces,
                        status=new_status,
                        rule=conv.rule if conv.rule != existing.rule else existing.rule,
                        example=conv.example or existing.example,
                    )
                    updated += 1
                else:
                    rule = Rule(
                        id="",
                        domain=domain,
                        rule_type=conv.type,
                        rule=conv.rule,
                        example=conv.example,
                        confidence=5.0,
                        status="active",
                        source_traces=[source_trace],
                    )
                    store.add_rule(rule)
                    created += 1

            # Run decay and regenerate conventions
            archived = decay.run_decay(store)
            store.regenerate_conventions(conventions_path)

            lines = [
                f"## Outcome Recorded: {domain}/{outcome}\n",
                f"Rules created: {created}",
                f"Rules reinforced: {updated}",
                f"Rules archived (decay): {archived}",
                f"\nConventions file regenerated at `.loom/conventions.md`",
            ]
            if result.conventions:
                lines.append(f"\n### Extracted Conventions")
                for conv in result.conventions:
                    lines.append(f"- **{conv.type}**: {conv.rule}")

            return [TextContent(type="text", text="\n".join(lines))]

        # ---- get_stats ----
        elif name == "get_stats":
            domain = arguments.get("domain")
            stats = store.get_stats()

            if domain:
                dom = stats["by_domain"].get(domain, {})
                output = (
                    f"### {domain} Memory Stats\n\n"
                    f"Total rules: {dom.get('total', 0)}\n"
                    f"Active: {dom.get('active', 0)}\n"
                    f"Hard rules: {dom.get('hard_rules', 0)}\n"
                    f"Average confidence: {dom.get('avg_confidence', 0):.1f}/10\n"
                )
                return [TextContent(type="text", text=output)]

            # Full dashboard
            active = stats["by_status"].get("active", 0) + stats["by_status"].get("hard_rule", 0)
            lines = [
                "## Loom Memory Store\n",
                f"Total: {stats['total_rules']} rules "
                f"({active} active, {stats['by_status'].get('archived', 0)} archived)\n",
            ]

            for dom_name in sorted(stats.get("by_domain", {}).keys()):
                dom = stats["by_domain"][dom_name]
                if dom.get("total", 0) == 0:
                    continue
                lines.append(
                    f"**{dom_name}**: {dom['total']} rules "
                    f"(avg {dom.get('avg_confidence', 0):.1f}/10, "
                    f"{dom.get('hard_rules', 0)} hard)"
                )

            dist = stats.get("confidence_distribution", {})
            lines.append(
                f"\nConfidence: 10={dist.get('10', 0)}  7-9={dist.get('7-9', 0)}  "
                f"4-6={dist.get('4-6', 0)}  1-3={dist.get('1-3', 0)}"
            )

            if stats.get("recently_archived", 0) > 0:
                lines.append(f"\nRecently archived: {stats['recently_archived']} rules")

            return [TextContent(type="text", text="\n".join(lines))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    """Entry point for ``python -m loom.mcp`` — runs the stdio MCP server."""
    import os
    import mcp.server.stdio

    project_root = Path(os.environ.get("LOOM_PROJECT_ROOT", Path.cwd()))
    server = create_loom_server(project_root)

    async with mcp.server.stdio.stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

"""Loom MCP server — exposes recall_memory, store_outcome, get_stats tools."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from loom.engine.rule_store import RuleStore
from loom.engine.domain_extractor import DomainExtractor
from loom.engine.decay_manager import DecayManager

RECALL_MEMORY_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "What to search for"},
        "domain": {"type": "string", "description": "Optional domain filter"},
        "min_confidence": {"type": "integer", "description": "Minimum confidence (1-10)", "default": 1},
        "limit": {"type": "integer", "description": "Max results to return"},
    },
    "required": ["query"],
}

STORE_OUTCOME_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Domain name"},
        "outcome": {"type": "string", "description": "accepted or rejected"},
        "feedback": {"type": "string", "description": "PR review feedback"},
        "source_url": {"type": "string", "description": "URL of the PR or review"},
    },
    "required": ["domain", "outcome", "feedback"],
}

GET_STATS_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Optional domain filter"},
    },
    "required": [],
}


@dataclass
class ToolDef:
    name: str
    description: str = ""
    inputSchema: dict = field(default_factory=dict)


@dataclass
class TextContent:
    """A single text content result with a .text attribute."""
    text: str = ""
    type: str = "text"


class LoomMCPServer:
    """MCP server that wraps Loom engine for agent tool calls."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.loom_dir = self.project_root / ".loom"
        self._bootstrapped = False

    def _bootstrap(self):
        if self._bootstrapped:
            return
        if not self.loom_dir.exists():
            self.loom_dir.mkdir(parents=True, exist_ok=True)
            (self.loom_dir / "domains").mkdir(exist_ok=True)
            _write_default_domain_configs(self.loom_dir / "domains")
            (self.loom_dir / "rules.json").write_text(json.dumps({"rules": []}, indent=2))
            (self.loom_dir / "conventions.md").write_text(
                "# Loom Conventions\n\nNot learned yet.\n"
            )
        self._bootstrapped = True

    @property
    def store(self) -> RuleStore:
        self._bootstrap()
        return RuleStore(self.loom_dir / "rules.json")

    @property
    def extractor(self) -> DomainExtractor:
        return DomainExtractor(self.loom_dir / "domains")

    @property
    def decay(self) -> DecayManager:
        return DecayManager(self.store)

    async def list_tools(self) -> list[ToolDef]:
        self._bootstrap()
        return [
            ToolDef(
                name="recall_memory",
                description="Search learned conventions and rules",
                inputSchema=RECALL_MEMORY_SCHEMA,
            ),
            ToolDef(
                name="store_outcome",
                description="Store a PR outcome and learn from feedback",
                inputSchema=STORE_OUTCOME_SCHEMA,
            ),
            ToolDef(
                name="get_stats",
                description="Get statistics about learned rules",
                inputSchema=GET_STATS_SCHEMA,
            ),
        ]

    async def call_tool(self, name: str, arguments: dict) -> list:
        self._bootstrap()
        store = self.store

        if name == "recall_memory":
            return self._handle_recall(store, arguments)
        elif name == "store_outcome":
            return self._handle_store(store, arguments)
        elif name == "get_stats":
            return self._handle_stats(store, arguments)
        else:
            return [_text_result(f"Unknown tool: {name}")]

    def _handle_recall(self, store: RuleStore, args: dict) -> list:
        query = args.get("query", "")
        domain = args.get("domain")
        min_conf = args.get("min_confidence", 1)
        limit = args.get("limit")

        results = store.search_rules(query, domain=domain, min_confidence=min_conf, limit=limit)

        if not results:
            return [_text_result("No rules found for that query.")]

        lines = [f"## Recall Results for \"{query}\"\n"]
        for r in results:
            lines.append(
                f"- [{r.domain}] **{r.rule_type}** ({r.confidence}/10): {r.rule}\n"
                f"  ID: `{r.id}` | Confirmed: {r.times_confirmed}x"
            )
            if r.example:
                lines.append(f"  Example: `{r.example}`")

        return [_text_result("\n".join(lines))]

    def _handle_store(self, store: RuleStore, args: dict) -> list:
        domain = args["domain"]
        outcome = args.get("outcome", "rejected")
        feedback = args.get("feedback", "")
        source_url = args.get("source_url", "")

        extractor = DomainExtractor(self.loom_dir / "domains")

        available = list(extractor.domains.keys()) if extractor.domains else []
        if available and domain not in available:
            return [_text_result(
                f"No domain config found for '{domain}'. "
                f"Available domains: {', '.join(available)}"
            )]

        if outcome == "rejected" and feedback:
            extracted = extractor.extract_rules(feedback, domain)
            created = 0
            for rule_data in extracted:
                store.add_rule(
                    domain=domain,
                    rule_type=rule_data["rule_type"],
                    rule=rule_data["rule"],
                    example=rule_data.get("example", ""),
                    confidence=rule_data.get("confidence", 5),
                    source_url=source_url,
                )
                created += 1

            # Regenerate conventions.md
            self._regenerate_conventions(store, domain)

            return [_text_result(
                f"## Stored Outcome\n\n"
                f"Domain: {domain}\n"
                f"Outcome: {outcome}\n"
                f"Rules created: {created}\n"
            )]
        else:
            # accepted — promote existing rules matching the feedback
            promoted = 0
            if feedback:
                for rule in list(store.rules.values()):
                    if rule.domain == domain and any(
                        kw in feedback.lower() for kw in rule.rule.lower().split()[:3]
                    ):
                        store.promote_rule(rule.id)
                        promoted += 1

            self._regenerate_conventions(store, domain)

            return [_text_result(
                f"## Stored Outcome\n\n"
                f"Domain: {domain}\n"
                f"Outcome: {outcome}\n"
                f"Rules promoted: {promoted}\n"
            )]

    def _handle_stats(self, store: RuleStore, args: dict) -> list:
        domain = args.get("domain")
        stats = store.get_domain_stats(domain)
        per_domain = store.get_all_domain_stats()

        if stats["total"] == 0:
            return [_text_result("## Stats\n\nTotal: 0 rules\n\nNothing learned yet.")]

        lines = [
            f"## Stats\n",
            f"Total: {stats['total']} rule(s)",
            f"Average confidence: {stats['avg_confidence']:.1f}/10",
            "",
        ]

        if domain:
            lines.insert(1, f"Domain: {domain}")
        elif per_domain:
            lines.append("By domain:")
            for d, s in sorted(per_domain.items()):
                lines.append(f"  - {d}: {s['total']} rule(s)")

        if stats["by_type"]:
            lines.append("\nBy type:")
            for t, count in sorted(stats["by_type"].items()):
                lines.append(f"  - {t}: {count}")

        return [_text_result("\n".join(lines))]

    def _regenerate_conventions(self, store: RuleStore, domain_filter: str | None = None):
        """Update conventions.md from current store state."""
        rules = store.get_rules_by_domain(domain_filter) if domain_filter else store.get_active_rules(min_confidence=1)

        lines = ["# Loom Conventions\n", "Auto-learned from PR feedback.\n"]
        if not rules:
            lines.append("Nothing learned yet.")
        else:
            current_domain = None
            for r in sorted(rules, key=lambda x: (x.domain, -x.confidence)):
                if r.domain != current_domain:
                    current_domain = r.domain
                    lines.append(f"\n## {current_domain}\n")
                lines.append(
                    f"- **{r.rule_type}** ({r.confidence}/10): {r.rule}\n"
                    f"  - Confirmed: {r.times_confirmed}x\n"
                )

        (self.loom_dir / "conventions.md").write_text("\n".join(lines))


def _text_result(text: str) -> TextContent:
    return TextContent(text=text)


def _write_default_domain_configs(domains_dir: Path):
    coding_yml = domains_dir / "coding.yml"
    support_yml = domains_dir / "support.yml"

    if not coding_yml.exists():
        coding_yml.write_text("""\
name: coding
description: Software engineering conventions
keywords:
  - code
  - PR
  - review
  - type hint
  - test
  - refactor
  - architecture
  - merge
rule_types:
  - type_safety
  - testing
  - error_handling
  - naming
  - architecture
  - documentation
  - formatting
  - security
""")

    if not support_yml.exists():
        support_yml.write_text("""\
name: support
description: Support and escalation conventions
keywords:
  - support
  - customer
  - escalation
  - ticket
  - response
  - SLA
  - triage
rule_types:
  - escalation
  - response_time
  - triage
  - communication
  - documentation
""")


def create_loom_server(project_root: Path) -> LoomMCPServer:
    """Create a Loom MCP server pointed at a project root."""
    return LoomMCPServer(Path(project_root))


def main():
    """Start the Loom MCP server via stdio transport."""
    from mcp.server.fastmcp import FastMCP

    project_root = Path(os.environ.get("LOOM_PROJECT_ROOT", os.getcwd()))
    loom = create_loom_server(project_root)

    mcp = FastMCP("loom")

    @mcp.tool(
        name="recall_memory",
        description="Search learned conventions and rules",
    )
    async def recall_memory(
        query: str,
        domain: str | None = None,
        min_confidence: int = 1,
        limit: int | None = None,
    ) -> str:
        result = loom._handle_recall(
            loom.store,
            {"query": query, "domain": domain, "min_confidence": min_confidence, "limit": limit},
        )
        return result[0].text

    @mcp.tool(
        name="store_outcome",
        description="Store a PR outcome and learn from feedback",
    )
    async def store_outcome(
        domain: str,
        outcome: str,
        feedback: str,
        source_url: str = "",
    ) -> str:
        result = loom._handle_store(
            loom.store,
            {"domain": domain, "outcome": outcome, "feedback": feedback, "source_url": source_url},
        )
        return result[0].text

    @mcp.tool(
        name="get_stats",
        description="Get statistics about learned rules",
    )
    async def get_stats(domain: str | None = None) -> str:
        result = loom._handle_stats(loom.store, {"domain": domain})
        return result[0].text

    mcp.run(transport="stdio")

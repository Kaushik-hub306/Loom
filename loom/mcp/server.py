"""Loom MCP server — memory layer for AI agents: learn, teach, reflect, recall, export, stats, observe.

Uses ObservationStore, CategoryRegistry, and SourceTracker when available,
with full backward compatibility for existing tool signatures and data formats.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ── Core engine imports (always available) ─────────────────────────
from loom.engine.rule_store import Rule, RuleStore
from loom.engine.domain_extractor import DomainExtractor
from loom.engine.decay_manager import DecayManager

# ── New v2 engine imports ──────────────────────────────────────────
from loom.engine.observation import Observation, ObservationType
from loom.engine.observation_store import ObservationStore
from loom.engine.category_registry import CategoryRegistry
from loom.engine.source_tracker import SourceTracker

# ── Security middleware ────────────────────────────────────────────
from loom.security import SecurityMiddleware

# ── JSON schemas for MCP tools ──────────────────────────────────────

RECALL_MEMORY_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "What to search for"},
        "domain": {"type": "string", "description": "Optional domain filter"},
        "min_confidence": {"type": "integer", "description": "Minimum confidence (1-10)", "default": 1},
        "limit": {"type": "integer", "description": "Max results to return"},
        "observation_type": {
            "type": "string",
            "description": "Optional: filter by observation type (e.g. 'rule', 'pattern', 'failure')",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional: filter by tags",
        },
        "semantic": {
            "type": "boolean",
            "description": "Use semantic (vector) search when available; falls back to keyword search otherwise",
            "default": False,
        },
    },
    "required": ["query"],
}

RECORD_OBSERVATION_SCHEMA = {
    "type": "object",
    "properties": {
        "observation": {
            "type": "string",
            "description": "The observation text to record",
        },
        "domain": {
            "type": "string",
            "description": "Domain name (e.g. 'coding', 'support')",
        },
        "observation_type": {
            "type": "string",
            "description": "Optional: observation type (e.g. 'rule', 'fact', 'decision', 'context', 'technique'). Auto-detected when not provided.",
        },
        "source_url": {
            "type": "string",
            "description": "Optional: source URL for provenance tracking",
            "default": "",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional: tags to attach to stored observations",
        },
        "private": {
            "type": "boolean",
            "description": "Skip persistent storage when true (in-memory only)",
            "default": False,
        },
        "extract": {
            "type": "boolean",
            "description": "Use LLM to extract structured observations from the text when true",
            "default": False,
        },
    },
    "required": ["observation", "domain"],
}

STORE_OUTCOME_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Domain name"},
        "outcome": {"type": "string", "description": "accepted or rejected"},
        "feedback": {"type": "string", "description": "Feedback, review comment, or observation text"},
        "source_url": {"type": "string", "description": "Optional source URL (PR, issue, doc)"},
        "observation_type": {
            "type": "string",
            "description": "Optional: observation type for stored entries (default 'rule')",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional: tags to attach to stored observations",
        },
    },
    "required": ["domain", "outcome", "feedback"],
}

GET_STATS_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Optional domain filter"},
        "observation_type": {
            "type": "string",
            "description": "Optional: filter stats by observation type",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional: filter stats by tags",
        },
    },
    "required": [],
}

LEARN_SCHEMA = {
    "type": "object",
    "properties": {
        "context": {"type": "string", "description": "What was happening (e.g., 'building a REST API', 'refactoring auth')"},
        "observation": {"type": "string", "description": "What was observed — feedback, pattern noticed, code snippet, outcome"},
        "lesson": {"type": "string", "description": "Explicit lesson to learn (if empty, extraction runs on observation)"},
        "domain": {"type": "string", "description": "Domain to store in (default: 'general')", "default": "general"},
        "confidence": {"type": "integer", "description": "Confidence 1-10 (default: 5)", "default": 5},
        "source_type": {"type": "string", "description": "Type of source — observation, pr_review, reflection, pattern", "default": "observation"},
    },
    "required": ["context", "observation"],
}

TEACH_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Domain name"},
        "rule": {"type": "string", "description": "The rule text — what to do or not do"},
        "rule_type": {"type": "string", "description": "Free-form rule type (e.g., 'naming', 'git_workflow', 'preference')"},
        "example": {"type": "string", "description": "Optional example illustrating the rule"},
        "confidence": {"type": "integer", "description": "Confidence 1-10 (default: 7)", "default": 7},
    },
    "required": ["domain", "rule", "rule_type"],
}

REFLECT_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Domain to store in"},
        "context": {"type": "string", "description": "What you were doing or building"},
        "patterns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of observed patterns (one per entry)",
        },
    },
    "required": ["domain", "patterns"],
}

EXPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Optional domain filter"},
        "format": {"type": "string", "description": "Output format: 'markdown', 'json', or 'compact'", "default": "markdown"},
        "min_confidence": {"type": "integer", "description": "Minimum confidence filter (default: 1)", "default": 1},
        "rule_type": {"type": "string", "description": "Filter by rule type"},
    },
    "required": [],
}

SET_PRIVATE_MODE_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {
            "type": "boolean",
            "description": "True to enable private mode (skips persistent writes), False to disable",
        },
    },
    "required": ["enabled"],
}

VERIFY_INTEGRITY_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
}

GET_AUDIT_LOG_SCHEMA = {
    "type": "object",
    "properties": {
        "limit": {
            "type": "integer",
            "description": "Maximum number of audit entries to return (default 50)",
            "default": 50,
        },
    },
    "required": [],
}


# ── Helper dataclasses ──────────────────────────────────────────────

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


# ══════════════════════════════════════════════════════════════════════
# LoomMCPServer
# ══════════════════════════════════════════════════════════════════════

class LoomMCPServer:
    """MCP server that wraps Loom engine for agent tool calls.

    Backward compatible: all existing tool signatures work unchanged.
    New optional parameters (observation_type, tags) are additive and
    honor sensible defaults.
    """

    V2_STORE_FILE = "store.json"
    V1_STORE_FILE = "rules.json"

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.loom_dir = self.project_root / ".loom"
        self._bootstrapped = False
        self._cached_store: ObservationStore | None = None
        self._security = SecurityMiddleware(
            store_dir=self.loom_dir,
            tokens_path=self.loom_dir / "tokens.json",
        )

    # ── bootstrap ──────────────────────────────────────────────────

    def _bootstrap(self):
        if self._bootstrapped:
            return

        if not self.loom_dir.exists() or not (self.loom_dir / "domains").exists():
            self.loom_dir.mkdir(parents=True, exist_ok=True)
            (self.loom_dir / "domains").mkdir(exist_ok=True)
            _write_default_domain_configs(self.loom_dir / "domains")

            # Write v2 store.json (ObservationStore format)
            _write_v2_store(self.loom_dir / self.V2_STORE_FILE)

            # Also write v1 rules.json for backward compat
            (self.loom_dir / self.V1_STORE_FILE).write_text(
                json.dumps({"rules": []}, indent=2)
            )

            (self.loom_dir / "conventions.md").write_text(
                "# Loom Conventions\n\nNot learned yet.\n"
            )

            # Create .gitignore for sensitive loom files
            (self.loom_dir / ".gitignore").write_text(
                "tokens.json\nintegrity.json\naudit.jsonl\nprivate.jsonl\n"
            )
        self._bootstrapped = True

    # ── store property ─────────────────────────────────────────────

    @property
    def store(self) -> ObservationStore:
        """Returns the cached ObservationStore (v2).

        Auto-migrates from v1 rules.json on first access.
        """
        self._bootstrap()
        if self._cached_store is None:
            self._cached_store = ObservationStore(self.loom_dir / self.V2_STORE_FILE)
        return self._cached_store

    @property
    def _rule_store(self) -> RuleStore:
        """RuleStore for backward-compatible fallback operations."""
        self._bootstrap()
        return RuleStore(self.loom_dir / self.V1_STORE_FILE)

    @property
    def _obs_store(self) -> ObservationStore:
        """ObservationStore alias (convenience, same as self.store)."""
        return self.store

    @property
    def extractor(self) -> DomainExtractor:
        """DomainExtractor for legacy domain validation / rule extraction."""
        return DomainExtractor(self.loom_dir / "domains")

    @property
    def decay(self) -> DecayManager:
        """DecayManager operates on the RuleStore for backward compat."""
        return DecayManager(self._rule_store)

    @property
    def _category_registry(self) -> CategoryRegistry:
        """CategoryRegistry loaded from domains directory."""
        return CategoryRegistry(self.loom_dir / "domains")

    @property
    def _source_tracker(self) -> SourceTracker:
        """SourceTracker for provenance recording."""
        return SourceTracker()

    # ── list_tools / call_tool ──────────────────────────────────────

    async def list_tools(self) -> list[ToolDef]:
        self._bootstrap()
        return [
            ToolDef(
                name="learn",
                description="Learn from observation — report what happened and what was learned",
                inputSchema=LEARN_SCHEMA,
            ),
            ToolDef(
                name="teach",
                description="Teach a rule directly — inject a convention without extraction",
                inputSchema=TEACH_SCHEMA,
            ),
            ToolDef(
                name="reflect",
                description="Reflect on completed work — extract patterns from multiple observations",
                inputSchema=REFLECT_SCHEMA,
            ),
            ToolDef(
                name="recall_memory",
                description="Search learned conventions and rules",
                inputSchema=RECALL_MEMORY_SCHEMA,
            ),
            ToolDef(
                name="export",
                description="Export learned rules in structured formats (markdown, json, compact)",
                inputSchema=EXPORT_SCHEMA,
            ),
            ToolDef(
                name="get_stats",
                description="Get statistics about learned rules",
                inputSchema=GET_STATS_SCHEMA,
            ),
            ToolDef(
                name="record_observation",
                description="Record an observation into the knowledge base with domain classification and provenance tracking",
                inputSchema=RECORD_OBSERVATION_SCHEMA,
            ),
            ToolDef(
                name="store_outcome",
                description="Store an outcome and learn from feedback (delegates to learn)",
                inputSchema=STORE_OUTCOME_SCHEMA,
            ),
            ToolDef(
                name="set_private_mode",
                description="Toggle private mode on or off for the current session (skips persistent writes when on)",
                inputSchema=SET_PRIVATE_MODE_SCHEMA,
            ),
            ToolDef(
                name="verify_integrity",
                description="Verify the integrity of the observation store (checksum audit)",
                inputSchema=VERIFY_INTEGRITY_SCHEMA,
            ),
            ToolDef(
                name="get_audit_log",
                description="Return recent entries from the audit trail",
                inputSchema=GET_AUDIT_LOG_SCHEMA,
            ),
        ]

    async def call_tool(self, name: str, arguments: dict) -> list:
        self._bootstrap()
        store = self.store  # ObservationStore

        if name == "learn":
            return self._handle_learn(store, arguments)
        elif name == "teach":
            return self._handle_teach(store, arguments)
        elif name == "reflect":
            return self._handle_reflect(store, arguments)
        elif name == "recall_memory":
            return self._handle_recall(store, arguments)
        elif name == "export":
            return self._handle_export(store, arguments)
        elif name == "get_stats":
            return self._handle_stats(store, arguments)
        elif name == "record_observation":
            return self._handle_record_observation(store, arguments)
        elif name == "store_outcome":
            return self._handle_store(store, arguments)
        elif name == "set_private_mode":
            return self._handle_set_private_mode(arguments)
        elif name == "verify_integrity":
            return self._handle_verify_integrity()
        elif name == "get_audit_log":
            return self._handle_get_audit_log(arguments)
        else:
            return [_text_result(f"Unknown tool: {name}")]

    # ── handle_recall ──────────────────────────────────────────────

    def _handle_recall(self, store: ObservationStore, args: dict) -> list:
        query: str = args.get("query", "")
        domain: str | None = args.get("domain")
        min_conf: int = args.get("min_confidence", 1)
        limit: int | None = args.get("limit")
        observation_type: str | None = args.get("observation_type")
        tags: list[str] | None = args.get("tags")
        semantic: bool = args.get("semantic", False)

        # ── Security: domain access check ─────────────────────────
        if domain and not self._security.pre_read(domain):
            return [_text_result(f"Access denied for domain: {domain}")]

        note: str | None = None

        if semantic:
            results, note = self._semantic_search(
                store=store,
                query=query,
                domain=domain,
                min_confidence=min_conf,
                limit=limit,
                observation_type=observation_type,
                tags=tags,
            )
        else:
            results = store.search(
                query=query,
                domain=domain,
                min_confidence=min_conf,
                limit=limit,
                observation_type=observation_type,
                tags=tags,
            )

        return self._format_recall_results(results, query, observation_type, tags, note=note)

    def _semantic_search(
        self,
        store: ObservationStore,
        query: str,
        domain: str | None,
        min_confidence: int,
        limit: int | None,
        observation_type: str | None,
        tags: list[str] | None,
    ) -> tuple[list[Observation], str | None]:
        """Attempt hybrid (vector + keyword) search; fall back to keyword search."""

        try:
            from loom.engine.hybrid_search import HybridSearch
        except ImportError:
            results = store.search(
                query=query,
                domain=domain,
                min_confidence=min_confidence,
                limit=limit,
                observation_type=observation_type,
                tags=tags,
            )
            return results, "Semantic search not available; using keyword search."

        hyb = HybridSearch(store)
        return hyb.search(
            query=query,
            domain=domain,
            min_confidence=min_confidence,
            limit=limit,
            observation_type=observation_type,
            tags=tags,
        ), None

    def _format_recall_results(
        self,
        results: list[Observation],
        query: str,
        observation_type: str | None = None,
        tags: list[str] | None = None,
        note: str | None = None,
    ) -> list:
        """Format recall results from ObservationStore.search() output."""
        if not results:
            filters = []
            if observation_type:
                filters.append(f"type={observation_type}")
            if tags:
                filters.append(f"tags={tags}")
            suffix = f" (filtered by {', '.join(filters)})" if filters else ""
            msg = f"No observations found for that query{suffix}."
            if note:
                msg = f"{note}\n\n{msg}"
            return [_text_result(msg)]

        lines = [f'## Recall Results for "{query}"\n']
        if note:
            lines.insert(0, f"> {note}\n")
        for obs in results:
            lines.append(
                f"- [{obs.domain}] **{obs.observation_type}** "
                f"({obs.confidence}/10): {obs.content}\n"
                f"  ID: `{obs.id}` | Confirmed: {obs.times_confirmed}x"
            )
            if obs.tags:
                lines.append(f"  Tags: {', '.join(obs.tags)}")

        return [_text_result("\n".join(lines))]


    # ── handle_store ───────────────────────────────────────────────

    def _handle_store(self, store: ObservationStore, args: dict) -> list:
        domain: str = args["domain"]
        outcome: str = args.get("outcome", "rejected")
        feedback: str = args.get("feedback", "")
        source_url: str = args.get("source_url", "")
        observation_type: str | None = args.get("observation_type")
        tags: list[str] | None = args.get("tags")

        # ── Domain validation ──────────────────────────────────────
        available = list(self.extractor.domains.keys()) if self.extractor.domains else []
        if available and domain not in available:
            return [
                _text_result(
                    f"No domain config found for '{domain}'. "
                    f"Available domains: {', '.join(available)}"
                )
            ]

        if outcome == "rejected" and feedback:
            # ── Security: pre-write pipeline ─────────────────────────
            write_data = {
                "domain": domain,
                "content": feedback,
                "feedback": feedback,
            }
            cleaned = self._security.pre_write(write_data)
            if cleaned is None:
                return [
                    _text_result(
                        "## Stored Outcome\n\n"
                        "Write skipped (private mode active or access denied)."
                    )
                ]

            # ── Classify feedback into categories via CategoryRegistry ──
            cat = self._category_registry
            classification = cat.classify(domain, cleaned["feedback"]) or {}

            # Filter to categories that actually matched (score > 0)
            matched_categories = [(c, s) for c, s in classification.items() if s > 0]
            # Sort by score descending, take top matches
            matched_categories.sort(key=lambda x: x[1], reverse=True)

            obs_type: ObservationType = observation_type or "rule"  # type: ignore[assignment]

            # ── Store an observation per matched category ───────────
            created = 0
            obs = self._obs_store
            src = self._source_tracker
            session_id = src.generate_session_id() if source_url else ""

            for category_name, score in matched_categories:
                # Confidence based on match score (1-10 scale)
                confidence = min(10, max(1, score * 2))

                new_obs = obs.add_observation(
                    domain=domain,
                    category=category_name,
                    content=cleaned["feedback"].strip()[:500],
                    observation_type=obs_type,
                    confidence=confidence,
                    source_url=source_url,
                    source_agent="mcp-server",
                    source_session=session_id,
                    tags=tags or [],
                )
                created += 1

                # Track source provenance
                if source_url:
                    src.record_source(
                        observation_id=new_obs.id,
                        agent="mcp-server",
                        session=session_id,
                        source_url=source_url,
                    )

                # ── Security: post-write audit + integrity ───────────
                try:
                    self._security.post_write(
                        new_obs,
                        action="observation_created",
                        agent="mcp-server",
                    )
                except Exception:
                    pass

            # Regenerate conventions.md
            self._regenerate_conventions(store, domain)

            return [
                _text_result(
                    f"## Stored Outcome\n\n"
                    f"Domain: {domain}\n"
                    f"Outcome: {outcome}\n"
                    f"Observations created: {created}\n"
                )
            ]
        else:
            # ── Security: pre-write pipeline ─────────────────────────
            write_data = {
                "domain": domain,
                "content": feedback,
                "feedback": feedback,
            }
            cleaned = self._security.pre_write(write_data)
            if cleaned is None:
                return [
                    _text_result(
                        "## Stored Outcome\n\n"
                        "Write skipped (private mode active or access denied)."
                    )
                ]

            # ── accepted: promote matching observations ────────────
            obs = self._obs_store
            promoted = 0
            if feedback:
                # Search for matching observations to promote
                matching = obs.search(query=feedback, domain=domain, limit=50)
                for o in matching:
                    obs.promote_observation(o.id)
                    promoted += 1
                    try:
                        self._security.post_write(
                            o,
                            action="observation_promoted",
                            agent="mcp-server",
                        )
                    except Exception:
                        pass

            return [
                _text_result(
                    f"## Stored Outcome\n\n"
                    f"Domain: {domain}\n"
                    f"Outcome: {outcome}\n"
                    f"Observations promoted: {promoted}\n"
                )
            ]

    def _handle_learn(self, store: ObservationStore, args: dict) -> list:
        """Learn from an observation — the primary general-purpose learning entry point."""
        context = args.get("context", "")
        observation = args.get("observation", "")
        lesson = args.get("lesson", "")
        domain = args.get("domain", "general")
        confidence = args.get("confidence", 5)
        source_type = args.get("source_type", "observation")

        extractor = DomainExtractor(self.loom_dir / "domains")
        available = list(extractor.domains.keys()) if extractor.domains else []
        if available and domain not in available:
            return [_text_result(
                f"No domain config found for '{domain}'. "
                f"Available domains: {', '.join(available)}"
            )]

        created = 0
        _obs = self._obs_store

        if lesson:
            _obs.add_observation(
                domain=domain,
                category="explicit_lesson",
                content=lesson.strip(),
                observation_type="rule",
                confidence=min(10, confidence + 2),
                source_url=context,
                tags=[source_type],
            )
            created = 1
        elif observation:
            extracted = extractor.extract_rules(observation, domain)
            for rule_data in extracted:
                _obs.add_observation(
                    domain=domain,
                    category=rule_data["rule_type"],
                    content=rule_data["rule"],
                    observation_type="rule",
                    confidence=rule_data.get("confidence", confidence),
                    source_url=context,
                    tags=[source_type],
                )
                created += 1

        self._regenerate_conventions(store, domain)
        return [_text_result(
            f"## Learned\n\n"
            f"Domain: {domain}\n"
            f"Context: {context}\n"
            f"Rules created: {created}\n"
        )]

    def _handle_teach(self, store: ObservationStore, args: dict) -> list:
        """Teach a rule directly — inject a convention without any extraction."""
        domain = args["domain"]
        rule_text = args["rule"]
        rule_type = args["rule_type"]
        example = args.get("example", "")
        confidence = args.get("confidence", 7)

        _obs = self._obs_store
        _obs.add_observation(
            domain=domain,
            category=rule_type,
            content=rule_text.strip(),
            observation_type="rule",
            confidence=confidence,
            source_url="explicit_teach",
        )

        self._regenerate_conventions(store, domain)
        return [_text_result(
            f"## Taught\n\n"
            f"Domain: {domain}\n"
            f"Rule type: {rule_type}\n"
            f"Rule: {rule_text.strip()}\n"
            f"Confidence: {confidence}/10\n"
        )]

    def _handle_reflect(self, store: ObservationStore, args: dict) -> list:
        """Reflect on completed work — extract rules from multiple observations."""
        domain = args["domain"]
        context = args.get("context", "")
        patterns = args.get("patterns", [])

        extractor = DomainExtractor(self.loom_dir / "domains")
        created = 0
        _obs = self._obs_store

        for pattern in patterns:
            extracted = extractor.extract_rules(pattern, domain)
            for rule_data in extracted:
                _obs.add_observation(
                    domain=domain,
                    category=rule_data["rule_type"],
                    content=rule_data["rule"],
                    observation_type="rule",
                    confidence=rule_data.get("confidence", 7),
                    source_url=context,
                    tags=["reflection"],
                )
                created += 1

        self._regenerate_conventions(store, domain)
        return [_text_result(
            f"## Reflected\n\n"
            f"Domain: {domain}\n"
            f"Patterns considered: {len(patterns)}\n"
            f"Rules created: {created}\n"
        )]

    def _handle_export(self, store: ObservationStore, args: dict) -> list:
        """Export learned rules in a structured format."""
        domain = args.get("domain")
        fmt = args.get("format", "markdown")
        min_conf = args.get("min_confidence", 1)
        rule_type = args.get("rule_type")

        rules = store.search(
            query="",
            domain=domain,
            min_confidence=min_conf,
            category=rule_type,
        )

        if not rules:
            return [_text_result("No rules to export.")]

        if fmt == "json":
            data = [r.to_dict() for r in rules]
            return [_text_result(json.dumps(data, indent=2))]

        elif fmt == "compact":
            lines = [
                f"{r.domain} | {r.category} | c{r.confidence} | {r.content}"
                for r in rules
            ]
            return [_text_result("\n".join(lines))]

        else:  # markdown
            current_domain = None
            lines = ["# Exported Rules\n"]
            for r in sorted(rules, key=lambda x: (x.domain, -x.confidence)):
                if r.domain != current_domain:
                    current_domain = r.domain
                    lines.append(f"\n## {current_domain}\n")
                lines.append(
                    f"- **{r.category}** ({r.confidence}/10): {r.content}\n"
                    f"  - Source: {r.source_agent or 'unknown'} | Confirmed: {r.times_confirmed}x"
                )
            return [_text_result("\n".join(lines))]

    # ── handle_record_observation ───────────────────────────────────

    def _handle_record_observation(self, store: ObservationStore, args: dict) -> list:
        observation: str = args["observation"]
        domain: str = args["domain"]
        observation_type: str | None = args.get("observation_type")
        source_url: str = args.get("source_url", "")
        tags: list[str] | None = args.get("tags")
        private: bool = args.get("private", False)
        extract: bool = args.get("extract", False)

        # ── Security: pre-write pipeline ──────────────────────────
        write_data = {
            "domain": domain,
            "content": observation,
            "observation_type": observation_type,
        }
        cleaned = self._security.pre_write(write_data)
        if cleaned is None:
            return [
                _text_result(
                    "## Recorded Observation\n\n"
                    "Write skipped (private mode active or access denied)."
                )
            ]
        # Use the potentially-redacted content
        observation = cleaned.get("content", observation)

        session_id = self._source_tracker.generate_session_id() if source_url else ""

        stored: list[dict] = []

        if extract:
            stored = self._extract_observations(
                text=observation,
                domain=domain,
                observation_type=observation_type,
                source_url=source_url,
                tags=tags,
                private=private,
                session_id=session_id,
                store=store,
            )

        if not stored:
            # No extraction performed or extraction produced nothing —
            # fall through to single observation from raw text.
            stored = self._record_single_observation(
                text=observation,
                domain=domain,
                observation_type=observation_type,
                source_url=source_url,
                tags=tags,
                private=private,
                session_id=session_id,
                store=store,
            )

        # ── Build summary ───────────────────────────────────────────
        total = len(stored)
        lines = [
            "## Recorded Observation",
            "",
            f"**Domain:** {domain}",
            f"**Observations created:** {total}",
        ]

        if private:
            lines.append("**Mode:** private (not persisted)")

        if extract and stored:
            lines.append("**Method:** LLM extraction")

        if stored:
            lines.append("")
            for i, entry in enumerate(stored, 1):
                lines.append(
                    f"{i}. `{entry['id']}` — **{entry.get('observation_type', 'rule')}** "
                    f"({entry.get('category', 'general')}): {entry['content'][:120]}"
                )

            # ── Security: post-write audit for each stored entry ───
            if not private:
                for entry in stored:
                    try:
                        obs = store.get_observation(entry["id"])
                        if obs:
                            self._security.post_write(
                                obs,
                                action="observation_created",
                                agent="mcp-server",
                            )
                    except Exception:
                        pass

        return [_text_result("\n".join(lines))]

    def _extract_observations(
        self,
        text: str,
        domain: str,
        observation_type: str | None,
        source_url: str,
        tags: list[str] | None,
        private: bool,
        session_id: str,
        store: ObservationStore,
    ) -> list[dict]:
        """Use LLMExtractor to parse text into structured observations.

        Falls back gracefully when LLMExtractor is not available.
        """

        try:
            from loom.semantic.llm_extractor import LLMExtractor
        except ImportError:
            try:
                from loom.engine.llm_extractor import LLMExtractor
            except ImportError:
                return []  # caller falls back to single observation

        extractor = LLMExtractor()
        extracted = extractor.extract(text)

        results: list[dict] = []
        for item in extracted:
            cat = item.get("category", "general")
            content = item.get("content", item.get("observation", item.get("text", "")))
            if not content:
                continue
            obs_type: ObservationType = item.get("observation_type", observation_type or "rule")  # type: ignore[assignment]

            obs = self._add_one_observation(
                store=store,
                domain=domain,
                category=cat,
                content=content,
                observation_type=obs_type,
                source_url=source_url,
                tags=tags,
                private=private,
                session_id=session_id,
            )
            if obs:
                results.append(obs.to_dict())

        return results

    def _record_single_observation(
        self,
        text: str,
        domain: str,
        observation_type: str | None,
        source_url: str,
        tags: list[str] | None,
        private: bool,
        session_id: str,
        store: ObservationStore,
    ) -> list[dict]:
        """Classify raw text via CategoryRegistry and store as a single observation."""

        cat = self._category_registry
        classification = cat.classify(domain, text) or {}

        # Pick the category with the highest score, fall back to "general"
        best_category = "general"
        best_score = 0
        for cat_name, score in classification.items():
            if score > best_score:
                best_score = score
                best_category = cat_name

        obs = self._add_one_observation(
            store=store,
            domain=domain,
            category=best_category,
            content=text.strip()[:500],
            observation_type=observation_type or "rule",  # type: ignore[assignment]
            source_url=source_url,
            tags=tags,
            private=private,
            session_id=session_id,
        )

        return [obs.to_dict()] if obs else []

    def _add_one_observation(
        self,
        store: ObservationStore,
        domain: str,
        category: str,
        content: str,
        observation_type: ObservationType,
        source_url: str,
        tags: list[str] | None,
        private: bool,
        session_id: str,
    ) -> Observation | None:
        """Create (or bump) a single observation. Skips persistence when *private* is True."""

        obs_id = store._make_id(domain, category, content, observation_type)
        now = store._now()

        existing = store.get_observation(obs_id)
        if existing:
            existing.confidence = min(10, existing.confidence + 1)
            existing.times_confirmed += 1
            existing.updated_at = now
            if source_url and source_url not in existing.source_urls:
                existing.source_urls.append(source_url)
            if tags:
                for t in tags:
                    if t not in existing.tags:
                        existing.tags.append(t)
            if not private:
                store._save()
            # Record provenance
            if source_url:
                self._source_tracker.record_source(
                    observation_id=existing.id,
                    agent="mcp-server",
                    session=session_id,
                    source_url=source_url,
                )
            return existing

        new_obs = Observation(
            id=obs_id,
            observation_type=observation_type,
            domain=domain,
            category=category,
            content=content,
            confidence=5,
            times_confirmed=1,
            source_urls=[source_url] if source_url else [],
            source_agent="mcp-server",
            source_session=session_id,
            tags=tags or [],
            access_scope="private" if private else "team",
            created_at=now,
            updated_at=now,
        )

        store.observations[new_obs.id] = new_obs
        if not private:
            store._save()

        if source_url:
            self._source_tracker.record_source(
                observation_id=new_obs.id,
                agent="mcp-server",
                session=session_id,
                source_url=source_url,
            )

        return new_obs

    # ── handle_stats ───────────────────────────────────────────────

    def _handle_stats(self, store: ObservationStore, args: dict) -> list:
        domain: str | None = args.get("domain")
        observation_type: str | None = args.get("observation_type")
        tags: list[str] | None = args.get("tags")

        # ── Fetch all observations, filter client-side ─────────────
        all_obs = store.search(query="", min_confidence=1)

        # Apply filters
        if domain:
            all_obs = [o for o in all_obs if o.domain == domain]
        if observation_type:
            all_obs = [o for o in all_obs if o.observation_type == observation_type]
        if tags:
            tag_set = set(tags)
            all_obs = [o for o in all_obs if set(o.tags).issuperset(tag_set)]

        total = len(all_obs)
        if total == 0:
            return [_text_result("## Stats\n\nTotal: 0 observations\n\nNothing learned yet.")]

        # Compute stats
        by_type: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        by_category: dict[str, int] = {}
        confidence_sum = 0
        for o in all_obs:
            by_type[o.observation_type] = by_type.get(o.observation_type, 0) + 1
            by_domain[o.domain] = by_domain.get(o.domain, 0) + 1
            by_category[o.category] = by_category.get(o.category, 0) + 1
            confidence_sum += o.confidence

        avg_confidence = confidence_sum / total

        lines = [
            "## Stats",
            f"Total: {total} observation(s)",
            f"Average confidence: {avg_confidence:.1f}/10",
            "",
        ]

        if domain:
            lines.insert(1, f"Domain: {domain}")
        if observation_type:
            lines.insert(2, f"Type filter: {observation_type}")
        if tags:
            lines.insert(3, f"Tag filter: {', '.join(tags)}")

        # Per-domain breakdown
        if not domain and by_domain:
            lines.append("By domain:")
            for d, count in sorted(by_domain.items()):
                lines.append(f"  - {d}: {count} observation(s)")

        if by_type:
            lines.append("\nBy type:")
            for t, count in sorted(by_type.items()):
                lines.append(f"  - {t}: {count}")

        if by_category:
            lines.append("\nBy category:")
            for c, count in sorted(by_category.items()):
                lines.append(f"  - {c}: {count}")

        return [_text_result("\n".join(lines))]

    # ── Security tool handlers ───────────────────────────────────────

    def _handle_set_private_mode(self, args: dict) -> list:
        enabled: bool = args.get("enabled", False)
        self._security.set_private_mode(enabled)
        state = "ON" if enabled else "OFF"
        return [_text_result(f"## Private Mode: {state}\n\nPersistent writes are {'skipped' if enabled else 'enabled'}.")]

    def _handle_verify_integrity(self) -> list:
        passed, message = self._security.verify_integrity()
        status = "PASSED" if passed else "FAILED"
        # Log the integrity check result
        try:
            action = "integrity_check_passed" if passed else "integrity_check_failed"
            self._security._audit.record(action=action, details={"message": message})
        except Exception:
            pass
        return [_text_result(f"## Integrity Check: {status}\n\n{message}")]

    def _handle_get_audit_log(self, args: dict) -> list:
        limit: int = args.get("limit", 50)
        entries = self._security.get_audit_entries(limit=limit)
        if not entries:
            return [_text_result("## Audit Log\n\nNo entries found.")]

        lines = ["## Audit Log", f"Showing up to {len(entries)} most recent entries:\n"]
        for entry in entries:
            ts = entry.get("timestamp", "unknown")
            action = entry.get("action", "unknown")
            details = entry.get("details", {})
            obs_id = details.get("observation_id", "")
            domain = details.get("domain", "")
            obs_type = details.get("observation_type", "")
            lines.append(
                f"- `{ts}` **{action}** | domain={domain} | "
                f"type={obs_type} | id=`{obs_id}`"
            )
        return [_text_result("\n".join(lines))]

    # ── regenerate_conventions ─────────────────────────────────────

    def _regenerate_conventions(
        self, store: ObservationStore, domain_filter: str | None = None
    ):
        """Update conventions.md from current store state.

        Reads from ObservationStore, filters for observation_type="rule",
        and writes a human-readable conventions.md.
        """
        obs = self._obs_store
        rules = obs.search(
            query="",
            domain=domain_filter,
            min_confidence=1,
            observation_type="rule",
        )

        lines = ["# Loom Conventions\n", "Auto-learned from observations, teaching, and reflection.\n"]
        if not rules:
            lines.append("Nothing learned yet.")
        else:
            current_domain: str | None = None
            for r in sorted(
                rules,
                key=lambda x: (x.domain, -x.confidence),
            ):
                if r.domain != current_domain:
                    current_domain = r.domain
                    lines.append(f"\n## {current_domain}\n")
                lines.append(
                    f"- **{r.category}** ({r.confidence}/10): {r.content}\n"
                    f"  - Confirmed: {r.times_confirmed}x\n"
                )

        (self.loom_dir / "conventions.md").write_text("\n".join(lines))


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _text_result(text: str) -> TextContent:
    return TextContent(text=text)


def _write_v2_store(store_path: Path) -> None:
    """Write a v2 store.json in the format expected by ObservationStore."""
    store_path.write_text(
        json.dumps(
            {
                "version": 2,
                "observations": [],
            },
            indent=2,
        )
    )


def _write_default_domain_configs(domains_dir: Path) -> None:
    """Write default domain configs in both legacy (.yml) and v2 (.yaml) formats.

    Legacy .yml files have ``name`` / ``keywords`` / ``rule_types`` keys
    and are consumed by ``DomainExtractor``.

    V2 .yaml files have ``domain`` / ``label`` / ``categories`` keys with
    per-category ``prompts`` and are consumed by ``CategoryRegistry``.
    """

    # ── v2 format (.yaml) for CategoryRegistry ─────────────────
    coding_yaml = domains_dir / "coding.yaml"
    support_yaml = domains_dir / "support.yaml"

    if not coding_yaml.exists():
        coding_yaml.write_text("""\
domain: coding
label: Software engineering conventions
categories:
  type_safety:
    label: Type Safety
    prompts:
      - type hint
      - type annotation
      - typing
      - mypy
      - return type
      - type safety
      - type-check
  testing:
    label: Testing
    prompts:
      - test
      - testing
      - unit test
      - integration test
      - pytest
      - coverage
      - test case
  error_handling:
    label: Error Handling
    prompts:
      - error handling
      - try-except
      - try/except
      - exception
      - error
      - result type
      - unwrap
  naming:
    label: Naming
    prompts:
      - camelCase
      - snake_case
      - PascalCase
      - naming convention
      - rename
      - variable name
  architecture:
    label: Architecture
    prompts:
      - separation of concerns
      - module
      - service layer
      - util
      - architecture
      - design pattern
  documentation:
    label: Documentation
    prompts:
      - docstring
      - comment
      - readme
      - document
      - docs
  formatting:
    label: Formatting
    prompts:
      - tab
      - space
      - indent
      - formatting
      - prettier
      - black
      - formatter
  security:
    label: Security
    prompts:
      - security
      - vulnerability
      - injection
      - xss
      - csrf
      - authentication
      - authorization
""")

    if not support_yaml.exists():
        support_yaml.write_text("""\
domain: support
label: Support and escalation conventions
categories:
  escalation:
    label: Escalation
    prompts:
      - escalation
      - escalate
      - P0
      - P1
      - priority
      - urgent
  response_time:
    label: Response Time
    prompts:
      - response time
      - response
      - SLA
      - delay
      - latency
  triage:
    label: Triage
    prompts:
      - triage
      - classification
      - categorize
      - first response
  communication:
    label: Communication
    prompts:
      - communication
      - comms
      - message
      - incident
      - status page
      - update
  documentation:
    label: Documentation
    prompts:
      - documentation
      - runbook
      - playbook
      - knowledge base
      - wiki
""")

    # ── Legacy format (.yml) for DomainExtractor backward compat ─
    coding_yml = domains_dir / "coding.yml"
    support_yml = domains_dir / "support.yml"

    _DOMAINS = {
        "coding": {
            "name": "coding",
            "description": "Software engineering conventions — type safety, error handling, function design",
            "keywords": [
                "code", "function", "class", "module", "import", "type",
                "variable", "algorithm", "refactor", "method",
            ],
            "rule_types": [
                "type_safety", "error_handling", "naming", "imports",
                "function_design", "control_flow", "data_structures", "performance",
            ],
            "patterns": {
                "type_safety": [
                    "type hint", "type annotation", "typing", "mypy",
                    "return type", "type safety", "type-check", "generic",
                ],
                "error_handling": [
                    "error handling", "try-except", "try/except", "exception",
                    "error", "result type", "unwrap", "abort", "fallback",
                ],
                "naming": [
                    "camelcase", "snake_case", "pascalcase", "naming convention",
                    "rename", "variable name", "function name",
                ],
                "imports": [
                    "import", "from import", "circular import", "dependency",
                    "module", "package",
                ],
                "function_design": [
                    "pure function", "side effect", "parameter", "return",
                    "function too long", "split function", "single responsibility",
                ],
                "control_flow": [
                    "if-else", "loop", "recursion", "early return",
                    "guard clause", "switch", "match case",
                ],
                "data_structures": [
                    "list", "dict", "set", "tuple", "dataclass", "class",
                    "inheritance", "composition", "interface",
                ],
                "performance": [
                    "performance", "slow", "optimize", "cache", "lazy",
                    "eager", "memory", "allocation", "bottleneck",
                ],
            },
        },
        "style": {
            "name": "style",
            "description": "Coding style, formatting, and aesthetic conventions",
            "keywords": [
                "style", "format", "indent", "spacing", "line length",
                "whitespace", "quote", "trailing", "brace", "look",
                "readability", "clean",
            ],
            "rule_types": [
                "formatting", "naming_convention", "comments", "whitespace",
                "line_length", "quotes", "trailing_commas", "brace_style",
            ],
            "patterns": {
                "formatting": [
                    "tab", "space", "indent", "formatting", "prettier",
                    "black", "formatter", "auto-format",
                ],
                "naming_convention": [
                    "camelcase", "snake_case", "pascalcase", "naming",
                    "rename", "variable name", "function name", "file name",
                ],
                "comments": [
                    "comment", "docstring", "inline comment", "TODO",
                    "FIXME", "explain", "document",
                ],
                "whitespace": [
                    "blank line", "whitespace", "trailing space",
                    "newline", "EOF", "end of file",
                ],
                "line_length": [
                    "line too long", "line length", "wrap", "break line",
                    "80", "100", "120",
                ],
                "quotes": [
                    "single quote", "double quote", "quote", "string",
                    "f-string", "template string",
                ],
                "trailing_commas": [
                    "trailing comma", "comma", "last item",
                ],
                "brace_style": [
                    "brace", "bracket", "indent style", "curly brace",
                    "same line", "new line",
                ],
            },
        },
        "architecture": {
            "name": "architecture",
            "description": "Design patterns, module structure, and system organization",
            "keywords": [
                "architecture", "design pattern", "module", "service",
                "layer", "separation", "dependency", "interface",
                "abstraction", "component",
            ],
            "rule_types": [
                "separation_of_concerns", "module_design", "service_layer",
                "dependency", "design_pattern", "abstraction",
                "interface", "composition",
            ],
            "patterns": {
                "separation_of_concerns": [
                    "separation of concerns", "single responsibility",
                    "concern", "layer", "tier",
                ],
                "module_design": [
                    "module", "package", "namespace", "file structure",
                    "folder", "directory",
                ],
                "service_layer": [
                    "service", "service layer", "API", "controller",
                    "handler", "route",
                ],
                "dependency": [
                    "dependency", "coupling", "decouple", "inversion",
                    "inject", "DI", "import",
                ],
                "design_pattern": [
                    "design pattern", "factory", "singleton", "observer",
                    "strategy", "builder", "adapter", "facade",
                    "repository",
                ],
                "abstraction": [
                    "abstraction", "abstract", "interface", "protocol",
                    "base class", "mixin",
                ],
                "interface": [
                    "interface", "API", "contract", "public", "private",
                    "internal", "export",
                ],
                "composition": [
                    "composition", "inheritance", "mixin", "trait",
                    "delegate", "wrapper",
                ],
            },
        },
        "process": {
            "name": "process",
            "description": "Workflow patterns, git practices, review norms, and CI/CD",
            "keywords": [
                "git", "commit", "branch", "merge", "PR", "pull request",
                "review", "CI", "CD", "deploy", "release", "workflow",
            ],
            "rule_types": [
                "git_workflow", "branching", "commit_message", "pr_process",
                "review_norms", "release", "deploy", "ci_cd",
            ],
            "patterns": {
                "git_workflow": [
                    "git", "workflow", "rebase", "squash", "merge commit",
                    "fast-forward",
                ],
                "branching": [
                    "branch", "branch name", "feature branch", "main",
                    "master", "develop", "hotfix",
                ],
                "commit_message": [
                    "commit message", "commit", "conventional commit",
                    "semantic commit", "changelog",
                ],
                "pr_process": [
                    "PR", "pull request", "draft", "ready for review",
                    "approve", "request changes",
                ],
                "review_norms": [
                    "review", "code review", "reviewer", "LGTM",
                    "approve", "feedback",
                ],
                "release": [
                    "release", "version", "semver", "tag", "changelog",
                    "release note",
                ],
                "deploy": [
                    "deploy", "deployment", "rollback", "staging",
                    "production", "canary", "blue-green",
                ],
                "ci_cd": [
                    "CI", "CD", "pipeline", "build", "test", "lint",
                    "check", "GitHub Actions", "Jenkins",
                ],
            },
        },
        "testing": {
            "name": "testing",
            "description": "Testing conventions, frameworks, and quality practices",
            "keywords": [
                "test", "testing", "pytest", "coverage", "mock",
                "fixture", "assert", "TDD",
            ],
            "rule_types": [
                "unit_test", "integration_test", "e2e_test", "coverage",
                "test_location", "mocking", "fixtures", "assertions",
            ],
            "patterns": {
                "unit_test": [
                    "unit test", "test", "testing", "pytest", "unittest",
                    "test case",
                ],
                "integration_test": [
                    "integration test", "integration", "e2e", "end-to-end",
                    "system test",
                ],
                "e2e_test": [
                    "e2e", "end-to-end", "browser test", "playwright",
                    "selenium", "cypress",
                ],
                "coverage": [
                    "coverage", "code coverage", "line coverage",
                    "branch coverage",
                ],
                "test_location": [
                    "test directory", "test file", "tests/",
                    "conftest", "test fixture",
                ],
                "mocking": [
                    "mock", "stub", "fake", "spy", "patch", "monkeypatch",
                ],
                "fixtures": [
                    "fixture", "setup", "teardown", "before each",
                    "after each", "conftest",
                ],
                "assertions": [
                    "assert", "expect", "should", "must", "verify",
                    "check",
                ],
            },
        },
        "security": {
            "name": "security",
            "description": "Security patterns, vulnerability prevention, and secure coding",
            "keywords": [
                "security", "vulnerability", "injection", "XSS", "CSRF",
                "auth", "authentication", "authorization", "secret",
                "encrypt", "hash",
            ],
            "rule_types": [
                "auth", "authorization", "input_validation",
                "sanitization", "secrets", "cryptography",
                "dependency_security", "threat_model",
            ],
            "patterns": {
                "auth": [
                    "auth", "authentication", "login", "logout",
                    "session", "token", "JWT", "OAuth",
                ],
                "authorization": [
                    "authorization", "permission", "access control",
                    "RBAC", "role", "scope", "capability",
                ],
                "input_validation": [
                    "input validation", "validate", "sanitize",
                    "escape", "filter input", "user input",
                ],
                "sanitization": [
                    "sanitize", "sanitization", "escape", "encode",
                    "XSS", "cross-site scripting",
                ],
                "secrets": [
                    "secret", "password", "API key", "token",
                    "credential", "env", "environment variable",
                ],
                "cryptography": [
                    "encrypt", "decrypt", "hash", "bcrypt", "sha",
                    "tls", "ssl", "https",
                ],
                "dependency_security": [
                    "dependency", "vulnerability", "CVE", "supply chain",
                    "audit", "update", "patch",
                ],
                "threat_model": [
                    "threat", "attack", "exploit", "risk", "mitigation",
                    "trust boundary",
                ],
            },
        },
        "documentation": {
            "name": "documentation",
            "description": "Documentation patterns, READMEs, API docs, and knowledge sharing",
            "keywords": [
                "document", "docs", "readme", "comment", "docstring",
                "explain", "tutorial", "guide",
            ],
            "rule_types": [
                "docstrings", "readme", "api_docs", "inline_comments",
                "changelog", "architecture_docs", "examples", "tutorials",
            ],
            "patterns": {
                "docstrings": [
                    "docstring", "doc string", "documentation string",
                    "pydoc", "jsdoc",
                ],
                "readme": [
                    "readme", "README", "getting started", "setup",
                ],
                "api_docs": [
                    "API doc", "endpoint documentation", "swagger",
                    "openapi", "route documentation",
                ],
                "inline_comments": [
                    "inline comment", "comment", "explain", "why",
                ],
                "changelog": [
                    "changelog", "change log", "version history",
                ],
                "architecture_docs": [
                    "architecture document", "ADR", "design doc",
                    "RFC", "decision record",
                ],
                "examples": [
                    "example", "code sample", "usage example",
                    "demo",
                ],
                "tutorials": [
                    "tutorial", "guide", "walkthrough", "how-to",
                ],
            },
        },
        "general": {
            "name": "general",
            "description": "Catch-all domain for preferences, conventions, best practices, and habits",
            "keywords": [
                "always", "never", "should", "must", "prefer",
                "convention", "best practice", "guideline", "rule",
                "standard", "habit", "pattern",
            ],
            "rule_types": [
                "preference", "convention", "best_practice",
                "rule_of_thumb", "guideline", "standard", "habit",
                "pattern",
            ],
            "patterns": {
                "preference": [
                    "prefer", "preference", "I like", "we like",
                ],
                "convention": [
                    "convention", "conventional", "by convention",
                ],
                "best_practice": [
                    "best practice", "recommended", "industry standard",
                ],
                "rule_of_thumb": [
                    "rule of thumb", "generally", "in general",
                    "usually", "typically",
                ],
                "guideline": [
                    "guideline", "guide", "should", "ought to",
                ],
                "standard": [
                    "standard", "standardize", "consistent",
                    "uniform",
                ],
                "habit": [
                    "always", "never", "every time", "habit",
                ],
                "pattern": [
                    "pattern", "template", "boilerplate", "scaffold",
                ],
            },
        },
    }

    for name, config in _DOMAINS.items():
        yml_file = domains_dir / f"{name}.yml"
        if yml_file.exists():
            continue
        yml_file.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))


# ══════════════════════════════════════════════════════════════════════
# Factory / entrypoint
# ══════════════════════════════════════════════════════════════════════

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
        name="learn",
        description="Learn from observation — report what happened and what was learned",
    )
    async def learn(
        context: str,
        observation: str,
        lesson: str = "",
        domain: str = "general",
        confidence: int = 5,
        source_type: str = "observation",
    ) -> str:
        result = loom._handle_learn(
            loom.store,
            {
                "context": context,
                "observation": observation,
                "lesson": lesson,
                "domain": domain,
                "confidence": confidence,
                "source_type": source_type,
            },
        )
        return result[0].text

    @mcp.tool(
        name="teach",
        description="Teach a rule directly — inject a convention without extraction",
    )
    async def teach(
        domain: str,
        rule: str,
        rule_type: str,
        example: str = "",
        confidence: int = 7,
    ) -> str:
        result = loom._handle_teach(
            loom.store,
            {
                "domain": domain,
                "rule": rule,
                "rule_type": rule_type,
                "example": example,
                "confidence": confidence,
            },
        )
        return result[0].text

    @mcp.tool(
        name="reflect",
        description="Reflect on completed work — extract patterns from multiple observations",
    )
    async def reflect(
        domain: str,
        patterns: list[str],
        context: str = "",
    ) -> str:
        result = loom._handle_reflect(
            loom.store,
            {"domain": domain, "patterns": patterns, "context": context},
        )
        return result[0].text

    @mcp.tool(
        name="recall_memory",
        description="Search learned conventions and rules",
    )
    async def recall_memory(
        query: str,
        domain: str | None = None,
        min_confidence: int = 1,
        limit: int | None = None,
        observation_type: str | None = None,
        tags: list[str] | None = None,
        semantic: bool = False,
    ) -> str:
        result = loom._handle_recall(
            loom.store,
            {
                "query": query,
                "domain": domain,
                "min_confidence": min_confidence,
                "limit": limit,
                "observation_type": observation_type,
                "tags": tags,
                "semantic": semantic,
            },
        )
        return result[0].text

    @mcp.tool(
        name="export",
        description="Export learned rules in structured formats (markdown, json, compact)",
    )
    async def export_rules(
        domain: str = "",
        format: str = "markdown",
        min_confidence: int = 1,
        rule_type: str = "",
    ) -> str:
        result = loom._handle_export(
            loom.store,
            {
                "domain": domain or None,
                "format": format,
                "min_confidence": min_confidence,
                "rule_type": rule_type or None,
            },
        )
        return result[0].text

    @mcp.tool(
        name="store_outcome",
        description="Store an outcome and learn from feedback (delegates to learn)",
    )
    async def store_outcome(
        domain: str,
        outcome: str,
        feedback: str,
        source_url: str = "",
        observation_type: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        result = loom._handle_store(
            loom.store,
            {
                "domain": domain,
                "outcome": outcome,
                "feedback": feedback,
                "source_url": source_url,
                "observation_type": observation_type,
                "tags": tags,
            },
        )
        return result[0].text

    @mcp.tool(
        name="get_stats",
        description="Get statistics about learned rules",
    )
    async def get_stats(
        domain: str | None = None,
        observation_type: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        result = loom._handle_stats(
            loom.store,
            {"domain": domain, "observation_type": observation_type, "tags": tags},
        )
        return result[0].text

    @mcp.tool(
        name="record_observation",
        description="Record an observation into the knowledge base with domain classification and provenance tracking",
    )
    async def record_observation(
        observation: str,
        domain: str,
        observation_type: str | None = None,
        source_url: str = "",
        tags: list[str] | None = None,
        private: bool = False,
        extract: bool = False,
    ) -> str:
        result = loom._handle_record_observation(
            loom.store,
            {
                "observation": observation,
                "domain": domain,
                "observation_type": observation_type,
                "source_url": source_url,
                "tags": tags,
                "private": private,
                "extract": extract,
            },
        )
        return result[0].text

    @mcp.tool(
        name="set_private_mode",
        description="Toggle private mode on or off for the current session (skips persistent writes when on)",
    )
    async def set_private_mode(enabled: bool) -> str:
        result = loom._handle_set_private_mode({"enabled": enabled})
        return result[0].text

    @mcp.tool(
        name="verify_integrity",
        description="Verify the integrity of the observation store (checksum audit)",
    )
    async def verify_integrity() -> str:
        result = loom._handle_verify_integrity()
        return result[0].text

    @mcp.tool(
        name="get_audit_log",
        description="Return recent entries from the audit trail",
    )
    async def get_audit_log(limit: int = 50) -> str:
        result = loom._handle_get_audit_log({"limit": limit})
        return result[0].text

    mcp.run(transport="stdio")

    mcp.run(transport="stdio")

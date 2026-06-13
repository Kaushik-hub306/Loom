"""Loom MCP server — the complete memory layer for AI agents.

Glen-level features:
- Auto-capture (passive observation — "nothing to write down")
- Auto-recall (relevant context pre-loaded every session)
- Org-wide shared memory (one repository for the whole org)
- Per-observation RBAC (agents see only what their user is cleared to see)
- Tiered retention (permanent org knowledge + decaying conventions)
- Auditable timeline (one queryable history of the organization)
- Instant onboarding (new hire's agent already knows the org)
- Succession capture (knowledge survives turnover)
- Coaching amplification (top performer patterns scale across the team)

Tools (18 total):
  1. learn              — Learn from observation
  2. teach              — Teach a rule directly
  3. reflect            — Reflect on completed work
  4. recall_memory      — Search learned conventions
  5. recall_relevant    — Auto-recall relevant context for a task (Glen-style)
  6. observe            — Passive observation (silent auto-capture)
  7. export             — Export rules in structured formats
  8. export_timeline    — Export organization timeline (Glen-style)
  9. get_stats          — Get statistics
 10. store_outcome      — Backward-compat PR outcome storage
 11. onboard            — Generate/share onboarding pack for a role
 12. succession         — Capture departing member's knowledge
 13. amplify            — Amplify coaching across the team
 14. retain             — Mark a rule for permanent retention
 15. set_clearance      — Set per-observation access control
 16. timeline           — Query the auditable organization timeline
 17. federate           — Ingest rules from another project
 18. session_init       — Auto-preload context at session start (Glen-style)
"""

import json
import os
import uuid
import atexit
import signal
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from loom.engine.rule_store import RuleStore, Rule
from loom.engine.domain_extractor import DomainExtractor
from loom.engine.decay_manager import DecayManager
from loom.engine.retention import RetentionPolicy
from loom.security.rbac import ClearanceLevel

# ── JSON Schemas for all 18 tools ────────────────────────────────────

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
        "retention": {"type": "string", "description": "Retention tier: 'permanent', 'long_term', 'standard', 'transient'", "default": "standard"},
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

RECALL_RELEVANT_SCHEMA = {
    "type": "object",
    "properties": {
        "task": {"type": "string", "description": "What you're about to do — Loom finds everything relevant"},
        "role": {"type": "string", "description": "Your role (e.g., 'backend-engineer', 'support-agent')"},
        "max_rules": {"type": "integer", "description": "Max rules to return (default: 15)", "default": 15},
        "include_org": {"type": "boolean", "description": "Include org-wide knowledge (default: true)", "default": True},
    },
    "required": ["task"],
}

OBSERVE_SCHEMA = {
    "type": "object",
    "properties": {
        "context": {"type": "string", "description": "What's happening right now"},
        "content": {"type": "string", "description": "The conversation, code, or decision being observed"},
        "domain": {"type": "string", "description": "Optional domain hint"},
        "sensitivity": {"type": "string", "description": "Capture sensitivity: 'silent', 'normal', 'eager'", "default": "normal"},
    },
    "required": ["context", "content"],
}

EXPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Optional domain filter"},
        "format": {"type": "string", "description": "Output format: 'markdown', 'json', or 'compact'", "default": "markdown"},
        "min_confidence": {"type": "integer", "description": "Minimum confidence filter (default: 1)", "default": 1},
        "rule_type": {"type": "string", "description": "Filter by rule type"},
        "include_org": {"type": "boolean", "description": "Include org-wide rules (default: true)", "default": True},
    },
    "required": [],
}

EXPORT_TIMELINE_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Optional domain filter"},
        "project": {"type": "string", "description": "Optional project filter"},
        "format": {"type": "string", "description": "Output format: 'markdown', 'json', 'compact'", "default": "markdown"},
        "days": {"type": "integer", "description": "Last N days (default: 30)", "default": 30},
        "limit": {"type": "integer", "description": "Max entries", "default": 50},
    },
    "required": [],
}

GET_STATS_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Optional domain filter"},
        "include_org": {"type": "boolean", "description": "Include org-wide stats (default: true)", "default": True},
    },
    "required": [],
}

STORE_OUTCOME_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Domain name"},
        "outcome": {"type": "string", "description": "accepted or rejected"},
        "feedback": {"type": "string", "description": "Feedback, review comment, or observation text"},
        "source_url": {"type": "string", "description": "Optional source URL (PR, issue, doc)"},
    },
    "required": ["domain", "outcome", "feedback"],
}

ONBOARD_SCHEMA = {
    "type": "object",
    "properties": {
        "role": {"type": "string", "description": "Role to onboard (e.g., 'backend-engineer', 'frontend-dev', 'support-agent')"},
        "format": {"type": "string", "description": "Output format: 'markdown' or 'json'", "default": "markdown"},
        "custom_notes": {"type": "string", "description": "Custom welcome message or team notes"},
        "include_succession": {"type": "boolean", "description": "Include captured succession knowledge (default: true)", "default": True},
    },
    "required": ["role"],
}

SUCCESSION_SCHEMA = {
    "type": "object",
    "properties": {
        "member": {"type": "string", "description": "Name/handle of departing member"},
        "role": {"type": "string", "description": "Their role"},
        "action": {"type": "string", "description": "Action: 'start', 'capture', 'finalize', 'list'"},
        "title": {"type": "string", "description": "(capture) Knowledge item title"},
        "detail": {"type": "string", "description": "(capture) Full detail with reasoning"},
        "importance": {"type": "integer", "description": "(capture) Importance 1-10", "default": 5},
        "category": {"type": "string", "description": "(capture) Category: 'tribal_knowledge', 'gotcha', 'design_decision', 'process', 'contact', 'tool', 'convention'", "default": "tribal_knowledge"},
        "domain": {"type": "string", "description": "(capture) Domain", "default": "general"},
    },
    "required": ["member", "role", "action"],
}

AMPLIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "rule_id": {"type": "string", "description": "Rule ID to amplify"},
        "coach": {"type": "string", "description": "Who is providing the coaching"},
        "coach_role": {"type": "string", "description": "Coach's role"},
        "amplification": {"type": "string", "description": "Why this matters, real examples, anti-patterns"},
        "target_roles": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Roles this coaching targets",
        },
    },
    "required": ["rule_id", "coach", "coach_role", "amplification"],
}

RETAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "rule_id": {"type": "string", "description": "Rule ID to retain permanently"},
        "reason": {"type": "string", "description": "Why this rule should be permanent org knowledge"},
    },
    "required": ["rule_id", "reason"],
}

SET_CLEARANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "rule_id": {"type": "string", "description": "Rule ID"},
        "clearance": {"type": "string", "description": "Clearance level: 'public', 'internal', 'confidential', 'restricted', 'secret'"},
        "allowed_roles": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Roles allowed to see this rule",
        },
        "allowed_teams": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Teams allowed to see this rule",
        },
    },
    "required": ["rule_id", "clearance"],
}

TIMELINE_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Filter by domain"},
        "project": {"type": "string", "description": "Filter by project"},
        "agent": {"type": "string", "description": "Filter by agent/user"},
        "days": {"type": "integer", "description": "Last N days (default: 30)", "default": 30},
        "limit": {"type": "integer", "description": "Max entries (default: 50)", "default": 50},
        "format": {"type": "string", "description": "Output format: 'markdown' or 'json'", "default": "markdown"},
    },
    "required": [],
}

FEDERATE_SCHEMA = {
    "type": "object",
    "properties": {
        "project_path": {"type": "string", "description": "Path to the project to federate from"},
        "project_name": {"type": "string", "description": "Name to tag imported rules with"},
    },
    "required": ["project_path"],
}

SESSION_INIT_SCHEMA = {
    "type": "object",
    "properties": {
        "task": {"type": "string", "description": "What you're working on this session"},
        "role": {"type": "string", "description": "Your role"},
        "project": {"type": "string", "description": "Project name"},
        "max_rules": {"type": "integer", "description": "Max rules to preload (default: 15)", "default": 15},
        "include_onboarding": {"type": "boolean", "description": "Include onboarding context (default: true)", "default": True},
    },
    "required": ["task"],
}


# ── Tool definitions ──────────────────────────────────────────────────

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


# ── Role → Domain mapping (for auto-recall & onboarding) ─────────────

_ROLE_DOMAIN_MAP: dict[str, list[str]] = {
    "backend-engineer": ["coding", "architecture", "testing", "security", "process"],
    "frontend-dev": ["coding", "style", "testing", "documentation"],
    "fullstack-dev": ["coding", "architecture", "style", "testing", "security", "process"],
    "devops": ["process", "security", "architecture"],
    "data-scientist": ["coding", "testing", "documentation"],
    "data-engineer": ["coding", "architecture", "process", "security"],
    "support-agent": ["general", "process", "documentation"],
    "sales-agent": ["general", "process"],
    "tech-lead": ["architecture", "process", "security", "coding"],
    "engineering-manager": ["process", "architecture", "general"],
    "security-engineer": ["security", "coding", "architecture"],
    "qa-engineer": ["testing", "process", "coding"],
    "new-grad": ["coding", "style", "testing", "process", "general"],
    "tech-writer": ["documentation", "style", "general"],
    "mobile-dev": ["coding", "style", "testing", "architecture"],
    "ml-engineer": ["coding", "testing", "architecture", "process"],
}

# ── Task → Domain mapping (for smart auto-recall) ─────────────────────

_TASK_DOMAIN_PATTERNS: list[tuple[list[str], list[str]]] = [
    (["api", "endpoint", "route", "rest", "graphql", "rpc"], ["coding", "architecture", "testing", "security"]),
    (["refactor", "clean up", "restructure", "reorganize"], ["coding", "style", "architecture"]),
    (["fix", "bug", "issue", "defect", "broken"], ["coding", "testing"]),
    (["deploy", "release", "ship", "rollout"], ["process", "security"]),
    (["test", "coverage", "qa", "quality"], ["testing"]),
    (["document", "readme", "docs", "write up"], ["documentation"]),
    (["review", "pr", "pull request", "code review"], ["process", "style", "coding"]),
    (["auth", "login", "permission", "oauth"], ["security", "coding"]),
    (["performance", "slow", "optimize", "fast"], ["coding", "architecture"]),
    (["database", "schema", "migration", "query"], ["coding", "architecture"]),
    (["ui", "ux", "frontend", "component", "css"], ["style", "coding"]),
    (["config", "setup", "install", "bootstrap"], ["process", "general"]),
    (["monitoring", "alert", "log", "observability"], ["process", "architecture"]),
    (["security", "vulnerability", "audit", "compliance"], ["security"]),
    (["ci", "cd", "pipeline", "build"], ["process"]),
    (["accessibility", "a11y"], ["style", "coding"]),
    (["onboard", "new hire", "ramp up"], ["general", "process", "documentation"]),
]


class LoomMCPServer:
    """The complete MCP server — 18 tools, Glen-level feature parity + beyond."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.loom_dir = self.project_root / ".loom"
        self._bootstrapped = False
        self._auto_observer = None
        self._context_loader = None
        self._timeline = None
        self._retention = None
        self._onboarding = None
        self._succession = None
        self._amplifier = None
        self._rbac = None
        self._org_store = None

        # ── Session state (hook layer) ──────────────────────────────
        self._session_id: str | None = None
        self._session_initialized: bool = False
        self._session_task: str = ""
        self._session_role: str = ""
        self._session_call_count: int = 0
        # Tools excluded from auto-observation (reads, not writes)
        self._observe_excluded = frozenset({
            "recall_memory", "recall_relevant", "export", "export_timeline",
            "get_stats", "timeline", "onboard", "session_init", "observe",
        })


    def _bootstrap(self):
        if self._bootstrapped:
            return
        # Auto-create project root directory if it doesn't exist
        self.project_root.mkdir(parents=True, exist_ok=True)
        if not self.loom_dir.exists():
            self.loom_dir.mkdir(parents=True, exist_ok=True)
            (self.loom_dir / "domains").mkdir(exist_ok=True)
            _write_default_domain_configs(self.loom_dir / "domains")
            (self.loom_dir / "rules.json").write_text(json.dumps({"rules": []}, indent=2))
            (self.loom_dir / "conventions.md").write_text(
                "# Loom Conventions\n\nNot learned yet.\n"
            )
            (self.loom_dir / "onboarding").mkdir(exist_ok=True)
            (self.loom_dir / "succession").mkdir(exist_ok=True)
            (self.loom_dir / "coaching").mkdir(exist_ok=True)
            (self.loom_dir / ".gitignore").write_text(
                "tokens.json\nintegrity.json\naudit.jsonl\nprivate.jsonl\npermissions.json\n"
                "timeline.jsonl\nretention.json\narchive.json\n"
            )
        self._bootstrapped = True

    # ── Lazy-loaded sub-engines ───────────────────────────────────────

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

    @property
    def auto_observer(self):
        if self._auto_observer is None:
            from loom.engine.auto_observer import AutoObserver
            from loom.engine.llm_extractor import LLMExtractor
            llm = LLMExtractor()
            self._auto_observer = AutoObserver(
                store=self.store,
                domain_extractor=self.extractor,
                llm_extractor=llm if llm.is_available else None,
            )
        return self._auto_observer

    @property
    def context_loader(self):
        if self._context_loader is None:
            from loom.engine.context_loader import ContextLoader
            self._context_loader = ContextLoader(store=self.store)
        return self._context_loader

    @property
    def timeline(self):
        if self._timeline is None:
            from loom.engine.timeline import Timeline
            self._timeline = Timeline(self.loom_dir)
        return self._timeline

    @property
    def retention(self):
        if self._retention is None:
            from loom.engine.retention import RetentionManager
            self._retention = RetentionManager(
                store_dir=self.loom_dir,
                rule_store=self.store,
                decay_manager=self.decay,
            )
        return self._retention

    @property
    def onboarding(self):
        if self._onboarding is None:
            from loom.onboarding.packs import OnboardingManager
            self._onboarding = OnboardingManager(
                store=self.store,
                packs_dir=self.loom_dir / "onboarding",
            )
        return self._onboarding

    @property
    def succession(self):
        if self._succession is None:
            from loom.onboarding.succession import SuccessionManager
            self._succession = SuccessionManager(
                store=self.store,
                store_dir=self.loom_dir,
            )
        return self._succession

    @property
    def amplifier(self):
        if self._amplifier is None:
            from loom.coaching.amplifier import CoachingAmplifier
            self._amplifier = CoachingAmplifier(
                store_dir=str(self.loom_dir),
                rule_store=self.store,
            )
        return self._amplifier

    @property
    def rbac(self):
        if self._rbac is None:
            from loom.security.rbac import RBACEngine
            self._rbac = RBACEngine(self.loom_dir / "permissions.json")
        return self._rbac

    @property
    def org_store(self):
        if self._org_store is None:
            from loom.engine.org_store import OrgStore
            # Use project-local path when LOOM_ORG_STORE is not set
            # and we have a project root — keeps test fixtures isolated.
            org_path = None
            if not os.environ.get("LOOM_ORG_STORE"):
                org_path = self.loom_dir / "org-store.json"
            self._org_store = OrgStore(path=org_path)
        return self._org_store

    # ── Tool listing ──────────────────────────────────────────────────

    def _tool_names(self) -> set[str]:
        """Return the set of Loom's own 18 tool names (for proxy routing)."""
        return {
            "learn", "teach", "reflect", "recall_memory",
            "recall_relevant", "observe", "export", "export_timeline",
            "get_stats", "store_outcome", "onboard", "succession",
            "amplify", "retain", "set_clearance", "timeline",
            "federate", "session_init",
        }

    def list_tools_sync(self) -> list[ToolDef]:
        """Return Loom tool definitions synchronously (for proxy)."""
        self._bootstrap()
        return self._tool_defs()

    def _tool_defs(self) -> list[ToolDef]:
        """The full list of 18 tool definitions."""
        return [
            # Core learning (original Loom)
            ToolDef(name="learn", description="Learn from observation — report what happened and what was learned", inputSchema=LEARN_SCHEMA),
            ToolDef(name="teach", description="Teach a rule directly — inject a convention without extraction", inputSchema=TEACH_SCHEMA),
            ToolDef(name="reflect", description="Reflect on completed work — extract patterns from multiple observations", inputSchema=REFLECT_SCHEMA),

            # Recall (original + Glen-style auto-recall)
            ToolDef(name="recall_memory", description="Search learned conventions and rules", inputSchema=RECALL_MEMORY_SCHEMA),
            ToolDef(name="recall_relevant", description="Auto-recall everything relevant to a task — Glen-style pre-loaded context", inputSchema=RECALL_RELEVANT_SCHEMA),

            # Passive observation (Glen: "nothing to write down")
            ToolDef(name="observe", description="Passively observe work — silent background capture like Glen", inputSchema=OBSERVE_SCHEMA),

            # Export
            ToolDef(name="export", description="Export learned rules in structured formats", inputSchema=EXPORT_SCHEMA),
            ToolDef(name="export_timeline", description="Export the full organization timeline — Glen-style auditable history", inputSchema=EXPORT_TIMELINE_SCHEMA),

            # Stats
            ToolDef(name="get_stats", description="Get statistics about learned rules", inputSchema=GET_STATS_SCHEMA),

            # Backward compat
            ToolDef(name="store_outcome", description="Store an outcome and learn from feedback (delegates to learn)", inputSchema=STORE_OUTCOME_SCHEMA),

            # Glen-level features
            ToolDef(name="onboard", description="Generate an onboarding pack for a new team member — Glen-style instant ramp-up", inputSchema=ONBOARD_SCHEMA),
            ToolDef(name="succession", description="Capture departing member's knowledge — Glen-style knowledge retention", inputSchema=SUCCESSION_SCHEMA),
            ToolDef(name="amplify", description="Amplify a coach's guidance across the team — Glen-style coaching amplification", inputSchema=AMPLIFY_SCHEMA),
            ToolDef(name="retain", description="Mark a rule for permanent retention — Glen-style infinite memory", inputSchema=RETAIN_SCHEMA),
            ToolDef(name="set_clearance", description="Set per-observation access control — Glen-style RBAC", inputSchema=SET_CLEARANCE_SCHEMA),
            ToolDef(name="timeline", description="Query the auditable organization timeline", inputSchema=TIMELINE_SCHEMA),
            ToolDef(name="federate", description="Ingest rules from another project into the org-wide store", inputSchema=FEDERATE_SCHEMA),
            ToolDef(name="session_init", description="Initialize a session with pre-loaded relevant context — Glen-style auto-context", inputSchema=SESSION_INIT_SCHEMA),
        ]

    async def list_tools(self) -> list[ToolDef]:
        self._bootstrap()
        return self._tool_defs()

    def _proxy_observe(self, tool_name: str, args: dict, result: dict):
        """Auto-observe a proxied (non-Loom) tool call.

        Called by the proxy for every forwarded tools/call.
        Extracts a summary observation from the tool call + result.
        """
        arg_str = json.dumps(args, default=str)[:300]
        result_str = ""
        if isinstance(result, dict):
            content = result.get("result", {}).get("content", [])
            if content and isinstance(content, list):
                texts = [c.get("text", "") for c in content if isinstance(c, dict)]
                result_str = " ".join(texts)[:500]

        obs_text = f"Tool '{tool_name}' called"
        if arg_str and arg_str != "{}":
            obs_text += f" with: {arg_str}"
        if result_str:
            obs_text += f"\nResult: {result_str}"

        try:
            observer = self.auto_observer
            observer.observe(
                context=f"tool_call:{tool_name}",
                observation=obs_text,
                source=tool_name,
            )
            if observer.should_flush():
                observer.auto_flush()
        except Exception:
            pass

    # ── Tool dispatch ─────────────────────────────────────────────────

    async def call_tool(self, name: str, arguments: dict) -> list:
        self._bootstrap()

        # ── Pre-hook: auto session_init on first call ───────────────
        session_header = self._ensure_session_init(arguments)

        # ── Pre-hook: capture task/role from session_init ───────────
        if name == "session_init":
            self._session_task = arguments.get("task", "")
            self._session_role = arguments.get("role", "")
        if name == "recall_relevant":
            self._session_task = arguments.get("task", self._session_task)

        handlers = {
            "learn": self._handle_learn,
            "teach": self._handle_teach,
            "reflect": self._handle_reflect,
            "recall_memory": self._handle_recall,
            "recall_relevant": self._handle_recall_relevant,
            "observe": self._handle_observe,
            "export": self._handle_export,
            "export_timeline": self._handle_export_timeline,
            "get_stats": self._handle_stats,
            "store_outcome": self._handle_store,
            "onboard": self._handle_onboard,
            "succession": self._handle_succession,
            "amplify": self._handle_amplify,
            "retain": self._handle_retain,
            "set_clearance": self._handle_set_clearance,
            "timeline": self._handle_timeline,
            "federate": self._handle_federate,
            "session_init": self._handle_session_init,
        }

        handler = handlers.get(name)
        if handler is None:
            return [_text_result(f"Unknown tool: {name}")]

        try:
            result = handler(arguments)
        except Exception as e:
            result = [_text_result(f"Error in tool '{name}': {e}")]

        # ── Post-hook: auto-observe this tool call ──────────────────
        self._auto_observe(name, arguments, result)

        # ── Prepend session context on first call ───────────────────
        if session_header:
            result.insert(0, _text_result(session_header))

        self._session_call_count += 1
        return result

    def _ensure_session_init(self, args: dict) -> str:
        """Auto-inject context on the first tool call of a session.

        Returns a formatted context string to prepend to the response,
        or an empty string if the session was already initialized.
        """
        if self._session_initialized:
            return ""

        self._session_id = str(uuid.uuid4())
        self._session_initialized = True

        # Use task/role from session_init or recall_relevant if available,
        # otherwise use generic defaults.
        task = self._session_task or args.get("task", "")
        role = self._session_role or args.get("role", "")

        # If this is session_init or recall_relevant itself, don't
        # inject context on top of its own response.
        # But DO run ContextLoader in the background so subsequent
        # calls benefit.
        try:
            loader = self.context_loader
            if task:
                block = loader.load_context(task_description=task, role=role)
                formatted = loader.format_context_block(block)
                self.auto_observer.on_session_start()
                return formatted
        except Exception:
            pass

        self.auto_observer.on_session_start()
        return ""

    def _auto_observe(self, tool_name: str, args: dict, result: list):
        """Record this tool call as a passive observation.

        Only observes write/judgment tools (teach, learn, amplify, etc.).
        Read-only tools (recall, export, stats, etc.) are excluded.
        """
        if tool_name in self._observe_excluded:
            return

        # Build an observation from the tool call
        try:
            obs_text = _tool_to_observation(tool_name, args)
            if not obs_text:
                return

            observer = self.auto_observer
            observer.observe(
                context=f"tool_call:{tool_name}",
                observation=obs_text,
                source=tool_name,
            )

            # Auto-flush if threshold reached
            if observer.should_flush():
                observed = observer.auto_flush()
                written = observed.get("written", 0)
                if written > 0:
                    self._regenerate_conventions(self.store)
        except Exception:
            pass  # observation failure never blocks the tool call

    def _shutdown(self):
        """Flush all observations and persist state on exit."""
        try:
            if self._auto_observer:
                report = self._auto_observer.on_session_end()
                written = report.get("total_rules_extracted", 0)
                if written > 0:
                    self._regenerate_conventions(self.store)
        except Exception:
            pass

    def _extraction_status(self) -> str:
        """Return a human-readable extraction engine status."""
        from loom.engine.llm_extractor import LLMExtractor
        llm = LLMExtractor()
        if llm.is_available:
            return f"{llm.active_provider_name} (LLM)"
        return "keyword (free)"

    # ── Core learning handlers ────────────────────────────────────────

    def _handle_learn(self, args: dict) -> list:
        context = args.get("context", "")
        observation = args.get("observation", "")
        lesson = args.get("lesson", "")
        domain = args.get("domain", "general")
        confidence = args.get("confidence", 5)
        source_type = args.get("source_type", "observation")

        extractor = DomainExtractor(self.loom_dir / "domains")
        store = self.store

        available = list(extractor.domains.keys()) if extractor.domains else []
        if available and domain not in available:
            return [_text_result(
                f"No domain config found for '{domain}'. "
                f"Available domains: {', '.join(available)}"
            )]

        created = 0
        created_rules = []

        if lesson:
            rule = store.add_rule(
                domain=domain,
                rule_type="explicit_lesson",
                rule=lesson.strip(),
                example=observation[:200] if observation else "",
                confidence=min(10, confidence + 2),
                sources=[context],
                source_type=source_type,
            )
            created_rules.append(rule)
            created = 1
        elif observation:
            extracted = extractor.extract_rules(observation, domain)
            for rule_data in extracted:
                rule = store.add_rule(
                    domain=domain,
                    rule_type=rule_data["rule_type"],
                    rule=rule_data["rule"],
                    example=rule_data.get("example", ""),
                    confidence=rule_data.get("confidence", confidence),
                    sources=[context],
                    source_type=source_type,
                )
                created_rules.append(rule)
                created += 1

        self._regenerate_conventions(store, domain)

        # Record in timeline
        for r in created_rules:
            self.timeline.record(
                action="learned",
                rule_id=r.id,
                rule_text=r.rule,
                agent="agent",
                project=str(self.project_root.name),
                decision_context=context,
                domain=r.domain,
                confidence=r.confidence,
            )

        return [_text_result(
            f"## Learned\n\n"
            f"Domain: {domain}\n"
            f"Context: {context}\n"
            f"Rules created: {created}\n"
        )]

    def _handle_teach(self, args: dict) -> list:
        domain = args["domain"]
        rule_text = args["rule"]
        rule_type = args["rule_type"]
        example = args.get("example", "")
        confidence = args.get("confidence", 7)
        retention_tier = args.get("retention", "standard")

        store = self.store
        rule = store.add_rule(
            domain=domain,
            rule_type=rule_type,
            rule=rule_text.strip(),
            example=example,
            confidence=confidence,
            sources=[],
            source_type="explicit_teach",
        )

        self._regenerate_conventions(store, domain)

        # Apply retention tier if set
        if retention_tier != "standard":
            try:
                self.retention.set_retention(rule.id, RetentionPolicy(retention_tier))
            except Exception:
                pass  # retention module may not be fully wired yet

        # Record in timeline
        self.timeline.record(
            action="taught",
            rule_id=rule.id,
            rule_text=rule.rule,
            agent="agent",
            project=str(self.project_root.name),
            decision_context=f"Explicitly taught by agent. Retention: {retention_tier}",
            domain=rule.domain,
            confidence=rule.confidence,
        )

        return [_text_result(
            f"## Taught\n\n"
            f"Domain: {domain}\n"
            f"Rule type: {rule_type}\n"
            f"Rule: {rule_text.strip()}\n"
            f"Confidence: {confidence}/10\n"
            f"Retention: {retention_tier}\n"
        )]

    def _handle_reflect(self, args: dict) -> list:
        domain = args["domain"]
        context = args.get("context", "")
        patterns = args.get("patterns", [])

        extractor = DomainExtractor(self.loom_dir / "domains")
        store = self.store
        created = 0
        created_rules = []

        for pattern in patterns:
            extracted = extractor.extract_rules(pattern, domain)
            for rule_data in extracted:
                rule = store.add_rule(
                    domain=domain,
                    rule_type=rule_data["rule_type"],
                    rule=rule_data["rule"],
                    example=rule_data.get("example", ""),
                    confidence=rule_data.get("confidence", 7),
                    sources=[context],
                    source_type="reflection",
                )
                created_rules.append(rule)
                created += 1

        self._regenerate_conventions(store, domain)

        for r in created_rules:
            self.timeline.record(
                action="reflected",
                rule_id=r.id,
                rule_text=r.rule,
                agent="agent",
                project=str(self.project_root.name),
                decision_context=context,
                domain=r.domain,
                confidence=r.confidence,
            )

        return [_text_result(
            f"## Reflected\n\n"
            f"Domain: {domain}\n"
            f"Patterns considered: {len(patterns)}\n"
            f"Rules created: {created}\n"
        )]

    # ── Recall handlers ───────────────────────────────────────────────

    def _handle_recall(self, args: dict) -> list:
        query = args.get("query", "")
        domain = args.get("domain")
        min_conf = args.get("min_confidence", 1)
        limit = args.get("limit")

        store = self.store
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

    def _handle_recall_relevant(self, args: dict) -> list:
        """Glen-style auto-recall: given a task, return everything relevant."""
        task = args.get("task", "")
        role = args.get("role", "")
        max_rules = args.get("max_rules", 15)
        include_org = args.get("include_org", True)

        store = self.store

        # Detect relevant domains from the task description
        task_lower = task.lower()
        domains_to_search = set()
        for keywords, domains in _TASK_DOMAIN_PATTERNS:
            if any(kw in task_lower for kw in keywords):
                domains_to_search.update(domains)

        # If no domains detected, search broadly
        if not domains_to_search:
            if role and role in _ROLE_DOMAIN_MAP:
                domains_to_search = set(_ROLE_DOMAIN_MAP[role])
            else:
                domains_to_search = {"coding", "architecture", "general", "process"}

        # If role specifies additional domains, include those too
        if role and role in _ROLE_DOMAIN_MAP:
            domains_to_search.update(_ROLE_DOMAIN_MAP[role])

        # Extract meaningful search keywords from the task
        _STOP_WORDS = {"a", "an", "the", "for", "of", "in", "on", "to", "at",
                        "and", "or", "but", "is", "are", "was", "were", "be",
                        "i", "you", "we", "it", "they", "build", "create",
                        "make", "do", "get", "set", "use", "add", "new",
                        "need", "want", "should", "will", "can", "could"}
        query_keywords = [w for w in task_lower.split()
                          if w not in _STOP_WORDS and len(w) > 2]

        # Collect rules from all relevant domains
        all_results: list[Rule] = []
        for domain in domains_to_search:
            # Search with the full task text first
            domain_rules = store.search_rules(
                query=task,
                domain=domain,
                min_confidence=3,
            )
            all_results.extend(domain_rules)

            # Also search with individual keywords for better recall
            for kw in query_keywords[:5]:
                kw_results = store.search_rules(
                    query=kw,
                    domain=domain,
                    min_confidence=4,
                )
                for r in kw_results:
                    if r not in all_results:
                        all_results.append(r)

        # Also do a broader keyword search for anything we missed
        broad_results = store.search_rules(query=task, min_confidence=5)
        for r in broad_results:
            if r not in all_results:
                all_results.append(r)
            if r not in all_results:
                all_results.append(r)

        # Sort by confidence and deduplicate
        seen_ids = set()
        deduped = []
        for r in sorted(all_results, key=lambda x: (x.confidence, x.times_confirmed), reverse=True):
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                deduped.append(r)

        results = deduped[:max_rules]

        if not results:
            # Check if the store has ANY rules at all
            total_rules = len(store)
            if total_rules == 0:
                return [_text_result(
                    f"## 🔍 Welcome to Loom!\n\n"
                    f"No conventions have been learned yet — this is a fresh project.\n\n"
                    f"**Getting started:**\n"
                    f"- Start coding and Loom will auto-observe patterns from your work\n"
                    f"- Or use the `teach` tool to add your first convention directly:\n"
                    f"  `teach(domain=\"coding\", rule=\"Use type hints everywhere\", "
                    f"rule_type=\"type_safety\")`\n"
                    f"- Use `learn` to extract rules from an observation or feedback\n\n"
                    f"Once conventions are in the store, `recall_relevant` will find "
                    f"them automatically based on your task."
                )]
            return [_text_result(
                f"## 🔍 No relevant conventions found for \"{task}\"\n\n"
                f"Searched domains: {', '.join(sorted(domains_to_search))}\n\n"
                f"Try teaching some conventions first, or check back after "
                f"the team has used Loom for a while."
            )]

        # Format the output Glen-style
        lines = [
            f"<!-- LOOM:AUTO_CONTEXT -->",
            f"## 🔍 Relevant Conventions (from Loom)",
            f"",
            f"*Auto-loaded for task: \"{task}\"*",
            f"",
        ]

        # Top 3 most important
        top3 = results[:3]
        if top3:
            lines.append("### ⚡ Top Reminders")
            for r in top3:
                lines.append(f"1. **{r.rule}** ({r.confidence}/10)")
            lines.append("")

        # Group by domain
        by_domain: dict[str, list[Rule]] = {}
        for r in results:
            by_domain.setdefault(r.domain, []).append(r)

        lines.append("### By Domain")
        for domain in sorted(by_domain.keys()):
            lines.append(f"")
            lines.append(f"#### {domain}")
            for r in by_domain[domain]:
                lines.append(f"- **{r.rule_type}** ({r.confidence}/10): {r.rule}")
                if r.example:
                    lines.append(f"  Example: `{r.example}`")
                lines.append(f"  *Confirmed {r.times_confirmed}x*")

        # Coaching amplifications if any
        try:
            amp = self.amplifier
            coaching = amp.get_coaching_for_role(role) if role else []
            if coaching:
                lines.append("")
                lines.append("### 📢 Coaching Amplifications")
                for c in coaching[:5]:
                    lines.append(f"- **{c.original_rule or ''}** — by {c.coach or ''}")
                    if c.amplification:
                        lines.append(f"  {c.amplification[:200]}...")
        except Exception:
            pass

        # Org-wide context if requested
        if include_org:
            try:
                org = self.org_store
                org_rules = org.get_cross_project_context(
                    project=str(self.project_root.name),
                    query=task,
                )
                if org_rules:
                    lines.append("")
                    lines.append("### 🌐 Org-Wide Knowledge")
                    for r in org_rules[:5]:
                        lines.append(f"- [{r.project or 'org'}] **{r.rule_type or ''}**: {r.rule or ''}")
            except Exception:
                pass

        return [_text_result("\n".join(lines))]

    def _handle_observe(self, args: dict) -> list:
        """Glen-style passive observation — silent background capture."""
        context = args.get("context", "")
        content = args.get("content", "")
        domain = args.get("domain", "")
        sensitivity = args.get("sensitivity", "normal")

        observer = self.auto_observer
        observer.config.sensitivity = sensitivity

        # Auto-detect domain if not specified
        if not domain:
            extractor = DomainExtractor(self.loom_dir / "domains")
            detected = extractor.detect_domain(content)
            domain = detected or "general"

        # Feed to the observer
        observer.observe(context=context, observation=content, domain=domain)

        # Check if we should flush
        if observer.should_flush():
            result = observer.flush(domain)
            written = result.get("written", 0)
            self._regenerate_conventions(self.store, domain)
            return [_text_result(
                f"## 👁️ Observed & Learned\n\n"
                f"Domain: {domain}\n"
                f"Context: {context}\n"
                f"Rules auto-extracted: {written}\n"
                f"Buffer remaining: {observer.buffer_size}\n"
            )]

        return [_text_result(
            f"## 👁️ Observed\n\n"
            f"Domain: {domain}\n"
            f"Buffer size: {observer.buffer_size}\n"
            f"Sensitivity: {sensitivity}\n"
        )]

    # ── Export handlers ───────────────────────────────────────────────

    def _handle_export(self, args: dict) -> list:
        domain = args.get("domain")
        fmt = args.get("format", "markdown")
        min_conf = args.get("min_confidence", 1)
        rule_type = args.get("rule_type")
        include_org = args.get("include_org", True)

        store = self.store
        rules = store.search_rules(
            query="",
            domain=domain,
            min_confidence=min_conf,
            rule_type=rule_type,
        )

        if not rules:
            return [_text_result("No rules to export.")]

        if fmt == "json":
            data = [r.to_dict() for r in rules]
            # Include org rules if requested
            if include_org:
                try:
                    org_rules = self.org_store.get_org_rules(min_confidence=min_conf)
                    data.append({"__org_rules__": len(org_rules), "org_store": "use export_timeline for full org export"})
                except Exception:
                    pass
            return [_text_result(json.dumps(data, indent=2))]

        elif fmt == "compact":
            lines = [f"{r.domain} | {r.rule_type} | c{r.confidence} | {r.rule}" for r in rules]
            return [_text_result("\n".join(lines))]

        else:  # markdown
            current_domain = None
            lines = ["# Exported Rules\n"]
            for r in sorted(rules, key=lambda x: (x.domain, -x.confidence)):
                if r.domain != current_domain:
                    current_domain = r.domain
                    lines.append(f"\n## {current_domain}\n")
                lines.append(
                    f"- **{r.rule_type}** ({r.confidence}/10): {r.rule}\n"
                    f"  - Source: {r.source_type or 'unknown'} | Confirmed: {r.times_confirmed}x"
                )
            return [_text_result("\n".join(lines))]

    def _handle_export_timeline(self, args: dict) -> list:
        """Glen-style auditable timeline export."""
        domain = args.get("domain")
        project = args.get("project")
        fmt = args.get("format", "markdown")
        days = args.get("days", 30)
        limit = args.get("limit", 50)

        date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        entries = self.timeline.query(
            domain=domain,
            project=project,
            date_from=date_from,
            limit=limit,
        )

        if not entries:
            return [_text_result("## Timeline\n\nNo entries found for the selected period.")]

        if fmt == "json":
            return [_text_result(json.dumps([e.to_dict() for e in entries], indent=2))]

        if fmt == "compact":
            lines = []
            for e in entries:
                ts = e.timestamp[:10] if e.timestamp else ""
                lines.append(
                    f"{ts} | {e.action} | {e.domain} | "
                    f"{e.rule_text[:80]}"
                )
            return [_text_result("\n".join(lines))]

        # Markdown timeline
        lines = [f"## 📅 Organization Timeline\n", f"Last {days} days\n"]

        # Group by date
        by_date: dict[str, list] = {}
        for e in entries:
            date_key = e.timestamp[:10] if e.timestamp else "unknown"
            by_date.setdefault(date_key, []).append(e)

        for date_key in sorted(by_date.keys(), reverse=True):
            lines.append(f"\n### {date_key}")
            for e in by_date[date_key]:
                ts = e.timestamp if e.timestamp else ""
                time_str = ts[11:16] if len(ts) > 11 else ""
                action = e.action or "unknown"
                domain = e.domain or ""
                rule_text = (e.rule_text or "")[:120]
                agent = e.agent or "unknown"
                project = e.project or ""
                ctx = (e.decision_context or "")[:150]

                icon = {"learned": "🧠", "taught": "📖", "reflected": "🔄", "observed": "👁️",
                        "confirmed": "✅", "violated": "❌", "amplified": "📢",
                        "retained": "🔒", "archived": "📦"}.get(action, "•")

                lines.append(f"- {time_str} {icon} [{domain}] {action}: **{rule_text}**")
                lines.append(f"  Agent: {agent} | Project: {project}")
                if ctx:
                    lines.append(f"  Context: {ctx}")
                lines.append("")

        return [_text_result("\n".join(lines))]

    # ── Stats ─────────────────────────────────────────────────────────

    def _handle_stats(self, args: dict) -> list:
        domain = args.get("domain")
        include_org = args.get("include_org", True)

        store = self.store
        stats = store.get_domain_stats(domain)
        per_domain = store.get_all_domain_stats()

        if stats["total"] == 0:
            return [_text_result("## Stats\n\nTotal: 0 rules\n\nNothing learned yet.")]

        lines = [
            f"## 📊 Loom Stats\n",
            f"**Project rules:** {stats['total']}",
            f"**Average confidence:** {stats['avg_confidence']:.1f}/10",
            f"**Extraction engine:** {self._extraction_status()}",
            "",
        ]

        if domain:
            lines.insert(1, f"Domain: {domain}")
        elif per_domain:
            lines.append("### By Domain")
            for d, s in sorted(per_domain.items()):
                lines.append(f"  - **{d}**: {s['total']} rule(s) (avg confidence: {s['avg_confidence']:.1f})")

        if stats["by_type"]:
            lines.append("\n### By Type")
            for t, count in sorted(stats["by_type"].items()):
                lines.append(f"  - {t}: {count}")

        # Retention stats
        try:
            health = self.retention.get_health() if hasattr(self.retention, 'get_health') else {}
            if health:
                lines.append(f"\n### Retention")
                lines.append(f"  - Permanent: {health.get('permanent', 0)}")
                lines.append(f"  - Long-term: {health.get('long_term', 0)}")
                lines.append(f"  - Standard: {health.get('standard', 0)}")
                lines.append(f"  - Decaying: {health.get('decaying', 0)}")
        except Exception:
            pass

        # Org stats
        if include_org:
            try:
                org_stats = self.org_store.get_org_stats()
                if org_stats and org_stats.get("total_rules", 0) > 0:
                    lines.append(f"\n### Org-Wide")
                    lines.append(f"  - Total org rules: {org_stats['total_rules']}")
                    lines.append(f"  - Projects: {', '.join(org_stats.get('by_project', {}).keys())}")
            except Exception:
                pass

        # Timeline stats
        try:
            summary = self.timeline.get_summary("weekly")
            if summary:
                lines.append(f"\n### Recent Activity")
                lines.append(f"  - Total entries: {summary.get('total_entries', 0)}")
                lines.append(f"  - Avg confidence: {summary.get('avg_confidence', 0):.1f}")
        except Exception:
            pass

        return [_text_result("\n".join(lines))]

    def _handle_store(self, args: dict) -> list:
        """Backward-compat wrapper."""
        domain = args.get("domain", "coding")
        outcome = args.get("outcome", "rejected")
        feedback = args.get("feedback", "")
        source_url = args.get("source_url", "")

        learn_args = {
            "context": f"PR review (outcome: {outcome})",
            "observation": feedback,
            "lesson": "",
            "domain": domain,
            "confidence": 7 if outcome == "rejected" else 5,
            "source_type": "pr_review",
        }

        results = self._handle_learn(learn_args)
        text = results[0].text
        if source_url:
            text += f"\nSource: {source_url}"
        return [_text_result(text)]

    # ── Glen-level handlers ───────────────────────────────────────────

    def _handle_onboard(self, args: dict) -> list:
        """Glen-style instant onboarding: generate a pack for a new team member's agent."""
        role = args.get("role", "")
        fmt = args.get("format", "markdown")
        custom_notes = args.get("custom_notes", "")
        include_succession = args.get("include_succession", True)

        if not role or role not in _ROLE_DOMAIN_MAP:
            known = list(_ROLE_DOMAIN_MAP.keys())
            return [_text_result(
                f"Unknown role: '{role}'. Known roles: {', '.join(known)}\n\n"
                f"Tip: Use a role like 'backend-engineer', 'frontend-dev', 'support-agent', etc."
            )]

        domains = _ROLE_DOMAIN_MAP[role]
        store = self.store

        # Collect top rules for this role's domains
        all_rules = []
        for domain in domains:
            domain_rules = store.get_rules_by_domain(domain, min_confidence=5)
            all_rules.extend(domain_rules)

        # Sort by confidence
        all_rules.sort(key=lambda r: (r.confidence, r.times_confirmed), reverse=True)

        # Build the onboarding pack
        if fmt == "json":
            pack = {
                "role": role,
                "domains": domains,
                "rules": [r.to_dict() for r in all_rules[:20]],
                "custom_notes": custom_notes,
                "generated_at": _now(),
            }
            return [_text_result(json.dumps(pack, indent=2))]

        # Markdown format
        lines = [
            f"# 🚀 Onboarding Pack: {role.replace('-', ' ').title()}",
            "",
            f"*Welcome to the team! This is what our agents know about how we work.*",
            "",
        ]

        if custom_notes:
            lines.append(f"> {custom_notes}")
            lines.append("")

        # Top conventions grouped by domain
        lines.append("## 📋 Core Conventions")
        lines.append("")

        by_domain: dict[str, list[Rule]] = {}
        for r in all_rules[:20]:
            by_domain.setdefault(r.domain, []).append(r)

        for domain in domains:
            if domain not in by_domain:
                continue
            lines.append(f"### {domain.title()}")
            for r in by_domain[domain]:
                lines.append(f"- **{r.rule_type}** ({r.confidence}/10): {r.rule}")
                if r.example:
                    lines.append(f"  Example: `{r.example}`")
            lines.append("")

        # Key decisions from timeline
        try:
            date_from = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
            decisions = self.timeline.query(limit=10, date_from=date_from)
            if decisions:
                lines.append("## 🧭 Key Recent Decisions")
                lines.append("")
                for d in decisions[:5]:
                    ts = d.timestamp[:10] if d.timestamp else ""
                    lines.append(f"- **{ts}**: {(d.rule_text or '')[:150]}")
                lines.append("")
        except Exception:
            pass

        # Succession knowledge
        if include_succession:
            try:
                sessions = self.succession.list_sessions()
                if sessions:
                    lines.append("## 📋 Captured Team Knowledge")
                    lines.append("")
                    for s in sessions[:3]:
                        lines.append(f"- **{s}** — succession knowledge captured")
                    lines.append("")
                    lines.append("*Use `succession` to view full details.*")
                    lines.append("")
            except Exception:
                pass

        # Coaching amplifications
        try:
            coaching = self.amplifier.get_coaching_for_role(role)
            if coaching:
                lines.append("## 📢 Coaching From Your Team")
                lines.append("")
                for c in coaching[:5]:
                    lines.append(f"- **{c.original_rule or ''}** — by {c.coach or ''}")
                lines.append("")
        except Exception:
            pass

        lines.append("---")
        lines.append(f"*Generated by Loom — the memory layer for AI agents*")

        # Persist the pack
        try:
            self.onboarding.create_pack(
                name=f"{role} onboarding",
                role=role,
                description=f"Auto-generated onboarding for {role}",
                domain_filters=domains,
                custom_notes=custom_notes,
            )
        except Exception:
            pass

        return [_text_result("\n".join(lines))]

    def _handle_succession(self, args: dict) -> list:
        """Glen-style succession capture."""
        member = args.get("member", "")
        role = args.get("role", "")
        action = args.get("action", "start")

        if action == "start":
            session = self.succession.start_session(
                departing_member=member,
                role=role,
                project=str(self.project_root.name),
            )
            # Auto-import rules this person authored/confirmed
            imported = self.succession.import_from_rules(member)
            return [_text_result(
                f"## 📋 Succession Session Started\n\n"
                f"**Member:** {member}\n"
                f"**Role:** {role}\n"
                f"**Project:** {self.project_root.name}\n"
                f"**Auto-imported rules:** {len(imported)} rule(s) linked to {member}\n\n"
                f"Ready to capture knowledge. Use `succession` with `action='capture'` "
                f"to add items. Use `action='finalize'` when done."
            )]

        elif action == "capture":
            title = args.get("title", "")
            detail = args.get("detail", "")
            importance = args.get("importance", 5)
            category = args.get("category", "tribal_knowledge")
            domain = args.get("domain", "general")

            item = self.succession.capture(
                title=title,
                detail=detail,
                importance=importance,
                category=category,
                domain=domain,
            )
            return [_text_result(
                f"## ✅ Captured\n\n"
                f"**Title:** {title}\n"
                f"**Importance:** {importance}/10\n"
                f"**Category:** {category}\n"
                f"**Domain:** {domain}\n"
            )]

        elif action == "finalize":
            doc = self.succession.finalize_session()
            if doc is None:
                return [_text_result("No active succession session to finalize.")]
            rendered = self.succession.render_succession_doc(doc.departing_member, fmt="markdown")

            # Amplify critical items if amplifier is available
            try:
                # Collect critical items as text for succession amplification
                critical_items = [
                    f"{ki.title}\n{ki.detail}"
                    for ki in doc.knowledge_items
                    if ki.importance >= 8
                ]
                if critical_items:
                    succession_text = "\n\n".join(critical_items)
                    self.amplifier.amplify_from_succession(
                        succession_doc=succession_text,
                        coach=member,
                        coach_role=role,
                    )
            except Exception:
                pass

            return [_text_result(rendered)]

        elif action == "list":
            sessions = self.succession.list_sessions()
            if not sessions:
                return [_text_result("No succession sessions found.")]
            lines = ["## 📋 Succession Sessions\n"]
            for s in sessions:
                lines.append(f"- **{s}**")
            return [_text_result("\n".join(lines))]

        return [_text_result(f"Unknown action: {action}. Use 'start', 'capture', 'finalize', or 'list'.")]

    def _handle_amplify(self, args: dict) -> list:
        """Glen-style coaching amplification."""
        rule_id = args.get("rule_id", "")
        coach = args.get("coach", "")
        coach_role = args.get("coach_role", "")
        amplification = args.get("amplification", "")
        target_roles = args.get("target_roles", [])

        # Verify rule exists
        rule = self.store.get_rule(rule_id)
        if not rule:
            return [_text_result(f"Rule not found: {rule_id}")]

        amplified = self.amplifier.amplify(
            rule_id=rule_id,
            coach=coach,
            coach_role=coach_role,
            amplification_text=amplification,
            target_roles=target_roles,
        )

        # Record in timeline
        self.timeline.record(
            action="amplified",
            rule_id=rule.id,
            rule_text=rule.rule,
            agent=coach,
            project=str(self.project_root.name),
            decision_context=f"Amplified by {coach} ({coach_role}) for roles: {', '.join(target_roles)}",
            domain=rule.domain,
            confidence=rule.confidence,
        )

        return [_text_result(
            f"## 📢 Amplified\n\n"
            f"**Rule:** {rule.rule}\n"
            f"**Coach:** {coach} ({coach_role})\n"
            f"**Target roles:** {', '.join(target_roles) if target_roles else 'all'}\n"
            f"**Amplification:**\n{amplification}\n"
        )]

    def _handle_retain(self, args: dict) -> list:
        """Mark a rule for permanent retention — Glen-style infinite memory."""
        rule_id = args.get("rule_id", "")
        reason = args.get("reason", "")

        rule = self.store.get_rule(rule_id)
        if not rule:
            return [_text_result(f"Rule not found: {rule_id}")]

        self.retention.promote_to_permanent(rule_id, reason)

        # Record in timeline
        self.timeline.record(
            action="retained",
            rule_id=rule.id,
            rule_text=rule.rule,
            agent="agent",
            project=str(self.project_root.name),
            decision_context=f"Marked permanent: {reason}",
            domain=rule.domain,
            confidence=rule.confidence,
        )

        return [_text_result(
            f"## 🔒 Retained Permanently\n\n"
            f"**Rule:** {rule.rule}\n"
            f"**ID:** {rule_id}\n"
            f"**Reason:** {reason}\n"
            f"**Status:** This rule will never decay. It is now permanent organizational knowledge.\n"
        )]

    def _handle_set_clearance(self, args: dict) -> list:
        """Per-observation RBAC — Glen-style access control."""
        rule_id = args.get("rule_id", "")
        clearance = args.get("clearance", "internal")
        allowed_roles = args.get("allowed_roles", [])
        allowed_teams = args.get("allowed_teams", [])

        # Validate clearance level with a helpful error
        valid_levels = [level.name.lower() for level in ClearanceLevel]
        clearance_key = clearance.upper()
        if clearance_key not in ClearanceLevel.__members__:
            return [_text_result(
                f"Invalid clearance level: '{clearance}'. "
                f"Valid levels (case-insensitive): {', '.join(valid_levels)}"
            )]

        self.rbac.set_clearance(
            rule_id=rule_id,
            clearance=ClearanceLevel[clearance_key],
            allowed_roles=allowed_roles,
            allowed_teams=allowed_teams,
            allowed_agents=[],
            owner="agent",
        )

        return [_text_result(
            f"## 🔐 Clearance Set\n\n"
            f"**Rule ID:** {rule_id}\n"
            f"**Clearance:** {clearance}\n"
            f"**Allowed roles:** {', '.join(allowed_roles) if allowed_roles else 'all'}\n"
            f"**Allowed teams:** {', '.join(allowed_teams) if allowed_teams else 'all'}\n"
        )]

    def _handle_timeline(self, args: dict) -> list:
        """Query the auditable organization timeline."""
        domain = args.get("domain")
        project = args.get("project")
        agent = args.get("agent")
        days = args.get("days", 30)
        limit = args.get("limit", 50)
        fmt = args.get("format", "markdown")

        date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        entries = self.timeline.query(
            domain=domain,
            project=project,
            agent=agent,
            date_from=date_from,
            limit=limit,
        )

        if not entries:
            return [_text_result("## Timeline\n\nNo entries found. Start learning to build the timeline.")]

        if fmt == "json":
            return [_text_result(json.dumps([e.to_dict() for e in entries], indent=2))]

        # Markdown timeline
        lines = [f"## 📅 Organization Timeline\n"]

        if domain:
            lines.append(f"Domain: {domain} | ")
        if project:
            lines.append(f"Project: {project} | ")
        lines.append(f"Last {days} days\n")

        by_date: dict[str, list] = {}
        for e in entries:
            ts = e.timestamp if e.timestamp else ""
            date_key = ts[:10] or "unknown"
            by_date.setdefault(date_key, []).append(e)

        for date_key in sorted(by_date.keys(), reverse=True):
            lines.append(f"\n### {date_key}")
            for e in by_date[date_key]:
                ts = e.timestamp if e.timestamp else ""
                time_str = ts[11:16] if len(ts) > 11 else ""
                action = e.action or "unknown"
                icon = {"learned": "🧠", "taught": "📖", "reflected": "🔄", "observed": "👁️",
                        "amplified": "📢", "retained": "🔒"}.get(action, "•")
                lines.append(
                    f"- {time_str} {icon} **{(e.rule_text or '')[:120]}**"
                )
                lines.append(f"  Domain: {e.domain or ''} | Agent: {e.agent or ''}")
                if e.decision_context:
                    lines.append(f"  Context: {e.decision_context[:200]}")

        return [_text_result("\n".join(lines))]

    def _handle_federate(self, args: dict) -> list:
        """Ingest rules from another project into the org-wide store."""
        project_path = args.get("project_path", "")
        project_name = args.get("project_name", Path(project_path).name if project_path else "")

        if not project_path:
            return [_text_result("project_path is required.")]

        try:
            count = self.org_store.federate_project(project_path)
            return [_text_result(
                f"## 🔗 Federated\n\n"
                f"**Source:** {project_path}\n"
                f"**Project name:** {project_name or Path(project_path).name}\n"
                f"**Rules ingested:** {count}\n"
                f"**Org store total:** {len(self.org_store.rules)} rule(s)\n"
            )]
        except Exception as e:
            return [_text_result(f"Federation failed: {e}")]

    def _handle_session_init(self, args: dict) -> list:
        """Glen-style session initialization with pre-loaded context."""
        task = args.get("task", "")
        role = args.get("role", "")
        project = args.get("project", str(self.project_root.name))
        max_rules = args.get("max_rules", 15)
        include_onboarding = args.get("include_onboarding", True)

        # Get relevant context
        recall_args = {
            "task": task,
            "role": role,
            "max_rules": max_rules,
            "include_org": True,
        }
        context_result = self._handle_recall_relevant(recall_args)
        context_text = context_result[0].text

        lines = [context_text]

        # Add onboarding context if applicable
        if include_onboarding and role and role in _ROLE_DOMAIN_MAP:
            try:
                pack = self.onboarding.get_pack(role)
                if pack:
                    lines.append("")
                    lines.append("---")
                    lines.append("## 🚀 Onboarding Context")
                    lines.append("")
                    for rule_id in pack.rules[:5]:
                        rule = self.store.get_rule(rule_id)
                        if rule:
                            lines.append(f"- **{rule.rule_type}**: {rule.rule}")
            except Exception:
                pass

        # Add timeline summary
        try:
            summary = self.timeline.get_summary("weekly")
            if summary and summary.get("total_entries", 0) > 0:
                lines.append("")
                lines.append(f"---")
                lines.append(f"*This week: {summary['total_entries']} things learned across the org.*")
        except Exception:
            pass

        lines.append("")
        lines.append("*Session context loaded by Loom — the memory layer for AI agents*")

        # Reset auto-observer for new session
        try:
            self.auto_observer.on_session_start()
        except Exception:
            pass

        return [_text_result("\n".join(lines))]

    # ── Helpers ───────────────────────────────────────────────────────

    def _regenerate_conventions(self, store: RuleStore, domain_filter: str | None = None):
        """Update conventions.md from current store state."""
        rules = store.get_rules_by_domain(domain_filter) if domain_filter else store.get_active_rules(min_confidence=1)

        lines = ["# Loom Conventions\n", "Auto-learned from observations, teaching, and reflection.\n"]
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tool_to_observation(tool_name: str, args: dict) -> str:
    """Convert a tool call into an observation string for auto-capture.

    Each tool type extracts the most relevant information:
    - teach → the rule being taught
    - learn → the observation/lesson
    - amplify → the amplification text
    - etc.
    """
    if tool_name == "teach":
        domain = args.get("domain", "")
        rule = args.get("rule", "")
        rule_type = args.get("rule_type", "")
        example = args.get("example", "")
        base = f"[{domain}] {rule_type}: {rule}"
        if example:
            base += f"\nExample: {example}"
        return base

    if tool_name == "learn":
        ctx = args.get("context", "")
        obs = args.get("observation", "")
        lesson = args.get("lesson", "")
        parts = [p for p in [ctx, obs, lesson] if p]
        return "\n".join(parts)

    if tool_name == "reflect":
        ctx = args.get("context", "")
        patterns = args.get("patterns", [])
        return ctx + "\n" + "\n".join(f"- {p}" for p in patterns)

    if tool_name == "amplify":
        rule_id = args.get("rule_id", "")
        coach = args.get("coach", "")
        amplification = args.get("amplification", "")
        return f"Coach {coach} on rule {rule_id}: {amplification}"

    if tool_name == "retain":
        rule_id = args.get("rule_id", "")
        reason = args.get("reason", "")
        return f"Rule {rule_id} retained: {reason}"

    if tool_name == "set_clearance":
        rule_id = args.get("rule_id", "")
        clearance = args.get("clearance", "")
        return f"Clearance set for {rule_id}: {clearance}"

    if tool_name == "succession":
        action = args.get("action", "")
        member = args.get("member", "")
        title = args.get("title", "")
        detail = args.get("detail", "")
        if action == "capture":
            return f"Succession [{member}]: {title}\n{detail}"
        return f"Succession [{member}]: {action}"

    if tool_name == "federate":
        project = args.get("project_path", "")
        name = args.get("project_name", "")
        return f"Federated from {name or project}"

    if tool_name == "store_outcome":
        outcome = args.get("outcome", "")
        feedback = args.get("feedback", "")
        return f"PR {outcome}: {feedback}"

    # Generic fallback: concatenate string values
    return " ".join(
        str(v)[:200] for v in args.values()
        if isinstance(v, str) and v
    )


def _write_default_domain_configs(domains_dir: Path):
    """Create default domain YAML configs if they don't already exist."""
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
                "type_safety": ["type hint", "type annotation", "typing", "mypy", "return type", "type safety", "type-check", "generic"],
                "error_handling": ["error handling", "try-except", "try/except", "exception", "error", "result type", "unwrap", "abort", "fallback"],
                "naming": ["camelcase", "snake_case", "pascalcase", "naming convention", "rename", "variable name", "function name"],
                "imports": ["import", "from import", "circular import", "dependency", "module", "package"],
                "function_design": ["pure function", "side effect", "parameter", "return", "function too long", "split function", "single responsibility"],
                "control_flow": ["if-else", "loop", "recursion", "early return", "guard clause", "switch", "match case"],
                "data_structures": ["list", "dict", "set", "tuple", "dataclass", "class", "inheritance", "composition", "interface"],
                "performance": ["performance", "slow", "optimize", "cache", "lazy", "eager", "memory", "allocation", "bottleneck"],
            },
        },
        "style": {
            "name": "style",
            "description": "Coding style, formatting, and aesthetic conventions",
            "keywords": ["style", "format", "indent", "spacing", "line length", "whitespace", "quote", "trailing", "brace", "look", "readability", "clean"],
            "rule_types": ["formatting", "naming_convention", "comments", "whitespace", "line_length", "quotes", "trailing_commas", "brace_style"],
            "patterns": {
                "formatting": ["tab", "space", "indent", "formatting", "prettier", "black", "formatter", "auto-format"],
                "naming_convention": ["camelcase", "snake_case", "pascalcase", "naming", "rename", "variable name", "function name", "file name"],
                "comments": ["comment", "docstring", "inline comment", "TODO", "FIXME", "explain", "document"],
                "whitespace": ["blank line", "whitespace", "trailing space", "newline", "EOF", "end of file"],
                "line_length": ["line too long", "line length", "wrap", "break line", "80", "100", "120"],
                "quotes": ["single quote", "double quote", "quote", "string", "f-string", "template string"],
                "trailing_commas": ["trailing comma", "comma", "last item"],
                "brace_style": ["brace", "bracket", "indent style", "curly brace", "same line", "new line"],
            },
        },
        "architecture": {
            "name": "architecture",
            "description": "Design patterns, module structure, and system organization",
            "keywords": ["architecture", "design pattern", "module", "service", "layer", "separation", "dependency", "interface", "abstraction", "component"],
            "rule_types": ["separation_of_concerns", "module_design", "service_layer", "dependency", "design_pattern", "abstraction", "interface", "composition"],
            "patterns": {
                "separation_of_concerns": ["separation of concerns", "single responsibility", "concern", "layer", "tier"],
                "module_design": ["module", "package", "namespace", "file structure", "folder", "directory"],
                "service_layer": ["service", "service layer", "API", "controller", "handler", "route"],
                "dependency": ["dependency", "coupling", "decouple", "inversion", "inject", "DI", "import"],
                "design_pattern": ["design pattern", "factory", "singleton", "observer", "strategy", "builder", "adapter", "facade", "repository"],
                "abstraction": ["abstraction", "abstract", "interface", "protocol", "base class", "mixin"],
                "interface": ["interface", "API", "contract", "public", "private", "internal", "export"],
                "composition": ["composition", "inheritance", "mixin", "trait", "delegate", "wrapper"],
            },
        },
        "process": {
            "name": "process",
            "description": "Workflow patterns, git practices, review norms, and CI/CD",
            "keywords": ["git", "commit", "branch", "merge", "PR", "pull request", "review", "CI", "CD", "deploy", "release", "workflow"],
            "rule_types": ["git_workflow", "branching", "commit_message", "pr_process", "review_norms", "release", "deploy", "ci_cd"],
            "patterns": {
                "git_workflow": ["git", "workflow", "rebase", "squash", "merge commit", "fast-forward"],
                "branching": ["branch", "branch name", "feature branch", "main", "master", "develop", "hotfix"],
                "commit_message": ["commit message", "commit", "conventional commit", "semantic commit", "changelog"],
                "pr_process": ["PR", "pull request", "draft", "ready for review", "approve", "request changes"],
                "review_norms": ["review", "code review", "reviewer", "LGTM", "approve", "feedback"],
                "release": ["release", "version", "semver", "tag", "changelog", "release note"],
                "deploy": ["deploy", "deployment", "rollback", "staging", "production", "canary", "blue-green"],
                "ci_cd": ["CI", "CD", "pipeline", "build", "test", "lint", "check", "GitHub Actions", "Jenkins"],
            },
        },
        "testing": {
            "name": "testing",
            "description": "Testing conventions, frameworks, and quality practices",
            "keywords": ["test", "testing", "pytest", "coverage", "mock", "fixture", "assert", "TDD"],
            "rule_types": ["unit_test", "integration_test", "e2e_test", "coverage", "test_location", "mocking", "fixtures", "assertions"],
            "patterns": {
                "unit_test": ["unit test", "test", "testing", "pytest", "unittest", "test case"],
                "integration_test": ["integration test", "integration", "e2e", "end-to-end", "system test"],
                "e2e_test": ["e2e", "end-to-end", "browser test", "playwright", "selenium", "cypress"],
                "coverage": ["coverage", "code coverage", "line coverage", "branch coverage"],
                "test_location": ["test directory", "test file", "tests/", "conftest", "test fixture"],
                "mocking": ["mock", "stub", "fake", "spy", "patch", "monkeypatch"],
                "fixtures": ["fixture", "setup", "teardown", "before each", "after each", "conftest"],
                "assertions": ["assert", "expect", "should", "must", "verify", "check"],
            },
        },
        "security": {
            "name": "security",
            "description": "Security patterns, vulnerability prevention, and secure coding",
            "keywords": ["security", "vulnerability", "injection", "XSS", "CSRF", "auth", "authentication", "authorization", "secret", "encrypt", "hash"],
            "rule_types": ["auth", "authorization", "input_validation", "sanitization", "secrets", "cryptography", "dependency_security", "threat_model"],
            "patterns": {
                "auth": ["auth", "authentication", "login", "logout", "session", "token", "JWT", "OAuth"],
                "authorization": ["authorization", "permission", "access control", "RBAC", "role", "scope", "capability"],
                "input_validation": ["input validation", "validate", "sanitize", "escape", "filter input", "user input"],
                "sanitization": ["sanitize", "sanitization", "escape", "encode", "XSS", "cross-site scripting"],
                "secrets": ["secret", "password", "API key", "token", "credential", "env", "environment variable"],
                "cryptography": ["encrypt", "decrypt", "hash", "bcrypt", "sha", "tls", "ssl", "https"],
                "dependency_security": ["dependency", "vulnerability", "CVE", "supply chain", "audit", "update", "patch"],
                "threat_model": ["threat", "attack", "exploit", "risk", "mitigation", "trust boundary"],
            },
        },
        "documentation": {
            "name": "documentation",
            "description": "Documentation patterns, READMEs, API docs, and knowledge sharing",
            "keywords": ["document", "docs", "readme", "comment", "docstring", "explain", "tutorial", "guide"],
            "rule_types": ["docstrings", "readme", "api_docs", "inline_comments", "changelog", "architecture_docs", "examples", "tutorials"],
            "patterns": {
                "docstrings": ["docstring", "doc string", "documentation string", "pydoc", "jsdoc"],
                "readme": ["readme", "README", "getting started", "setup"],
                "api_docs": ["API doc", "endpoint documentation", "swagger", "openapi", "route documentation"],
                "inline_comments": ["inline comment", "comment", "explain", "why"],
                "changelog": ["changelog", "change log", "version history"],
                "architecture_docs": ["architecture document", "ADR", "design doc", "RFC", "decision record"],
                "examples": ["example", "code sample", "usage example", "demo"],
                "tutorials": ["tutorial", "guide", "walkthrough", "how-to"],
            },
        },
        "general": {
            "name": "general",
            "description": "Catch-all domain for preferences, conventions, best practices, and habits",
            "keywords": ["always", "never", "should", "must", "prefer", "convention", "best practice", "guideline", "rule", "standard", "habit", "pattern"],
            "rule_types": ["preference", "convention", "best_practice", "rule_of_thumb", "guideline", "standard", "habit", "pattern"],
            "patterns": {
                "preference": ["prefer", "preference", "I like", "we like"],
                "convention": ["convention", "conventional", "by convention"],
                "best_practice": ["best practice", "recommended", "industry standard"],
                "rule_of_thumb": ["rule of thumb", "generally", "in general", "usually", "typically"],
                "guideline": ["guideline", "guide", "should", "ought to"],
                "standard": ["standard", "standardize", "consistent", "uniform"],
                "habit": ["always", "never", "every time", "habit"],
                "pattern": ["pattern", "template", "boilerplate", "scaffold"],
            },
        },
    }

    for name, config in _DOMAINS.items():
        yml_file = domains_dir / f"{name}.yml"
        if yml_file.exists():
            continue
        yml_file.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))


def create_loom_server(project_root: Path) -> LoomMCPServer:
    """Create a Loom MCP server pointed at a project root."""
    return LoomMCPServer(Path(project_root))


def main():
    """Start the Loom MCP server via stdio transport."""
    from mcp.server.fastmcp import FastMCP

    project_root = Path(os.environ.get("LOOM_PROJECT_ROOT", os.getcwd()))
    loom = create_loom_server(project_root)

    mcp = FastMCP("loom")

    # ── Core learning tools ──────────────────────────────────────

    @mcp.tool(name="learn", description="Learn from observation — report what happened and what was learned")
    async def learn(
        context: str,
        observation: str,
        lesson: str = "",
        domain: str = "general",
        confidence: int = 5,
        source_type: str = "observation",
    ) -> str:
        result = loom._handle_learn({
            "context": context, "observation": observation, "lesson": lesson,
            "domain": domain, "confidence": confidence, "source_type": source_type,
        })
        return result[0].text

    @mcp.tool(name="teach", description="Teach a rule directly — inject a convention without extraction")
    async def teach(
        domain: str,
        rule: str,
        rule_type: str,
        example: str = "",
        confidence: int = 7,
        retention: str = "standard",
    ) -> str:
        result = loom._handle_teach({
            "domain": domain, "rule": rule, "rule_type": rule_type,
            "example": example, "confidence": confidence, "retention": retention,
        })
        return result[0].text

    @mcp.tool(name="reflect", description="Reflect on completed work — extract patterns from multiple observations")
    async def reflect(domain: str, patterns: list[str], context: str = "") -> str:
        result = loom._handle_reflect({"domain": domain, "patterns": patterns, "context": context})
        return result[0].text

    # ── Recall tools ─────────────────────────────────────────────

    @mcp.tool(name="recall_memory", description="Search learned conventions and rules")
    async def recall_memory(
        query: str,
        domain: str | None = None,
        min_confidence: int = 1,
        limit: int | None = None,
    ) -> str:
        result = loom._handle_recall({"query": query, "domain": domain, "min_confidence": min_confidence, "limit": limit})
        return result[0].text

    @mcp.tool(name="recall_relevant", description="Auto-recall everything relevant to a task — Glen-style pre-loaded context")
    async def recall_relevant(
        task: str,
        role: str = "",
        max_rules: int = 15,
        include_org: bool = True,
    ) -> str:
        result = loom._handle_recall_relevant({"task": task, "role": role, "max_rules": max_rules, "include_org": include_org})
        return result[0].text

    @mcp.tool(name="observe", description="Passively observe work — silent background capture like Glen")
    async def observe(
        context: str,
        content: str,
        domain: str = "",
        sensitivity: str = "normal",
    ) -> str:
        result = loom._handle_observe({"context": context, "content": content, "domain": domain, "sensitivity": sensitivity})
        return result[0].text

    # ── Export / Stats ───────────────────────────────────────────

    @mcp.tool(name="export", description="Export learned rules in structured formats")
    async def export_rules(
        domain: str = "",
        format: str = "markdown",
        min_confidence: int = 1,
        rule_type: str = "",
        include_org: bool = True,
    ) -> str:
        result = loom._handle_export({
            "domain": domain or None, "format": format,
            "min_confidence": min_confidence, "rule_type": rule_type or None,
            "include_org": include_org,
        })
        return result[0].text

    @mcp.tool(name="export_timeline", description="Export the full organization timeline — Glen-style auditable history")
    async def export_timeline(
        domain: str = "",
        project: str = "",
        format: str = "markdown",
        days: int = 30,
        limit: int = 50,
    ) -> str:
        result = loom._handle_export_timeline({
            "domain": domain or None, "project": project or None,
            "format": format, "days": days, "limit": limit,
        })
        return result[0].text

    @mcp.tool(name="get_stats", description="Get statistics about learned rules including org-wide and retention data")
    async def get_stats(domain: str | None = None, include_org: bool = True) -> str:
        result = loom._handle_stats({"domain": domain, "include_org": include_org})
        return result[0].text

    @mcp.tool(name="store_outcome", description="Store an outcome and learn from feedback (delegates to learn)")
    async def store_outcome(domain: str, outcome: str, feedback: str, source_url: str = "") -> str:
        result = loom._handle_store({"domain": domain, "outcome": outcome, "feedback": feedback, "source_url": source_url})
        return result[0].text

    # ── Glen-level tools ─────────────────────────────────────────

    @mcp.tool(name="onboard", description="Generate an onboarding pack for a new team member — Glen-style instant ramp-up")
    async def onboard(
        role: str,
        format: str = "markdown",
        custom_notes: str = "",
        include_succession: bool = True,
    ) -> str:
        result = loom._handle_onboard({
            "role": role, "format": format,
            "custom_notes": custom_notes, "include_succession": include_succession,
        })
        return result[0].text

    @mcp.tool(name="succession", description="Capture departing member's knowledge — Glen-style knowledge retention")
    async def succession(
        member: str,
        role: str,
        action: str = "start",
        title: str = "",
        detail: str = "",
        importance: int = 5,
        category: str = "tribal_knowledge",
        domain: str = "general",
    ) -> str:
        result = loom._handle_succession({
            "member": member, "role": role, "action": action,
            "title": title, "detail": detail, "importance": importance,
            "category": category, "domain": domain,
        })
        return result[0].text

    @mcp.tool(name="amplify", description="Amplify a coach's guidance across the team — Glen-style coaching amplification")
    async def amplify(
        rule_id: str,
        coach: str,
        coach_role: str,
        amplification: str,
        target_roles: list[str] | None = None,
    ) -> str:
        result = loom._handle_amplify({
            "rule_id": rule_id, "coach": coach, "coach_role": coach_role,
            "amplification": amplification, "target_roles": target_roles or [],
        })
        return result[0].text

    @mcp.tool(name="retain", description="Mark a rule for permanent retention — Glen-style infinite memory")
    async def retain(rule_id: str, reason: str) -> str:
        result = loom._handle_retain({"rule_id": rule_id, "reason": reason})
        return result[0].text

    @mcp.tool(name="set_clearance", description="Set per-observation access control — Glen-style RBAC")
    async def set_clearance(
        rule_id: str,
        clearance: str,
        allowed_roles: list[str] | None = None,
        allowed_teams: list[str] | None = None,
    ) -> str:
        result = loom._handle_set_clearance({
            "rule_id": rule_id, "clearance": clearance,
            "allowed_roles": allowed_roles or [], "allowed_teams": allowed_teams or [],
        })
        return result[0].text

    @mcp.tool(name="timeline", description="Query the auditable organization timeline")
    async def timeline(
        domain: str = "",
        project: str = "",
        agent: str = "",
        days: int = 30,
        limit: int = 50,
        format: str = "markdown",
    ) -> str:
        result = loom._handle_timeline({
            "domain": domain or None, "project": project or None,
            "agent": agent or None, "days": days, "limit": limit, "format": format,
        })
        return result[0].text

    @mcp.tool(name="federate", description="Ingest rules from another project into the org-wide store")
    async def federate(project_path: str, project_name: str = "") -> str:
        result = loom._handle_federate({"project_path": project_path, "project_name": project_name})
        return result[0].text

    @mcp.tool(name="session_init", description="Initialize a session with pre-loaded relevant context — Glen-style auto-context")
    async def session_init(
        task: str,
        role: str = "",
        project: str = "",
        max_rules: int = 15,
        include_onboarding: bool = True,
    ) -> str:
        result = loom._handle_session_init({
            "task": task, "role": role, "project": project,
            "max_rules": max_rules, "include_onboarding": include_onboarding,
        })
        return result[0].text

    # ── Register shutdown hooks ──────────────────────────────────
    atexit.register(loom._shutdown)
    signal.signal(signal.SIGTERM, lambda *_: loom._shutdown())
    signal.signal(signal.SIGINT, lambda *_: loom._shutdown())

    mcp.run(transport="stdio")

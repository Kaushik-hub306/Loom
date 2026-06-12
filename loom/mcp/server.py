"""Loom MCP server — memory layer for AI agents: learn, teach, reflect, recall, export, stats."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

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
        "feedback": {"type": "string", "description": "Feedback, review comment, or observation text"},
        "source_url": {"type": "string", "description": "Optional source URL (PR, issue, doc)"},
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
            # Create .gitignore for sensitive loom files
            (self.loom_dir / ".gitignore").write_text(
                "tokens.json\nintegrity.json\naudit.jsonl\nprivate.jsonl\n"
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
                name="store_outcome",
                description="Store an outcome and learn from feedback (delegates to learn)",
                inputSchema=STORE_OUTCOME_SCHEMA,
            ),
        ]

    async def call_tool(self, name: str, arguments: dict) -> list:
        self._bootstrap()
        store = self.store

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
        elif name == "store_outcome":
            return self._handle_store(store, arguments)
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

    def _handle_learn(self, store: RuleStore, args: dict) -> list:
        """Learn from an observation — the primary general-purpose learning entry point.

        If ``lesson`` is provided, the rule is stored directly without extraction.
        Otherwise, the extractor runs on ``observation`` against the given domain.
        """
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

        if lesson:
            # Direct rule injection — no extraction needed
            store.add_rule(
                domain=domain,
                rule_type="explicit_lesson",
                rule=lesson.strip(),
                example=observation[:200] if observation else "",
                confidence=min(10, confidence + 2),  # explicit lessons get a boost
                sources=[context],
                source_type=source_type,
            )
            created = 1
        elif observation:
            # Extract rules from the observation
            extracted = extractor.extract_rules(observation, domain)
            for rule_data in extracted:
                store.add_rule(
                    domain=domain,
                    rule_type=rule_data["rule_type"],
                    rule=rule_data["rule"],
                    example=rule_data.get("example", ""),
                    confidence=rule_data.get("confidence", confidence),
                    sources=[context],
                    source_type=source_type,
                )
                created += 1

        self._regenerate_conventions(store, domain)

        return [_text_result(
            f"## Learned\n\n"
            f"Domain: {domain}\n"
            f"Context: {context}\n"
            f"Rules created: {created}\n"
        )]

    def _handle_teach(self, store: RuleStore, args: dict) -> list:
        """Teach a rule directly — inject a convention without any extraction."""
        domain = args["domain"]
        rule_text = args["rule"]
        rule_type = args["rule_type"]
        example = args.get("example", "")
        confidence = args.get("confidence", 7)

        store.add_rule(
            domain=domain,
            rule_type=rule_type,
            rule=rule_text.strip(),
            example=example,
            confidence=confidence,
            sources=[],
            source_type="explicit_teach",
        )

        self._regenerate_conventions(store, domain)

        return [_text_result(
            f"## Taught\n\n"
            f"Domain: {domain}\n"
            f"Rule type: {rule_type}\n"
            f"Rule: {rule_text.strip()}\n"
            f"Confidence: {confidence}/10\n"
        )]

    def _handle_reflect(self, store: RuleStore, args: dict) -> list:
        """Reflect on completed work — extract rules from multiple observations."""
        domain = args["domain"]
        context = args.get("context", "")
        patterns = args.get("patterns", [])

        extractor = DomainExtractor(self.loom_dir / "domains")
        created = 0

        for pattern in patterns:
            extracted = extractor.extract_rules(pattern, domain)
            for rule_data in extracted:
                store.add_rule(
                    domain=domain,
                    rule_type=rule_data["rule_type"],
                    rule=rule_data["rule"],
                    example=rule_data.get("example", ""),
                    confidence=rule_data.get("confidence", 7),  # reflection gets higher base confidence
                    sources=[context],
                    source_type="reflection",
                )
                created += 1

        self._regenerate_conventions(store, domain)

        return [_text_result(
            f"## Reflected\n\n"
            f"Domain: {domain}\n"
            f"Patterns considered: {len(patterns)}\n"
            f"Rules created: {created}\n"
        )]

    def _handle_export(self, store: RuleStore, args: dict) -> list:
        """Export learned rules in a structured format."""
        domain = args.get("domain")
        fmt = args.get("format", "markdown")
        min_conf = args.get("min_confidence", 1)
        rule_type = args.get("rule_type")

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

    def _handle_store(self, store: RuleStore, args: dict) -> list:
        """Backward-compat wrapper — delegates to _handle_learn."""
        domain = args.get("domain", "coding")
        outcome = args.get("outcome", "rejected")
        feedback = args.get("feedback", "")
        source_url = args.get("source_url", "")

        # Map old outcome schema to the new learn interface
        learn_args = {
            "context": f"PR review (outcome: {outcome})",
            "observation": feedback,
            "lesson": "",
            "domain": domain,
            "confidence": 7 if outcome == "rejected" else 5,
            "source_type": "pr_review",
        }

        if source_url:
            results = self._handle_learn(store, learn_args)
            text = results[0].text
            text += f"\nSource: {source_url}"
            return [_text_result(text)]

        return self._handle_learn(store, learn_args)

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


def _write_default_domain_configs(domains_dir: Path):
    """Create default domain YAML configs if they don't already exist.

    Each domain defines its own keywords (for auto-detection), rule_types
    (for stats grouping), patterns (for keyword-based extraction), and an
    optional ``use_llm`` flag (for LLM-powered extraction).
    """

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
    ) -> str:
        result = loom._handle_recall(
            loom.store,
            {"query": query, "domain": domain, "min_confidence": min_confidence, "limit": limit},
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

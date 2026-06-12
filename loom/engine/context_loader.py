"""ContextLoader — pre-loads relevant context for agent sessions.

Loom's answer to "agents automatically get relevant context on every turn."
Instead of agents needing to call `recall_memory` explicitly, this
pre-loads all relevant context at session start and on demand.

Goes beyond keyword search: uses domain detection, task type inference,
and role awareness to build a curated context block for the system prompt.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .rule_store import Rule, RuleStore

if TYPE_CHECKING:
    from pathlib import Path


# ── Smart domain mapping ────────────────────────────────────────────────────

# Each entry maps a compiled regex to a list of domain names.
# Patterns are matched case-insensitively against the full task description.
# Order matters — first-match-wins per *category*, but we aggregate across all
# patterns that match (a single task can touch many domains).
_SMART_DOMAIN_MAP: list[tuple[re.Pattern, list[str]]] = [
    # API / endpoint patterns
    (
        re.compile(r"\b(api|endpoint|route|rest|graphql|openapi|swagger|grpc)\b", re.I),
        ["coding", "architecture", "testing", "security"],
    ),
    # Refactoring patterns
    (
        re.compile(r"\b(refactor|clean\s*up|restructure|reorganize|consolidate|simplify)\b", re.I),
        ["coding", "style", "architecture"],
    ),
    # Bug fix patterns
    (
        re.compile(r"\b(fix|bug|issue|crash|broken|defect|hotfix|patch)\b", re.I),
        ["coding", "testing"],
    ),
    # Deploy / release patterns
    (
        re.compile(r"\b(deploy|release|ship|publish|rollout|launch|push)\b", re.I),
        ["process", "security"],
    ),
    # Testing patterns
    (
        re.compile(r"\b(test|coverage|qa|quality assurance|snapshot|mock|fixture|assert)\b", re.I),
        ["testing"],
    ),
    # Documentation patterns
    (
        re.compile(r"\b(document|readme|docs|docstring|comment|changelog)\b", re.I),
        ["documentation"],
    ),
    # Code review patterns
    (
        re.compile(r"\b(review|pr|code\s*review|pull\s*request|merge\s*request)\b", re.I),
        ["process", "style", "coding"],
    ),
    # Auth / security patterns
    (
        re.compile(r"\b(auth|login|logout|permission|rbac|oauth|jwt|token|session|cors|csp)\b", re.I),
        ["security", "coding"],
    ),
    # Performance patterns
    (
        re.compile(r"\b(perf|performance|slow|optimize|latency|benchmark|throughput|cache)\b", re.I),
        ["coding", "architecture"],
    ),
    # Database patterns
    (
        re.compile(r"\b(database|db|migration|schema|sql|query|orm|postgres|mysql)\b", re.I),
        ["coding", "architecture"],
    ),
    # Error handling patterns
    (
        re.compile(r"\b(error|exception|crash|logging|monitor|alert|trace|sentry)\b", re.I),
        ["coding"],
    ),
    # Dependency patterns
    (
        re.compile(r"\b(dependency|package|library|upgrade|bump|version|npm|pip|cargo)\b", re.I),
        ["coding", "security"],
    ),
    # Configuration patterns
    (
        re.compile(r"\b(config|environment|env\s*var|secret|setting|feature\s*flag)\b", re.I),
        ["coding", "security"],
    ),
    # CI / pipeline patterns
    (
        re.compile(r"\b(ci|cd|pipeline|jenkins|github\s*actions|gitlab\s*ci|workflow|action)\b", re.I),
        ["process"],
    ),
    # Style / formatting patterns
    (
        re.compile(r"\b(style|format|lint|prettier|eslint|flake8|black|isort|ruff)\b", re.I),
        ["style", "coding"],
    ),
    # Infrastructure patterns
    (
        re.compile(r"\b(infra|terraform|docker|kubernetes|k8s|helm|cloud|aws|gcp|azure)\b", re.I),
        ["architecture", "security", "process"],
    ),
    # Accessibility patterns
    (
        re.compile(r"\b(a11y|accessibility|screen\s*reader|aria|wcag)\b", re.I),
        ["coding", "testing"],
    ),
    # Localization patterns
    (
        re.compile(r"\b(i18n|localization|locale|translation|translate|language)\b", re.I),
        ["coding", "documentation"],
    ),
    # Data / analytics patterns
    (
        re.compile(r"\b(analytics|telemetry|metric|datalake|pipeline|etl|report)\b", re.I),
        ["coding", "architecture"],
    ),
    # CLI patterns
    (
        re.compile(r"\b(cli|command\s*line|argparse|click|console|terminal)\b", re.I),
        ["coding", "documentation"],
    ),
]

# ── Role-to-domain biasing ──────────────────────────────────────────────────

# Certain roles naturally gravitate toward certain domains.
# This mapping biases domain selection when a role is specified.
_ROLE_DOMAIN_BIAS: dict[str, list[str]] = {
    "backend": ["coding", "architecture", "testing", "security"],
    "frontend": ["coding", "style", "testing"],
    "fullstack": ["coding", "architecture", "style", "testing", "security"],
    "devops": ["architecture", "security", "process"],
    "sre": ["architecture", "process", "coding"],
    "security": ["security", "coding", "architecture"],
    "qa": ["testing", "process", "documentation"],
    "tech_writer": ["documentation", "style", "process"],
    "data": ["coding", "architecture"],
    "ml": ["coding", "testing", "documentation"],
    "mobile": ["coding", "style", "testing"],
    "architect": ["architecture", "coding", "security", "process"],
    "tech_lead": ["architecture", "coding", "process", "security", "style"],
    "junior": ["coding", "style", "testing", "process"],
    "onboarding": ["process", "coding", "architecture", "style", "documentation"],
}


# ── ContextBlock ────────────────────────────────────────────────────────────


@dataclass
class ContextBlock:
    """Pre-loaded context for injection into an agent's system prompt."""

    rules: list[Rule] = field(default_factory=list)
    domains_covered: list[str] = field(default_factory=list)
    summary: str = ""
    top_reminders: list[Rule] = field(default_factory=list)
    injected_at: str = ""

    def to_dict(self) -> dict:
        return {
            "rules": [r.to_dict() for r in self.rules],
            "domains_covered": list(self.domains_covered),
            "summary": self.summary,
            "top_reminders": [r.to_dict() for r in self.top_reminders],
            "injected_at": self.injected_at,
        }


class ContextLoader:
    """Pre-loads relevant context for agents based on task, role, and domain.

    Works *with* the RuleStore — it doesn't duplicate storage, it supplies
    the intelligence layer that decides *which* rules matter for a given task.

    Usage::

        store = RuleStore(Path("rules.json"))
        loader = ContextLoader(store)
        block = loader.load_context(
            task_description="Build a REST API endpoint for user login",
            role="backend",
        )
        # Inject block into agent system prompt
    """

    # Top reminders are the N highest-confidence rules across all matched domains.
    _TOP_COUNT = 3

    def __init__(
        self,
        store: RuleStore,
        org_store: "RuleStore | None" = None,
    ):
        self.store = store
        self.org_store = org_store  # optional org-wide rules for blending

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── public API ──────────────────────────────────────────────────────

    def load_context(
        self,
        task_description: str,
        role: str = "",
        domain: str | None = None,
        max_rules: int = 20,
    ) -> ContextBlock:
        """Build a context block for injection into the agent system prompt.

        Parameters
        ----------
        task_description:
            What the agent is being asked to do.
        role:
            The agent's role (e.g. "backend", "frontend", "qa").
        domain:
            Explicit domain override.  When ``None``, domains are detected
            automatically from *task_description* and *role*.
        max_rules:
            Maximum number of rules to include across all domains.

        Returns
        -------
        ContextBlock
            A formatted block with rules, summary, and top reminders.
        """
        domains = self._resolve_domains(task_description, role, domain)
        all_rules = self._collect_rules(domains, task_description, max_rules)

        # Blend in org-wide rules at lower priority when available.
        if self.org_store:
            org_rules = self._collect_org_rules(domains, task_description)
            # Deduplicate by rule text similarity — org rules only add if novel.
            existing_texts = {r.rule.lower().strip() for r in all_rules}
            for or_ in org_rules:
                if or_.rule.lower().strip() not in existing_texts:
                    all_rules.append(or_)
                    existing_texts.add(or_.rule.lower().strip())
            all_rules.sort(
                key=lambda r: (r.confidence, r.times_confirmed), reverse=True
            )
            all_rules = all_rules[:max_rules]

        top_reminders = self._pick_top_reminders(all_rules)
        summary = self._build_summary(all_rules, domains)
        covered = list(dict.fromkeys(r.domain for r in all_rules))  # ordered, unique

        return ContextBlock(
            rules=all_rules,
            domains_covered=covered,
            summary=summary,
            top_reminders=top_reminders,
            injected_at=self._now(),
        )

    def smart_search(
        self,
        task_description: str,
        role: str = "",
        limit: int = 10,
    ) -> list[Rule]:
        """Intelligently search across domains based on task type.

        Unlike :meth:`load_context`, this returns a flat list of rules
        (not a full ``ContextBlock``) and is lighter-weight — useful for
        mid-session lookups when full context injection isn't needed.
        """
        domains = self._resolve_domains(task_description, role, domain=None)
        results: list[Rule] = []

        for d in domains:
            domain_rules = self.store.get_rules_by_domain(d, min_confidence=1)
            scored = []
            for rule in domain_rules:
                score = self._relevance_score(rule, task_description)
                if score > 0:
                    scored.append((score, rule))
            scored.sort(key=lambda x: x[0], reverse=True)
            results.extend(r for _, r in scored[:3])

        results.sort(key=lambda r: (r.confidence, r.times_confirmed), reverse=True)
        return results[:limit]

    def get_onboarding_context(
        self,
        role: str,
        team: str = "",
    ) -> ContextBlock:
        """Return a distilled, curated set of rules for a new team member.

        Onboarding context is built differently from a task context:
        - It casts a wider net across all conventional domains.
        - It favours high-confidence, well-worn rules over niche ones.
        - It includes process and style rules that wouldn't normally surface
          for a specific task.
        """
        bias_domains = _ROLE_DOMAIN_BIAS.get(role.lower(), list(_ROLE_DOMAIN_BIAS["junior"]))
        # Always include process and documentation for onboarding.
        for extra in ("process", "documentation"):
            if extra not in bias_domains:
                bias_domains.append(extra)

        all_rules: list[Rule] = []
        for d in bias_domains:
            domain_rules = self.store.get_rules_by_domain(d, min_confidence=3)
            all_rules.extend(domain_rules)

        # Blend org-store rules.
        if self.org_store:
            for d in bias_domains:
                domain_rules = self.org_store.get_rules_by_domain(d, min_confidence=3)
                existing_ids = {r.id for r in all_rules}
                for or_ in domain_rules:
                    if or_.id not in existing_ids:
                        all_rules.append(or_)

        all_rules.sort(key=lambda r: (r.confidence, r.times_confirmed), reverse=True)
        all_rules = all_rules[:25]

        top_reminders = self._pick_top_reminders(all_rules)
        covered = list(dict.fromkeys(r.domain for r in all_rules))

        role_label = f"{role} on {team}" if team else role
        summary = (
            f"Onboarding context for {role_label}. "
            f"Covers {len(covered)} domains with {len(all_rules)} rules. "
            f"Start with the Top Reminders below."
        )

        return ContextBlock(
            rules=all_rules,
            domains_covered=covered,
            summary=summary,
            top_reminders=top_reminders,
            injected_at=self._now(),
        )

    def get_project_overview(self) -> dict:
        """Summarize all domains and their top rules for session init.

        Returns a structured dict (not a ``ContextBlock``) — meant for
        initial session awareness rather than full prompt injection.
        """
        stats = self.store.get_all_domain_stats()
        overview: dict[str, list[dict]] = {}

        for domain, domain_stats in sorted(stats.items(), key=lambda x: -x[1]["total"]):
            rules = self.store.get_rules_by_domain(domain, min_confidence=1)
            rules.sort(key=lambda r: (r.confidence, r.times_confirmed), reverse=True)
            overview[domain] = []
            for r in rules[:3]:
                overview[domain].append({
                    "id": r.id,
                    "rule": r.rule,
                    "rule_type": r.rule_type,
                    "confidence": r.confidence,
                })

        return {
            "domain_count": len(stats),
            "total_rules": sum(s["total"] for s in stats.values()),
            "domains": overview,
            "overall_avg_confidence": round(
                sum(s["avg_confidence"] for s in stats.values())
                / max(len(stats), 1),
                1,
            ),
        }

    def detect_task_domains(self, task_description: str) -> list[str]:
        """Figure out which domains are relevant without explicit user input.

        Pure domain detection — does not load rules, does not require a role.
        Useful for UIs that want to show domain suggestions.
        """
        return self._match_domains(task_description)

    # ── formatting ──────────────────────────────────────────────────────

    def format_context_block(self, block: ContextBlock) -> str:
        """Render a ``ContextBlock`` as a markdown string for injection.

        The output format matches the Loom conventions.md style and is
        intended to be placed directly into an agent's system prompt.
        """
        lines: list[str] = []

        lines.append("<!-- LOOM:AUTO_CONTEXT -->")
        lines.append("## Relevant Conventions (from Loom)")
        lines.append("")

        # Top reminders
        if block.top_reminders:
            lines.append("### Top Reminders")
            for i, rule in enumerate(block.top_reminders, 1):
                lines.append(
                    f"{i}. **{rule.rule}** (confidence: {rule.confidence}/10)"
                )
            lines.append("")

        # Summary
        if block.summary:
            lines.append(f"> {block.summary}")
            lines.append("")

        # Rules grouped by domain
        lines.append("### By Domain")
        rules_by_domain: dict[str, list[Rule]] = {}
        for rule in block.rules:
            rules_by_domain.setdefault(rule.domain, []).append(rule)

        for domain in block.domains_covered:
            domain_rules = rules_by_domain.get(domain, [])
            if not domain_rules:
                continue
            lines.append(f"#### {domain}")
            for rule in domain_rules:
                lines.append(
                    f"- {rule.rule_type} ({rule.confidence}/10): {rule.rule}"
                )
            lines.append("")

        return "\n".join(lines)

    def load_context_formatted(
        self,
        task_description: str,
        role: str = "",
        domain: str | None = None,
        max_rules: int = 20,
    ) -> str:
        """Convenience: load context and format it in one call.

        Equivalent to``loader.format_context_block(loader.load_context(...))``.
        """
        block = self.load_context(task_description, role, domain, max_rules)
        return self.format_context_block(block)

    # ── internal helpers ────────────────────────────────────────────────

    def _resolve_domains(
        self,
        task_description: str,
        role: str,
        domain: str | None,
    ) -> list[str]:
        """Resolve the final domain list from all inputs."""
        if domain:
            return [domain]

        domains = self._match_domains(task_description)

        # Bias toward role-relevant domains.
        if role:
            bias = _ROLE_DOMAIN_BIAS.get(role.lower(), [])
            for d in bias:
                if d not in domains:
                    domains.append(d)

        # Always include a sensible fallback.
        if not domains:
            domains = ["coding", "testing"]

        return domains

    def _match_domains(self, task_description: str) -> list[str]:
        """Run the smart domain matchers against a task description."""
        domains: list[str] = []
        seen: set[str] = set()

        for pattern, domain_list in _SMART_DOMAIN_MAP:
            if pattern.search(task_description):
                for d in domain_list:
                    if d not in seen:
                        domains.append(d)
                        seen.add(d)

        return domains

    def _collect_rules(
        self,
        domains: list[str],
        task_description: str,
        max_rules: int,
    ) -> list[Rule]:
        """Collect rules across domains, scored by relevance, then truncated."""
        all_scored: list[tuple[int, Rule]] = []

        for d in domains:
            domain_rules = self.store.get_rules_by_domain(d, min_confidence=1)
            for rule in domain_rules:
                score = self._relevance_score(rule, task_description)
                all_scored.append((score, rule))

        # Sort: score desc, then confidence desc, then times_confirmed desc.
        all_scored.sort(
            key=lambda x: (
                x[0],
                x[1].confidence,
                x[1].times_confirmed,
            ),
            reverse=True,
        )

        rules = [r for _, r in all_scored[:max_rules]]
        return rules

    def _collect_org_rules(
        self,
        domains: list[str],
        task_description: str,
    ) -> list[Rule]:
        """Collect relevant rules from the org store."""
        if not self.org_store:
            return []

        results: list[Rule] = []
        for d in domains:
            domain_rules = self.org_store.search_rules(task_description, domain=d)
            results.extend(domain_rules)

        results.sort(key=lambda r: (r.confidence, r.times_confirmed), reverse=True)
        return results[:5]

    def _relevance_score(self, rule: Rule, task_description: str) -> int:
        """Score how relevant a rule is to the task description.

        A simple overlap heuristic: more keyword intersections = higher score.
        Returns 0 when there is no apparent relevance.
        """
        task_lower = task_description.lower()
        score = 0

        # Check rule text fields.
        fields = [
            rule.rule,
            rule.rule_type,
            rule.domain,
            rule.example,
        ]
        for field in fields:
            if not field:
                continue
            field_lower = field.lower()
            # Count word-level overlaps.
            words = re.findall(r"\w+", field_lower)
            for w in words:
                if len(w) >= 3 and w in task_lower:
                    score += 2
            # Boost for full phrase matches.
            if len(field_lower) > 10 and field_lower in task_lower:
                score += 5

        # Bonus for high confidence — well-proven rules are likely relevant.
        if rule.confidence >= 8:
            score += 3
        elif rule.confidence >= 5:
            score += 1

        return score

    def _pick_top_reminders(self, rules: list[Rule]) -> list[Rule]:
        """Pick the top N rules by confidence (already sorted)."""
        if not rules:
            return []
        sorted_rules = sorted(
            rules,
            key=lambda r: (r.confidence, r.times_confirmed),
            reverse=True,
        )
        return sorted_rules[: self._TOP_COUNT]

    def _build_summary(
        self,
        rules: list[Rule],
        domains: list[str],
    ) -> str:
        """Build a 1-2 sentence summary of key conventions."""
        if not rules:
            return f"No conventions found for domains: {', '.join(domains)}."

        top = self._pick_top_reminders(rules)
        if not top:
            return f"{len(rules)} conventions loaded across {len(domains)} domains."

        # Use the top reminder rule text as the anchor.
        anchor = top[0].rule

        return (
            f"Loaded {len(rules)} convention rules across "
            f"{len(domains)} domains ({', '.join(domains[:4])}{'...' if len(domains) > 4 else ''}). "
            f"Key principle: {anchor}"
        )

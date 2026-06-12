"""OrgStore — centralized memory layer that spans multiple projects.

Every agent in an organization shares from one repository of learning.

OrgStore is backed by a JSON file at a configurable path (default:
``$LOOM_ORG_STORE`` env var or ``~/.loom/org-store.json``). It stores
all rules from all projects with project-scoping metadata so learning
accumulates across every project a team touches.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .rule_store import Rule


# ── platform-aware file locking ────────────────────────────────────────

def _lock_file(f):
    """Acquire an exclusive advisory lock on *f* (a file object)."""
    try:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    except ImportError:
        try:
            import msvcrt

            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        except ImportError:
            pass  # best-effort on unsupported platforms


def _unlock_file(f):
    """Release an advisory lock held on *f*."""
    try:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except ImportError:
        try:
            import msvcrt

            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except ImportError:
            pass


# ── data model ─────────────────────────────────────────────────────────


@dataclass
class OrgRule:
    """A rule enriched with org-wide scoping metadata.

    Extends the base ``Rule`` contract with fields that capture which
    project produced the rule, what tags (roles) it is relevant for,
    its visibility scope, retention policy, and the decision-making
    context that produced it.
    """

    id: str
    domain: str
    rule_type: str
    rule: str
    example: str = ""
    confidence: int = 5
    times_confirmed: int = 0
    times_violated: int = 0
    sources: list[str] = field(default_factory=list)
    source_type: str = ""
    created_at: str = ""
    updated_at: str = ""

    # ── org-scoping fields ──
    project: str = ""
    tags: list[str] = field(default_factory=list)
    scope: str = "org"  # "org" | "project" | "role"
    retention: str = "standard"  # "permanent" | "long_term" | "standard"
    author: str = ""
    decision_context: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "rule_type": self.rule_type,
            "rule": self.rule,
            "example": self.example,
            "confidence": self.confidence,
            "times_confirmed": self.times_confirmed,
            "times_violated": self.times_violated,
            "sources": self.sources,
            "source_type": self.source_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "project": self.project,
            "tags": self.tags,
            "scope": self.scope,
            "retention": self.retention,
            "author": self.author,
            "decision_context": self.decision_context,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OrgRule":
        sources = d.get("sources", d.get("source_urls", []))
        return cls(
            id=d["id"],
            domain=d["domain"],
            rule_type=d["rule_type"],
            rule=d.get("rule", d.get("pattern", "")),
            example=d.get("example", ""),
            confidence=d.get("confidence", 5),
            times_confirmed=d.get("times_confirmed", 0),
            times_violated=d.get("times_violated", 0),
            sources=sources,
            source_type=d.get("source_type", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            project=d.get("project", ""),
            tags=d.get("tags", []),
            scope=d.get("scope", "org"),
            retention=d.get("retention", "standard"),
            author=d.get("author", ""),
            decision_context=d.get("decision_context", ""),
        )

    def to_rule(self) -> Rule:
        """Convert back to a base ``Rule`` (drops org-scoping fields)."""
        return Rule(
            id=self.id,
            domain=self.domain,
            rule_type=self.rule_type,
            rule=self.rule,
            example=self.example,
            confidence=self.confidence,
            times_confirmed=self.times_confirmed,
            times_violated=self.times_violated,
            sources=list(self.sources),
            source_type=self.source_type,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


# ── store ──────────────────────────────────────────────────────────────


class OrgStore:
    """Centralized memory layer spanning all projects in an organization.

    Backed by a single JSON file. Every agent across every project
    reads from and writes to the same store so learning accumulates
    globally.

    Parameters
    ----------
    path:
        Path to the JSON backing file.  Defaults to ``$LOOM_ORG_STORE``
        or ``~/.loom/org-store.json``.

    Notes
    -----
    Writes acquire an advisory file lock (``fcntl`` on POSIX, ``msvcrt``
    on Windows) so concurrent access from multiple processes is safe.
    """

    def __init__(self, path: Path | str | None = None):
        if path is None:
            env_path = os.environ.get("LOOM_ORG_STORE")
            if env_path:
                path = Path(env_path)
            else:
                path = Path.home() / ".loom" / "org-store.json"
        self.path = Path(path)
        self.rules: dict[str, OrgRule] = {}
        if self.path.exists():
            self._load()

    # ── persistence ────────────────────────────────────────────────

    def _load(self):
        """Load rules from the backing JSON file."""
        try:
            data = json.loads(self.path.read_text())
            for rule_dict in data.get("rules", []):
                rule = OrgRule.from_dict(rule_dict)
                self.rules[rule.id] = rule
        except (json.JSONDecodeError, KeyError):
            self.rules = {}

    def _save(self):
        """Persist rules to the backing JSON file under a file lock."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"rules": [r.to_dict() for r in self.rules.values()]}
        payload = json.dumps(data, indent=2)
        with open(self.path, "w") as f:
            _lock_file(f)
            try:
                f.write(payload)
            finally:
                _unlock_file(f)

    def _make_id(self, domain: str, rule_type: str, rule_text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", rule_text.lower().strip())[:60].strip("-")
        return f"{domain}::{rule_type}::{slug}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── resolve path helper ────────────────────────────────────────

    @staticmethod
    def default_path() -> Path:
        """Return the default store path without creating anything."""
        env_path = os.environ.get("LOOM_ORG_STORE")
        if env_path:
            return Path(env_path)
        return Path.home() / ".loom" / "org-store.json"

    # ── CRUD ───────────────────────────────────────────────────────

    def get_rule(self, rule_id: str) -> OrgRule | None:
        """Look up a single rule by id."""
        return self.rules.get(rule_id)

    def add_rule(
        self,
        domain: str,
        rule_type: str,
        rule: str,
        project: str,
        example: str = "",
        confidence: int = 5,
        source_url: str = "",
        sources: list[str] | None = None,
        source_type: str = "",
        tags: list[str] | None = None,
        scope: str = "org",
        retention: str = "standard",
        author: str = "",
        decision_context: str = "",
    ) -> OrgRule:
        """Add (or confirm) a rule with project-scoping metadata.

        If a rule with the same deterministic id already exists its
        confidence is bumped and confirmation count incremented (just
        like ``RuleStore.add_rule``), and the org-scoping metadata is
        merged.

        Parameters
        ----------
        domain:
            Convention domain (e.g. ``"python"``, ``"git"``).
        rule_type:
            Short tag for the category of convention.
        rule:
            The rule text / pattern.
        project:
            Human-readable project name that produced this rule.
        example:
            An example snippet illustrating the rule.
        confidence:
            Initial confidence (1–10).  Default 5.
        source_url:
            Deprecated — prefer *sources*.
        sources:
            List of source URLs or file paths.
        source_type:
            Kind of source (``"copied"``, ``"pr"``, ``"manual"``, etc.).
        tags:
            Role-based tags (e.g. ``["engineering", "support"]``).
        scope:
            Visibility scope — ``"org"``, ``"project"``, or ``"role"``.
        retention:
            Retention tier — ``"permanent"``, ``"long_term"``, or ``"standard"``.
        author:
            Human-readable name of the agent or person who authored the rule.
        decision_context:
            Free-form explanation of *why* the rule was created.
        """
        rule_id = self._make_id(domain, rule_type, rule)
        now = self._now()

        source_list = list(sources) if sources else []
        if source_url and source_url not in source_list:
            source_list.append(source_url)
        tag_list = list(tags) if tags else []

        if rule_id in self.rules:
            existing = self.rules[rule_id]
            existing.confidence = min(10, existing.confidence + 1)
            existing.times_confirmed += 1
            existing.updated_at = now
            for src in source_list:
                if src not in existing.sources:
                    existing.sources.append(src)
            if source_type:
                existing.source_type = source_type
            for t in tag_list:
                if t not in existing.tags:
                    existing.tags.append(t)
            if decision_context and decision_context != existing.decision_context:
                existing.decision_context = (
                    existing.decision_context + "\n---\n" + decision_context
                )
            if author:
                existing.author = author
            if scope and scope != existing.scope:
                existing.scope = scope
            self._save()
            return existing

        new_rule = OrgRule(
            id=rule_id,
            domain=domain,
            rule_type=rule_type,
            rule=rule,
            example=example,
            confidence=confidence,
            times_confirmed=1,
            sources=source_list,
            source_type=source_type,
            created_at=now,
            updated_at=now,
            project=project,
            tags=tag_list,
            scope=scope,
            retention=retention,
            author=author,
            decision_context=decision_context,
        )
        self.rules[new_rule.id] = new_rule
        self._save()
        return new_rule

    def promote_rule(self, rule_id: str) -> OrgRule | None:
        """Increment confidence for the given rule."""
        rule = self.rules.get(rule_id)
        if rule:
            rule.confidence = min(10, rule.confidence + 1)
            rule.times_confirmed += 1
            rule.updated_at = self._now()
            self._save()
        return rule

    def demote_rule(self, rule_id: str) -> OrgRule | None:
        """Decrement confidence for the given rule."""
        rule = self.rules.get(rule_id)
        if rule:
            rule.confidence = max(1, rule.confidence - 1)
            rule.times_violated += 1
            rule.updated_at = self._now()
            self._save()
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Remove a rule entirely.  Returns whether anything was deleted."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            self._save()
            return True
        return False

    # ── org-scoped queries ─────────────────────────────────────────

    def get_org_rules(
        self,
        min_confidence: int = 1,
        project: str | None = None,
        tags: list[str] | None = None,
        scope: str | None = None,
    ) -> list[OrgRule]:
        """Get rules across projects, optionally filtered.

        Parameters
        ----------
        min_confidence:
            Minimum confidence threshold (inclusive).
        project:
            If given, only return rules from this project.
        tags:
            If given, only return rules that have at least one matching tag.
        scope:
            If given, only return rules with this scope (``"org"``, ``"project"``, ``"role"``).
        """
        results: list[OrgRule] = []
        for rule in self.rules.values():
            if rule.confidence < min_confidence:
                continue
            if project is not None and rule.project != project:
                continue
            if tags is not None:
                if not any(t in rule.tags for t in tags):
                    continue
            if scope is not None and rule.scope != scope:
                continue
            results.append(rule)
        results.sort(key=lambda r: (r.confidence, r.times_confirmed), reverse=True)
        return results

    def search_org(
        self,
        query: str,
        project: str | None = None,
        tags: list[str] | None = None,
        role: str | None = None,
        limit: int | None = None,
        min_confidence: int = 1,
    ) -> list[OrgRule]:
        """Full-text search across the entire org knowledge base.

        Parameters
        ----------
        query:
            Free-text query.  Matched against id, domain, rule_type, rule,
            sources, source_type, project, tags, decision_context, and author.
        project:
            Optional project filter.
        tags:
            Optional tag filter (any match).
        role:
            Convenience shorthand — if given, also matches rules
            whose *tags* contain this value.
        limit:
            Maximum results to return.
        min_confidence:
            Minimum confidence threshold.
        """
        query_lower = query.lower()
        # Collect the tag match set early so we don't recompute it per rule.
        tag_filter: set[str] | None = set(tags) if tags else None
        if role:
            tag_filter = (tag_filter | {role}) if tag_filter else {role}

        results: list[OrgRule] = []
        for rule in self.rules.values():
            if rule.confidence < min_confidence:
                continue
            if project is not None and rule.project != project:
                continue
            if tag_filter is not None:
                if not tag_filter.intersection(rule.tags):
                    continue
            # Build a composite searchable string from every text field.
            searchable = (
                rule.rule.lower()
                + " "
                + rule.rule_type.lower()
                + " "
                + rule.id.lower()
                + " "
                + rule.domain.lower()
                + " "
                + " ".join(rule.sources).lower()
                + " "
                + rule.source_type.lower()
                + " "
                + rule.project.lower()
                + " "
                + " ".join(rule.tags).lower()
                + " "
                + rule.decision_context.lower()
                + " "
                + rule.author.lower()
                + " "
                + rule.example.lower()
            )
            if query_lower in searchable:
                results.append(rule)

        results.sort(key=lambda r: (r.confidence, r.times_confirmed), reverse=True)
        if limit:
            results = results[:limit]
        return results

    def get_rules_by_tag(self, tag: str, min_confidence: int = 1) -> list[OrgRule]:
        """Return every rule tagged for a specific role (e.g. ``"engineering"``).

        Parameters
        ----------
        tag:
            The tag to match.
        min_confidence:
            Minimum confidence threshold.
        """
        results: list[OrgRule] = []
        for rule in self.rules.values():
            if rule.confidence < min_confidence:
                continue
            if tag in rule.tags:
                results.append(rule)
        results.sort(key=lambda r: (r.confidence, r.times_confirmed), reverse=True)
        return results

    def get_rules_by_project(
        self, project: str, min_confidence: int = 1
    ) -> list[OrgRule]:
        """Return every rule originating from a specific project."""
        return self.get_org_rules(min_confidence=min_confidence, project=project)

    # ── federation ─────────────────────────────────────────────────

    def federate_project(self, project_root: str | Path) -> int:
        """Ingest rules from a project-level ``.loom/rules.json`` into the org store.

        Reads ``<project_root>/.loom/rules.json``, converts every ``Rule``
        into an ``OrgRule`` stamped with the project name (derived from
        the directory name), and merges them into the org store.

        Existing rules with the same id are upgraded in confidence rather
        than duplicated.

        Returns
        -------
        int
            Number of rules ingested.
        """
        project_root = Path(project_root).resolve()
        rules_file = project_root / ".loom" / "rules.json"
        if not rules_file.exists():
            return 0

        try:
            data = json.loads(rules_file.read_text())
        except (json.JSONDecodeError, OSError):
            return 0

        project_name = project_root.name
        raw_rules = data.get("rules", [])
        count = 0

        for rule_dict in raw_rules:
            rule = Rule.from_dict(rule_dict)
            org_id = rule.id
            now = self._now()

            if org_id in self.rules:
                existing = self.rules[org_id]
                existing.confidence = min(10, existing.confidence + 1)
                existing.times_confirmed += 1
                existing.updated_at = now
                if project_name not in existing.project and existing.project:
                    # Multiple projects confirm the same rule — mark it org-scoped.
                    existing.scope = "org"
                    existing.project = f"{existing.project},{project_name}"
            else:
                org_rule = OrgRule(
                    id=rule.id,
                    domain=rule.domain,
                    rule_type=rule.rule_type,
                    rule=rule.rule,
                    example=rule.example,
                    confidence=rule.confidence,
                    times_confirmed=rule.times_confirmed,
                    times_violated=rule.times_violated,
                    sources=list(rule.sources),
                    source_type=rule.source_type,
                    created_at=rule.created_at or now,
                    updated_at=now,
                    project=project_name,
                    scope="project",
                    retention="standard",
                )
                self.rules[org_rule.id] = org_rule
            count += 1

        if count:
            self._save()
        return count

    # ── cross-project context ──────────────────────────────────────

    def get_cross_project_context(
        self,
        project: str,
        query: str,
        limit: int = 10,
    ) -> list[OrgRule]:
        """Find relevant rules from **other** projects that may apply to *project*.

        This is the key method that enables transfer learning across
        projects — when an agent is working on *project* it can query
        what every other project has already learned about a topic.

        Parameters
        ----------
        project:
            The project to **exclude** (we want context from everywhere else).
        query:
            Free-text query to match against the org store.
        limit:
            Maximum results.
        """
        query_lower = query.lower()
        results: list[OrgRule] = []

        for rule in self.rules.values():
            if rule.confidence < 1:
                continue
            # Exclude rules that belong to the requesting project.
            stored_projects = {p.strip() for p in rule.project.split(",") if p.strip()}
            if project in stored_projects and len(stored_projects) == 1:
                continue

            searchable = (
                rule.rule.lower()
                + " "
                + rule.rule_type.lower()
                + " "
                + rule.id.lower()
                + " "
                + rule.domain.lower()
                + " "
                + " ".join(rule.sources).lower()
                + " "
                + rule.source_type.lower()
                + " "
                + rule.project.lower()
                + " "
                + " ".join(rule.tags).lower()
                + " "
                + rule.decision_context.lower()
                + " "
                + rule.author.lower()
                + " "
                + rule.example.lower()
            )
            if query_lower in searchable:
                results.append(rule)

        results.sort(key=lambda r: (r.confidence, r.times_confirmed), reverse=True)
        return results[:limit]

    # ── summarization & onboarding ─────────────────────────────────

    def summarize_for_onboarding(
        self,
        role_tags: list[str] | None = None,
        min_confidence: int = 3,
        limit: int = 10,
    ) -> list[OrgRule]:
        """Return the top *limit* most relevant rules for onboarding a given role.

        Rules are ranked by confidence (descending), then times_confirmed
        (descending), then filtered to those matching at least one of the
        *role_tags* (when provided).

        Parameters
        ----------
        role_tags:
            Role tags to filter by (e.g. ``["engineering"]``).
            If ``None`` or empty, returns top rules across all roles.
        min_confidence:
            Minimum confidence threshold (default 3 — above noise).
        limit:
            Maximum number of rules to return (default 10).
        """
        candidates = self.get_org_rules(
            min_confidence=min_confidence,
            tags=role_tags if role_tags else None,
        )
        # get_org_rules already sorts by (confidence, times_confirmed) desc.
        return candidates[:limit]

    def get_timeline(self, min_confidence: int = 1) -> list[OrgRule]:
        """Return all rules sorted by ``created_at``, most recent first.

        Each rule carries full ``decision_context`` so the timeline tells
        the story of *why* every decision was made across the org.

        Parameters
        ----------
        min_confidence:
            Minimum confidence threshold (default 1 — everything).
        """
        results = [r for r in self.rules.values() if r.confidence >= min_confidence]
        # Sort by created_at descending; rules without a timestamp sort last.
        results.sort(
            key=lambda r: r.created_at if r.created_at else "",
            reverse=True,
        )
        return results

    # ── stats & export ─────────────────────────────────────────────

    def get_org_stats(self) -> dict[str, Any]:
        """Return aggregate statistics across all projects.

        Returns a dictionary with:

        - ``total_rules``
        - ``total_projects``
        - ``by_project`` — per-project rule counts and average confidence
        - ``by_tag`` — per-tag rule counts
        - ``by_scope`` — rule counts broken down by scope
        - ``by_retention`` — rule counts broken down by retention tier
        - ``avg_confidence`` — overall average confidence
        """
        stats: dict[str, Any] = {
            "total_rules": len(self.rules),
            "total_projects": 0,
            "by_project": {},
            "by_tag": {},
            "by_scope": {},
            "by_retention": {},
            "avg_confidence": 0.0,
        }

        projects_seen: set[str] = set()

        for rule in self.rules.values():
            # Collect unique projects (a rule may be confirmed by multiple).
            for p in rule.project.split(","):
                p = p.strip()
                if p:
                    projects_seen.add(p)

            # By project
            proj_key = rule.project or "(unknown)"
            if proj_key not in stats["by_project"]:
                stats["by_project"][proj_key] = {
                    "count": 0,
                    "confidence_sum": 0,
                }
            stats["by_project"][proj_key]["count"] += 1
            stats["by_project"][proj_key]["confidence_sum"] += rule.confidence

            # By tag
            for t in rule.tags:
                stats["by_tag"][t] = stats["by_tag"].get(t, 0) + 1

            # By scope
            scope = rule.scope or "org"
            stats["by_scope"][scope] = stats["by_scope"].get(scope, 0) + 1

            # By retention
            retention = rule.retention or "standard"
            stats["by_retention"][retention] = stats["by_retention"].get(retention, 0) + 1

        stats["total_projects"] = len(projects_seen)

        # Compute per-project avg confidence
        for proj_key, proj_stats in stats["by_project"].items():
            proj_stats["avg_confidence"] = (
                proj_stats["confidence_sum"] / max(proj_stats["count"], 1)
            )
            del proj_stats["confidence_sum"]

        # Overall avg confidence
        if self.rules:
            stats["avg_confidence"] = sum(
                r.confidence for r in self.rules.values()
            ) / len(self.rules)

        return stats

    def export_org(self, format: str = "json") -> str | dict[str, Any]:
        """Export the full org knowledge base.

        Parameters
        ----------
        format:
            ``"json"`` — returns the full dict (caller can json.dumps).
            ``"summary"`` — returns a compact dict with stats and top rules.

        Returns
        -------
        str or dict
            JSON string for ``"json"``, dict for ``"summary"``.
        """
        if format == "summary":
            stats = self.get_org_stats()
            top_rules = sorted(
                self.rules.values(),
                key=lambda r: (r.confidence, r.times_confirmed),
                reverse=True,
            )[:50]
            return {
                "stats": stats,
                "top_rules": [r.to_dict() for r in top_rules],
            }

        # Default: full JSON export
        data = {
            "exported_at": self._now(),
            "rules": [r.to_dict() for r in self.rules.values()],
        }
        return json.dumps(data, indent=2)

    # ── bulk operations ────────────────────────────────────────────

    def reload(self):
        """Re-read the backing file, discarding in-memory changes."""
        self.rules.clear()
        if self.path.exists():
            self._load()

    def __len__(self) -> int:
        return len(self.rules)

    def __contains__(self, rule_id: str) -> bool:
        return rule_id in self.rules

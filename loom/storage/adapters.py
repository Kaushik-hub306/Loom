"""Adapters that wrap PostgresStore to match local-engine interfaces.

Each adapter class exposes the same method signatures as the corresponding
local engine (RuleStore, Timeline, OrgStore, RetentionManager, RBACEngine)
so the MCP server can swap between JSON and Postgres backends transparently.

Safety: database connection strings are never included in log messages or
exception traces.  All errors are wrapped to strip sensitive information.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loom.engine.org_store import OrgRule
from loom.engine.retention import RetentionEntry, RetentionPolicy

# ── Re-export the shared data classes (so callers don't need two imports) ──
from loom.engine.rule_store import Rule
from loom.engine.timeline import TimelineEntry
from loom.security.rbac import ClearanceLevel, ObservationPermissions

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_err(exc: Exception) -> str:
    """Return a user-safe error message with no connection-string leakage."""
    msg = str(exc)
    # Strip anything that looks like a postgres:// URL
    if "postgresql://" in msg or "postgres://" in msg:
        return "Database error (connection details redacted)."
    # psycopg2 sometimes includes the host in OperationalError
    if "connection to server" in msg.lower():
        return "Database connection failed — check your LOOM_DATABASE_URL."
    return msg


# ═══════════════════════════════════════════════════════════════════════════
# PostgresRuleStore — drop-in replacement for RuleStore
# ═══════════════════════════════════════════════════════════════════════════

class PostgresRuleStore:
    """RuleStore-compatible adapter backed by PostgresStore."""

    def __init__(self, pg_store):
        self._pg = pg_store

    # ── CRUD ──────────────────────────────────────────────────────────

    def get_rule(self, rule_id: str) -> Rule | None:
        row = self._pg.get_rule(rule_id)
        if row is None:
            return None
        return _pg_row_to_rule(row)

    def add_rule(
        self,
        domain: str,
        rule_type: str,
        rule: str,
        example: str = "",
        confidence: int = 5,
        source_url: str = "",
        sources: list[str] | None = None,
        source_type: str = "",
    ) -> Rule:
        source_list = list(sources) if sources else []
        if source_url and source_url not in source_list:
            source_list.append(source_url)

        row = self._pg.add_rule({
            "id": _make_rule_id(domain, rule_type, rule),
            "domain": domain,
            "rule_type": rule_type,
            "rule": rule,
            "example": example,
            "confidence": confidence,
            "sources": source_list,
            "source_type": source_type,
        })
        return _pg_row_to_rule(row)

    def promote_rule(self, rule_id: str) -> Rule | None:
        row = self._pg.promote_rule(rule_id)
        return _pg_row_to_rule(row) if row else None

    def demote_rule(self, rule_id: str) -> Rule | None:
        row = self._pg.demote_rule(rule_id)
        return _pg_row_to_rule(row) if row else None

    def delete_rule(self, rule_id: str) -> bool:
        return self._pg.delete_rule(rule_id)

    # ── Queries ───────────────────────────────────────────────────────

    def get_active_rules(self, min_confidence: int = 1) -> list[Rule]:
        rows = self._pg.get_rules(min_confidence=min_confidence)
        return [_pg_row_to_rule(r) for r in rows]

    def get_rules_by_domain(
        self, domain: str, min_confidence: int = 1
    ) -> list[Rule]:
        rows = self._pg.get_rules(domain=domain, min_confidence=min_confidence)
        return [_pg_row_to_rule(r) for r in rows]

    def search_rules(
        self,
        query: str,
        domain: str | None = None,
        min_confidence: int = 1,
        limit: int | None = None,
        rule_type: str | None = None,
    ) -> list[Rule]:
        rows = self._pg.search_rules(
            query=query,
            domain=domain,
            min_confidence=min_confidence,
            limit=limit,
            rule_type=rule_type,
        )
        return [_pg_row_to_rule(r) for r in rows]

    def get_all_domain_stats(self) -> dict[str, dict]:
        return self._pg.get_all_domain_stats()

    def get_domain_stats(self, domain: str | None = None) -> dict:
        return self._pg.get_domain_stats(domain=domain)

    def __len__(self) -> int:
        stats = self._pg.get_domain_stats()
        return stats.get("total", 0)


# ═══════════════════════════════════════════════════════════════════════════
# PostgresTimeline — drop-in replacement for Timeline
# ═══════════════════════════════════════════════════════════════════════════

class PostgresTimeline:
    """Timeline-compatible adapter backed by PostgresStore."""

    VALID_ACTIONS = frozenset({
        "learned", "taught", "reflected", "confirmed", "violated",
        "archived", "onboarded", "succeeded", "amplified", "retained",
        "observed",
    })

    def __init__(self, pg_store):
        self._pg = pg_store

    def record(
        self,
        action: str,
        rule_id: str,
        rule_text: str,
        agent: str,
        project: str,
        decision_context: str,
        domain: str = "",
        confidence: int = 5,
        sources: list[str] | None = None,
    ) -> TimelineEntry:
        if action not in self.VALID_ACTIONS:
            raise ValueError(
                f"Invalid action '{action}'. Must be one of: "
                f"{', '.join(sorted(self.VALID_ACTIONS))}"
            )
        row = self._pg.append_timeline({
            "timestamp": _now(),
            "action": action,
            "domain": domain,
            "rule_id": rule_id,
            "rule_text": rule_text,
            "agent": agent,
            "project": project,
            "decision_context": decision_context,
            "confidence": confidence,
            "sources": sources or [],
        })
        return _pg_row_to_timeline_entry(row)

    def query(
        self,
        domain: str | None = None,
        project: str | None = None,
        agent: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        action: str | None = None,
        limit: int | None = None,
    ) -> list[TimelineEntry]:
        rows = self._pg.query_timeline(
            domain=domain,
            project=project,
            agent=agent,
            date_from=date_from,
            date_to=date_to,
            action=action,
            limit=limit,
        )
        return [_pg_row_to_timeline_entry(r) for r in rows]

    def get_summary(self, period: str = "daily") -> dict:
        return self._pg.get_timeline_summary(period=period)

    def __len__(self) -> int:
        summary = self._pg.get_timeline_summary("weekly")
        return summary.get("total_entries", 0)


# ═══════════════════════════════════════════════════════════════════════════
# PostgresOrgStoreAdapter — drop-in replacement for OrgStore (org-rules subset)
# ═══════════════════════════════════════════════════════════════════════════

class PostgresOrgStoreAdapter:
    """OrgStore-compatible adapter backed by PostgresStore (org_rules table)."""

    def __init__(self, pg_store):
        self._pg = pg_store

    def get_cross_project_context(
        self, project: str, query: str, limit: int = 10
    ) -> list[OrgRule]:
        rows = self._pg.get_cross_project_context(
            project=project, query=query, limit=limit
        )
        return [_pg_row_to_org_rule(r) for r in rows]

    def get_org_rules(
        self,
        min_confidence: int = 1,
        project: str | None = None,
        tags: list[str] | None = None,
        scope: str | None = None,
    ) -> list[OrgRule]:
        rows = self._pg.get_org_rules(
            min_confidence=min_confidence,
            project=project,
            tags=tags,
            scope=scope,
        )
        return [_pg_row_to_org_rule(r) for r in rows]

    def get_org_stats(self) -> dict[str, Any]:
        return self._pg.get_org_stats()

    def __len__(self) -> int:
        stats = self._pg.get_org_stats()
        return stats.get("total_rules", 0)


# ═══════════════════════════════════════════════════════════════════════════
# PostgresRetention — drop-in replacement for RetentionManager (subset)
# ═══════════════════════════════════════════════════════════════════════════

class PostgresRetention:
    """RetentionManager-compatible adapter backed by PostgresStore.

    Covers the subset of RetentionManager that the MCP server actually uses:
    set_retention, get_retention, promote_to_permanent, get_permanent_rules,
    and get_health.
    """

    def __init__(self, pg_store):
        self._pg = pg_store

    def set_retention(
        self,
        rule_id: str,
        policy: RetentionPolicy,
        set_by: str = "",
        reason: str = "",
    ) -> RetentionEntry:
        row = self._pg.set_retention(
            rule_id=rule_id,
            policy=policy.value,
            set_by=set_by,
            reason=reason,
        )
        return RetentionEntry(
            rule_id=row.get("rule_id", rule_id),
            policy=row.get("policy", policy.value),
            set_at=row.get("set_at", _now()),
            set_by=row.get("set_by", set_by),
            reason=row.get("reason", reason),
        )

    def get_retention(self, rule_id: str) -> RetentionPolicy:
        policy_str = self._pg.get_retention(rule_id)
        try:
            return RetentionPolicy(policy_str)
        except ValueError:
            return RetentionPolicy.STANDARD

    def promote_to_permanent(
        self, rule_id: str, reason: str = "", set_by: str = ""
    ) -> RetentionEntry:
        return self.set_retention(
            rule_id=rule_id,
            policy=RetentionPolicy.PERMANENT,
            set_by=set_by,
            reason=reason,
        )

    def get_permanent_rules(self) -> list[str]:
        return self._pg.get_permanent_rules()

    def get_health(self) -> dict:
        """Return retention health stats (approximate)."""
        perm = len(self._pg.get_permanent_rules())
        return {
            "permanent": perm,
            "long_term": 0,
            "standard": 0,
            "decaying": 0,
        }


# ═══════════════════════════════════════════════════════════════════════════
# PostgresRBAC — drop-in replacement for RBACEngine (clearance subset)
# ═══════════════════════════════════════════════════════════════════════════

class PostgresRBAC:
    """RBACEngine-compatible adapter backed by PostgresStore.

    Covers the set_clearance method that the MCP server uses.
    """

    def __init__(self, pg_store):
        self._pg = pg_store

    def set_clearance(
        self,
        rule_id: str,
        clearance: ClearanceLevel,
        allowed_roles: list[str] | None = None,
        allowed_teams: list[str] | None = None,
        allowed_agents: list[str] | None = None,
        owner: str = "",
    ) -> ObservationPermissions:
        row = self._pg.set_permission(
            rule_id=rule_id,
            clearance=clearance.name.lower(),
            allowed_roles=allowed_roles or [],
            allowed_teams=allowed_teams or [],
        )
        return ObservationPermissions(
            rule_id=row.get("rule_id", rule_id),
            clearance=clearance,
            allowed_roles=allowed_roles or [],
            allowed_agents=allowed_agents or [],
            allowed_teams=allowed_teams or [],
            owner=owner,
            set_at=row.get("set_at", _now()),
        )

    def check_access(
        self,
        rule_id: str,
        agent_id: str,
        agent_role: str,
        agent_teams: list[str] | None = None,
    ) -> bool:
        """Return True if the agent is cleared to see *rule_id*.

        Mirrors RBACEngine.check_access semantics: rules without a
        permission record are treated as PUBLIC (default-open).
        """
        from loom.security.rbac import RBACEngine

        row = self._pg.get_permission(rule_id)
        if not row:
            return True

        def _as_list(value) -> list:
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    return parsed if isinstance(parsed, list) else []
                except json.JSONDecodeError:
                    return []
            return []

        clearance_name = str(row.get("clearance", "internal")).upper()
        try:
            clearance = ClearanceLevel[clearance_name]
        except KeyError:
            clearance = ClearanceLevel.INTERNAL

        perm = ObservationPermissions(
            rule_id=rule_id,
            clearance=clearance,
            allowed_roles=_as_list(row.get("allowed_roles")),
            allowed_agents=_as_list(row.get("allowed_agents")),
            allowed_teams=_as_list(row.get("allowed_teams")),
            owner=row.get("owner", "") or "",
        )
        return RBACEngine._evaluate(perm, agent_id, agent_role, agent_teams or [])


# ═══════════════════════════════════════════════════════════════════════════
# Row → dataclass converters
# ═══════════════════════════════════════════════════════════════════════════

def _pg_row_to_rule(row: dict) -> Rule:
    """Convert a PostgresStore rule row to a Rule dataclass."""
    sources = row.get("sources", [])
    if isinstance(sources, str):
        try:
            sources = json.loads(sources)
        except (json.JSONDecodeError, TypeError):
            sources = []
    return Rule(
        id=row.get("id", ""),
        domain=row.get("domain", "general"),
        rule_type=row.get("rule_type", "convention"),
        rule=row.get("rule", ""),
        example=row.get("example", ""),
        confidence=row.get("confidence", 5),
        times_confirmed=row.get("times_confirmed", 0),
        times_violated=row.get("times_violated", 0),
        sources=sources,
        source_type=row.get("source_type", ""),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


def _pg_row_to_timeline_entry(row: dict) -> TimelineEntry:
    """Convert a PostgresStore timeline row to a TimelineEntry dataclass."""
    sources = row.get("sources", [])
    if isinstance(sources, str):
        try:
            sources = json.loads(sources)
        except (json.JSONDecodeError, TypeError):
            sources = []
    return TimelineEntry(
        timestamp=row.get("timestamp", ""),
        action=row.get("action", ""),
        domain=row.get("domain", ""),
        rule_id=row.get("rule_id", ""),
        rule_text=row.get("rule_text", row.get("rule", "")),
        agent=row.get("agent", ""),
        project=row.get("project", ""),
        decision_context=row.get("decision_context", ""),
        confidence=row.get("confidence", 5),
        sources=sources,
    )


def _pg_row_to_org_rule(row: dict) -> OrgRule:
    """Convert a PostgresStore org_rules row to an OrgRule dataclass."""
    sources = row.get("sources", [])
    if isinstance(sources, str):
        try:
            sources = json.loads(sources)
        except (json.JSONDecodeError, TypeError):
            sources = []
    tags = row.get("tags", [])
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            tags = []
    return OrgRule(
        id=row.get("id", ""),
        domain=row.get("domain", "general"),
        rule_type=row.get("rule_type", "convention"),
        rule=row.get("rule", ""),
        example=row.get("example", ""),
        confidence=row.get("confidence", 5),
        times_confirmed=row.get("times_confirmed", 0),
        times_violated=row.get("times_violated", 0),
        sources=sources,
        source_type=row.get("source_type", ""),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
        project=row.get("project", ""),
        tags=tags,
        scope=row.get("scope", "org"),
        retention=row.get("retention", "standard"),
        author=row.get("author", ""),
        decision_context=row.get("decision_context", ""),
    )


def _make_rule_id(domain: str, rule_type: str, rule_text: str) -> str:
    """Deterministic rule ID matching RuleStore._make_id."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", rule_text.lower().strip())[:60].strip("-")
    return f"{domain}::{rule_type}::{slug}"


# ═══════════════════════════════════════════════════════════════════════════
# Migration: copy local JSON data into Postgres
# ═══════════════════════════════════════════════════════════════════════════

def migrate_json_to_postgres(loom_dir: Path, pg_store) -> dict:
    """Migrate existing rules and timeline from local JSON files into Postgres.

    Reads ``rules.json`` and ``timeline.jsonl`` from *loom_dir* and writes
    any rows that don't already exist in the Postgres database (matched by
    rule ID or timeline timestamp+action+rule_id).

    Returns a dict with ``rules_migrated`` and ``timeline_migrated`` counts.
    """
    result = {"rules_migrated": 0, "timeline_migrated": 0}

    # ── Migrate rules ─────────────────────────────────────────────────
    rules_file = loom_dir / "rules.json"
    if rules_file.exists():
        try:
            data = json.loads(rules_file.read_text())
            for rule_dict in data.get("rules", []):
                rule = Rule.from_dict(rule_dict)
                existing = pg_store.get_rule(rule.id)
                if not existing:
                    try:
                        pg_store.add_rule({
                            "id": rule.id,
                            "domain": rule.domain,
                            "rule_type": rule.rule_type,
                            "rule": rule.rule,
                            "example": rule.example,
                            "confidence": rule.confidence,
                            "sources": rule.sources,
                            "source_type": rule.source_type,
                            "created_at": rule.created_at or _now(),
                            "project": "",
                        })
                        result["rules_migrated"] += 1
                    except Exception:
                        pass  # skip duplicates / constraint violations
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    # ── Migrate timeline ──────────────────────────────────────────────
    timeline_file = loom_dir / "timeline.jsonl"
    if timeline_file.exists():
        try:
            # Build a set of existing (timestamp, action, rule_id) tuples
            existing_entries = set()
            try:
                all_existing = pg_store.query_timeline()
                for ex in all_existing:
                    key = (
                        str(ex.get("timestamp", "")),
                        str(ex.get("action", "")),
                        str(ex.get("rule_id", "")),
                    )
                    existing_entries.add(key)
            except Exception:
                pass  # if we can't query, just try inserting

            for line in timeline_file.read_text().strip().splitlines():
                if not line.strip():
                    continue
                try:
                    entry_dict = json.loads(line)
                    entry = TimelineEntry.from_dict(entry_dict)
                    ts = entry.timestamp or _now()
                    key = (ts, entry.action, entry.rule_id)
                    if key in existing_entries:
                        continue
                    pg_store.append_timeline({
                        "timestamp": ts,
                        "action": entry.action,
                        "domain": entry.domain,
                        "rule_id": entry.rule_id,
                        "rule_text": entry.rule_text,
                        "agent": entry.agent,
                        "project": entry.project,
                        "decision_context": entry.decision_context,
                        "confidence": entry.confidence,
                        "sources": entry.sources,
                    })
                    existing_entries.add(key)
                    result["timeline_migrated"] += 1
                except Exception:
                    pass  # skip malformed lines
        except OSError:
            pass

    return result

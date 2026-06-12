"""RBACEngine — observation-level RBAC: an agent surfaces only what its user is cleared to see.

Complements (does not replace) the existing token-based domain-level access control
in access.py.  Token scope gates *operations* (read/write/admin); RBAC gates
*visibility* per observation so that even a reader token sees only the rules it
is authorised for.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ClearanceLevel(IntEnum):
    """Observation-level clearance — lower value = broader visibility."""
    PUBLIC = 0       # Visible to everyone in the org
    INTERNAL = 1     # Visible to all team members
    CONFIDENTIAL = 2 # Visible to specific roles/teams
    RESTRICTED = 3   # Visible only to explicitly authorised agents
    SECRET = 4       # Requires special clearance (compensation, security incidents, etc.)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AgentContext:
    """The identity bundle passed to every filter / check operation."""
    agent_id: str
    agent_role: str
    agent_teams: list[str] = field(default_factory=list)
    session_type: str = ""  # development, support, sales, admin, etc.


@dataclass
class ObservationPermissions:
    """Per-rule permissions record."""
    rule_id: str
    clearance: ClearanceLevel
    allowed_roles: list[str] = field(default_factory=list)
    allowed_agents: list[str] = field(default_factory=list)
    allowed_teams: list[str] = field(default_factory=list)
    owner: str = ""
    set_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "clearance": self.clearance.value,
            "allowed_roles": self.allowed_roles,
            "allowed_agents": self.allowed_agents,
            "allowed_teams": self.allowed_teams,
            "owner": self.owner,
            "set_at": self.set_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ObservationPermissions":
        return cls(
            rule_id=d["rule_id"],
            clearance=ClearanceLevel(d["clearance"]),
            allowed_roles=d.get("allowed_roles", []),
            allowed_agents=d.get("allowed_agents", []),
            allowed_teams=d.get("allowed_teams", []),
            owner=d.get("owner", ""),
            set_at=d.get("set_at", ""),
        )


# ---------------------------------------------------------------------------
# RBACEngine
# ---------------------------------------------------------------------------

class RBACEngine:
    """Observation-level RBAC — an agent surfaces only what its user is cleared to see.

    Public              (0)  — always visible
    Internal            (1)  — visible if agent has any valid role (non-empty agent_role)
    Confidential        (2)  — role in allowed_roles OR team intersection
    Restricted          (3)  — agent_id in allowed_agents
    Secret              (4)  — agent_id in allowed_agents AND role in allowed_roles
    """

    # ------------------------------------------------------------------
    # Constructors / persistence
    # ------------------------------------------------------------------

    def __init__(self, permissions_path: str | Path):
        self._path = Path(permissions_path)
        self._permissions: dict[str, ObservationPermissions] = {}
        self._policies: list[dict[str, Any]] = []
        self._audit_entries: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Load persisted permissions and policies from disk."""
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            return

        perms_raw = raw.get("permissions", {})
        for rule_id, perm_dict in perms_raw.items():
            self._permissions[rule_id] = ObservationPermissions.from_dict(perm_dict)

        self._policies = raw.get("policies", [])
        self._audit_entries = raw.get("audit", [])

    def _save(self) -> None:
        """Persist current permissions, policies, and audit log to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        raw = {
            "permissions": {rid: p.to_dict() for rid, p in self._permissions.items()},
            "policies": self._policies,
            "audit": self._audit_entries,
        }
        self._path.write_text(json.dumps(raw, indent=2))

    # ------------------------------------------------------------------
    # Core access logic
    # ------------------------------------------------------------------

    def check_access(
        self,
        rule_id: str,
        agent_id: str,
        agent_role: str,
        agent_teams: list[str] | None = None,
    ) -> bool:
        """Return True if the agent is cleared to see *rule_id*."""
        agent_teams = agent_teams or []
        perm = self._permissions.get(rule_id)

        # No explicit permissions → treated as PUBLIC (default-open)
        if perm is None:
            return True

        return self._evaluate(perm, agent_id, agent_role, agent_teams)

    @staticmethod
    def _evaluate(
        perm: "ObservationPermissions",
        agent_id: str,
        agent_role: str,
        agent_teams: list[str],
    ) -> bool:
        level = perm.clearance

        # PUBLIC — always visible
        if level == ClearanceLevel.PUBLIC:
            return True

        # INTERNAL — visible if the agent has any valid role (non-empty string)
        if level == ClearanceLevel.INTERNAL:
            return bool(agent_role)

        # CONFIDENTIAL — role in allowed_roles OR team overlap
        if level == ClearanceLevel.CONFIDENTIAL:
            if agent_role in perm.allowed_roles:
                return True
            if set(agent_teams) & set(perm.allowed_teams):
                return True
            return False

        # RESTRICTED — agent_id must appear in allowed_agents
        if level == ClearanceLevel.RESTRICTED:
            return agent_id in perm.allowed_agents

        # SECRET — agent_id AND agent_role must both match
        if level == ClearanceLevel.SECRET:
            return agent_id in perm.allowed_agents and agent_role in perm.allowed_roles

        return False

    # ------------------------------------------------------------------
    # Permission management
    # ------------------------------------------------------------------

    def set_clearance(
        self,
        rule_id: str,
        clearance: ClearanceLevel,
        allowed_roles: list[str] | None = None,
        allowed_teams: list[str] | None = None,
        allowed_agents: list[str] | None = None,
        owner: str = "",
    ) -> ObservationPermissions:
        """Create or update the permissions record for *rule_id*."""
        perm = ObservationPermissions(
            rule_id=rule_id,
            clearance=clearance,
            allowed_roles=allowed_roles or [],
            allowed_agents=allowed_agents or [],
            allowed_teams=allowed_teams or [],
            owner=owner,
            set_at=datetime.now(timezone.utc).isoformat(),
        )
        self._permissions[rule_id] = perm

        # Auto-apply any matching clearance policies
        self._apply_matching_policies(rule_id)

        self._save()
        return perm

    def get_clearance(self, rule_id: str) -> ObservationPermissions | None:
        """Return the current permissions for *rule_id*, or None."""
        return self._permissions.get(rule_id)

    def remove_clearance(self, rule_id: str) -> bool:
        """Remove the permissions record for *rule_id*.  Returns True if it existed."""
        existed = rule_id in self._permissions
        self._permissions.pop(rule_id, None)
        if existed:
            self._save()
        return existed

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def bulk_set_clearance(
        self,
        rule_ids: list[str],
        clearance: ClearanceLevel,
        allowed_roles: list[str] | None = None,
        allowed_teams: list[str] | None = None,
        allowed_agents: list[str] | None = None,
        owner: str = "",
    ) -> list[ObservationPermissions]:
        """Apply the same clearance to multiple rules at once."""
        results: list[ObservationPermissions] = []
        for rid in rule_ids:
            perm = self.set_clearance(
                rule_id=rid,
                clearance=clearance,
                allowed_roles=allowed_roles,
                allowed_teams=allowed_teams,
                allowed_agents=allowed_agents,
                owner=owner,
            )
            results.append(perm)
        return results

    def inherit_clearance(
        self,
        source_rule_id: str,
        target_rule_id: str,
    ) -> ObservationPermissions | None:
        """Copy permissions from *source_rule_id* to *target_rule_id*."""
        source = self._permissions.get(source_rule_id)
        if source is None:
            return None
        return self.set_clearance(
            rule_id=target_rule_id,
            clearance=source.clearance,
            allowed_roles=list(source.allowed_roles),
            allowed_teams=list(source.allowed_teams),
            allowed_agents=list(source.allowed_agents),
            owner=source.owner,
        )

    # ------------------------------------------------------------------
    # Filter — the core observation-level gate
    # ------------------------------------------------------------------

    def filter_rules(
        self,
        rules: list[dict[str, Any]],
        ctx: AgentContext,
    ) -> list[dict[str, Any]]:
        """Return only the rules that *ctx* is cleared to see.

        Each rule dict must contain a ``rule_id`` key (or ``id``).
        """
        visible: list[dict[str, Any]] = []
        for rule in rules:
            rule_id = rule.get("rule_id") or rule.get("id", "")
            if self.check_access(
                rule_id=rule_id,
                agent_id=ctx.agent_id,
                agent_role=ctx.agent_role,
                agent_teams=ctx.agent_teams,
            ):
                visible.append(rule)
        return visible

    def get_accessible_rules(
        self,
        store_rules: list[dict[str, Any]],
        ctx: AgentContext,
    ) -> list[dict[str, Any]]:
        """Convenience alias — get ALL rules from store filtered by access."""
        return self.filter_rules(store_rules, ctx)

    # ------------------------------------------------------------------
    # Clearance policies (templates that auto-apply to matching rules)
    # ------------------------------------------------------------------

    def create_clearance_policy(
        self,
        name: str,
        rules_pattern: str,
        clearance: ClearanceLevel,
        allowed_roles: list[str] | None = None,
        allowed_teams: list[str] | None = None,
        allowed_agents: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register a clearance policy that auto-applies to new rules matching *rules_pattern*.

        *rules_pattern* is a substring or glob-like pattern matched against rule IDs.
        Policies are evaluated at `set_clearance` time — they never retroactively
        downgrade existing permissions.
        """
        policy = {
            "name": name,
            "rules_pattern": rules_pattern,
            "clearance": clearance.value,
            "allowed_roles": allowed_roles or [],
            "allowed_teams": allowed_teams or [],
            "allowed_agents": allowed_agents or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._policies.append(policy)
        self._save()
        return policy

    def _apply_matching_policies(self, rule_id: str) -> None:
        """Evaluate stored policies against *rule_id* and update if they match.

        Policies only upgrade visibility (never restrict it) — a policy cannot
        lower an existing permission's clearance level.
        """
        perm = self._permissions.get(rule_id)
        if perm is None:
            return

        for policy in self._policies:
            pattern = policy["rules_pattern"]
            # Simple substring / prefix match on rule_id
            if not self._rule_matches_pattern(rule_id, pattern):
                continue

            policy_level = ClearanceLevel(policy["clearance"])

            # A policy only widens access: it only takes effect if it would
            # make the rule *more* visible than it already is.
            if policy_level < perm.clearance:
                perm.clearance = policy_level
                perm.allowed_roles = list(set(perm.allowed_roles) | set(policy["allowed_roles"]))
                perm.allowed_teams = list(set(perm.allowed_teams) | set(policy["allowed_teams"]))
                perm.allowed_agents = list(set(perm.allowed_agents) | set(policy["allowed_agents"]))

    @staticmethod
    def _rule_matches_pattern(rule_id: str, pattern: str) -> bool:
        """Glob-aware pattern match.  ``*`` matches any sequence of characters."""
        import fnmatch
        return fnmatch.fnmatch(rule_id, pattern)

    def list_policies(self) -> list[dict[str, Any]]:
        """Return all registered clearance policies."""
        return list(self._policies)

    def remove_policy(self, name: str) -> bool:
        """Remove a clearance policy by name.  Returns True if one was removed."""
        before = len(self._policies)
        self._policies = [p for p in self._policies if p["name"] != name]
        removed = len(self._policies) < before
        if removed:
            self._save()
        return removed

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def audit_access(
        self,
        agent_id: str,
        rule_id: str,
        timestamp: str | None = None,
        granted: bool = True,
    ) -> None:
        """Log an access check for compliance / audit trail."""
        entry = {
            "agent_id": agent_id,
            "rule_id": rule_id,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "granted": granted,
        }
        self._audit_entries.append(entry)
        self._save()

    def get_access_report(self) -> dict[str, Any]:
        """Return a summary of who can see what.

        The report includes:
        - per-clearance-level rule counts
        - per-agent access summaries
        - audit log summary
        """
        clearance_counts: dict[str, int] = {}
        agent_access: dict[str, list[str]] = {}

        for rule_id, perm in self._permissions.items():
            level_name = perm.clearance.name
            clearance_counts[level_name] = clearance_counts.get(level_name, 0) + 1

            for agent in perm.allowed_agents:
                agent_access.setdefault(agent, []).append(rule_id)

        total_audit_entries = len(self._audit_entries)
        granted_audit = sum(1 for e in self._audit_entries if e.get("granted"))
        denied_audit = total_audit_entries - granted_audit

        return {
            "total_rules_with_permissions": len(self._permissions),
            "clearance_counts": clearance_counts,
            "agent_access": agent_access,
            "policies": len(self._policies),
            "audit": {
                "total_entries": total_audit_entries,
                "granted": granted_audit,
                "denied": denied_audit,
            },
        }

    def export_permissions(self) -> dict[str, Any]:
        """Export all permissions data as a plain dict (suitable for serialisation)."""
        return {
            "permissions": {rid: p.to_dict() for rid, p in self._permissions.items()},
            "policies": self._policies,
            "audit": self._audit_entries,
        }

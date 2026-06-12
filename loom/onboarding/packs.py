"""OnboardingPacks — instant onboarding packs for new team members.

Loom's answer to "a new hire's agent already knows the org's conventions."
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loom.engine.rule_store import RuleStore


# ── Role → domain mapping ─────────────────────────────────────────────

ROLE_DOMAIN_MAP: dict[str, tuple[list[str], int]] = {
    "backend-engineer": (["coding", "architecture", "testing", "security", "process"], 5),
    "frontend-dev": (["coding", "style", "testing", "documentation"], 5),
    "devops": (["process", "security", "architecture"], 5),
    "data-scientist": (["coding", "testing", "documentation"], 4),
    "support-agent": (["general", "process", "documentation"], 4),
    "tech-lead": (["architecture", "process", "security", "coding"], 6),
    "new-grad": (["coding", "style", "testing", "process", "general"], 3),
    "embedded-engineer": (["coding", "architecture", "testing", "security"], 5),
    "mobile-dev": (["coding", "style", "testing", "security"], 5),
    "fullstack-dev": (["coding", "architecture", "style", "testing", "documentation"], 5),
    "qa-engineer": (["testing", "process", "documentation"], 4),
    "security-engineer": (["security", "architecture", "coding", "process"], 6),
    "sre": (["architecture", "security", "process"], 6),
    "product-manager": (["general", "process", "documentation"], 4),
    "designer": (["style", "documentation", "general"], 4),
    "architect": (["architecture", "coding", "security", "process"], 7),
    "team-lead": (["process", "architecture", "general", "coding"], 6),
    "docs-writer": (["documentation", "style", "general", "process"], 4),
}

# Max rules per domain included in a pack
MAX_RULES_PER_DOMAIN = 8


@dataclass
class OnboardingPack:
    """A curated collection of rules for onboarding a new team member."""

    name: str
    role: str
    description: str
    domains: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    custom_notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "domains": self.domains,
            "rules": self.rules,
            "custom_notes": self.custom_notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OnboardingPack":
        return cls(
            name=d.get("name", ""),
            role=d.get("role", ""),
            description=d.get("description", ""),
            domains=d.get("domains", []),
            rules=d.get("rules", []),
            custom_notes=d.get("custom_notes", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


class OnboardingManager:
    """Create, update, and render onboarding packs backed by a RuleStore."""

    def __init__(self, store: RuleStore, store_dir: Path):
        self._store = store
        self._packs_dir = Path(store_dir) / "onboarding"
        self._packs: dict[str, OnboardingPack] = {}
        if self._packs_dir.exists():
            self._load()

    # ── helpers ────────────────────────────────────────────────────

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _pack_path(self, role: str) -> Path:
        return self._packs_dir / f"{role}.json"

    def _load(self):
        for fpath in sorted(self._packs_dir.glob("*.json")):
            try:
                data = json.loads(fpath.read_text())
                pack = OnboardingPack.from_dict(data)
                self._packs[pack.role] = pack
            except (json.JSONDecodeError, KeyError):
                continue

    def _save(self):
        self._packs_dir.mkdir(parents=True, exist_ok=True)
        for role, pack in self._packs.items():
            self._pack_path(role).write_text(
                json.dumps(pack.to_dict(), indent=2)
            )

    def _resolve_role(self, role: str) -> tuple[str, list[str], int]:
        """Return (role, domains, min_confidence) for a known role label.

        Falls back to a sane default if the role is unknown.
        """
        if role in ROLE_DOMAIN_MAP:
            domains, min_conf = ROLE_DOMAIN_MAP[role]
            return role, list(domains), min_conf
        # Unknown role: use broad domains at a moderate threshold
        return role, ["coding", "general", "process"], 5

    # ── CRUD ───────────────────────────────────────────────────────

    def create_pack(
        self,
        name: str,
        role: str,
        description: str = "",
        domain_filters: list[str] | None = None,
        custom_notes: str = "",
    ) -> OnboardingPack:
        """Auto-generate an onboarding pack by selecting top rules for the role.

        Args:
            name: Human-readable name, e.g. "Backend Engineer Onboarding".
            role: Role slug, e.g. "backend-engineer".
            description: Optional description for the pack.
            domain_filters: Override which domains to include (otherwise
                inferred from the role map).
            custom_notes: Additional human-written context.
        """
        _, role_domains, min_confidence = self._resolve_role(role)

        domains_to_use = domain_filters if domain_filters else role_domains
        now = self._now()

        rule_ids: list[str] = []
        for domain in domains_to_use:
            domain_rules = self._store.get_rules_by_domain(
                domain, min_confidence=min_confidence
            )
            # Sort by (confidence, times_confirmed) descending
            domain_rules.sort(
                key=lambda r: (r.confidence, r.times_confirmed), reverse=True
            )
            for r in domain_rules[:MAX_RULES_PER_DOMAIN]:
                rule_ids.append(r.id)

        pack = OnboardingPack(
            name=name,
            role=role,
            description=description,
            domains=domains_to_use,
            rules=rule_ids,
            custom_notes=custom_notes,
            created_at=now,
            updated_at=now,
        )
        self._packs[role] = pack
        self._save()
        return pack

    def get_pack(self, role: str) -> OnboardingPack | None:
        """Retrieve an onboarding pack by role slug."""
        return self._packs.get(role)

    def update_pack(
        self,
        role: str,
        rule_ids: list[str] | None = None,
        custom_notes: str | None = None,
    ) -> OnboardingPack | None:
        """Update an existing pack's rule list and/or custom notes."""
        pack = self._packs.get(role)
        if pack is None:
            return None
        if rule_ids is not None:
            pack.rules = rule_ids
        if custom_notes is not None:
            pack.custom_notes = custom_notes
        pack.updated_at = self._now()
        self._save()
        return pack

    def delete_pack(self, role: str) -> bool:
        """Remove an onboarding pack. Returns True if it existed."""
        if role in self._packs:
            del self._packs[role]
            fpath = self._pack_path(role)
            if fpath.exists():
                fpath.unlink()
            self._save()
            return True
        return False

    def list_packs(self) -> list[OnboardingPack]:
        """List all available onboarding packs, newest first."""
        return sorted(
            self._packs.values(),
            key=lambda p: p.updated_at,
            reverse=True,
        )

    # ── rendering ──────────────────────────────────────────────────

    def render_pack(self, role: str, fmt: str = "markdown") -> str:
        """Render an onboarding pack as markdown or JSON.

        Args:
            role: Role slug.
            fmt: "markdown" or "json".

        Returns:
            Rendered string, or empty string if the pack does not exist.
        """
        pack = self._packs.get(role)
        if pack is None:
            return ""
        if fmt == "json":
            return json.dumps(pack.to_dict(), indent=2)

        return self._render_markdown(pack)

    def _render_markdown(self, pack: OnboardingPack) -> str:
        lines: list[str] = []
        lines.append(f"# 🚀 Onboarding Pack: {pack.name}")
        lines.append("")
        if pack.description:
            lines.append(pack.description)
            lines.append("")
        lines.append(
            "Welcome to the team! Here's what our agents know about how we work."
        )
        lines.append("")
        lines.append("## Top Conventions")
        lines.append("")

        # Group rules by domain
        grouped: dict[str, list[dict]] = {}
        for rule_id in pack.rules:
            rule = self._store.get_rule(rule_id)
            if rule is None:
                continue
            domain = rule.domain.capitalize()
            grouped.setdefault(domain, []).append(
                {
                    "rule_type": rule.rule_type,
                    "rule": rule.rule,
                    "confidence": rule.confidence,
                    "times_confirmed": rule.times_confirmed,
                    "example": rule.example,
                }
            )

        for domain in sorted(grouped.keys()):
            lines.append(f"### {domain}")
            lines.append("")
            for item in grouped[domain]:
                lines.append(
                    f"- **{item['rule_type']}** "
                    f"({item['confidence']}/10): {item['rule']}"
                )
                if item["example"]:
                    lines.append(f"  Example: {item['example']}")
                lines.append("")

        # Custom notes
        if pack.custom_notes.strip():
            lines.append("## Team Notes")
            lines.append("")
            lines.append(pack.custom_notes.strip())
            lines.append("")

        # Build a simple decision log from high-confidence architecture/process rules
        lines.append("## Key Decisions You Should Know")
        lines.append("")
        decision_rules_found = 0
        for rule_id in pack.rules:
            rule = self._store.get_rule(rule_id)
            if rule is None:
                continue
            if rule.domain in ("architecture", "process") and rule.confidence >= 7:
                decision_rules_found += 1
                lines.append(
                    f"- **{rule.rule_type}**: {rule.rule}"
                )
                if rule.example:
                    lines.append(f"  {rule.example}")
        if decision_rules_found == 0:
            lines.append(
                "_No key decisions captured yet. "
                "This section populates as the team records architectural decisions._"
            )
        lines.append("")

        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._packs)

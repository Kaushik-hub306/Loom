"""SuccessionCapture — knowledge retention when team members depart.

Loom's answer to "when a staff engineer leaves, the decisions and lessons
they learned remain."
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loom.engine.rule_store import RuleStore

# ── Knowledge item categories ─────────────────────────────────────────

CATEGORY_LABELS: dict[str, str] = {
    "tribal_knowledge": "Tribal Knowledge",
    "gotcha": "Gotchas",
    "design_decision": "Design Decisions",
    "process": "Processes",
    "contact": "Contacts & People",
    "tool": "Tools & Configurations",
    "convention": "Conventions",
}

IMPORTANCE_BANDS = [
    (9, "## 🔴 Critical Knowledge (Must Know)"),
    (6, "## 🟡 Important Context"),
    (1, "## 🟢 Nice to Know"),
]


@dataclass
class KnowledgeItem:
    """A single captured piece of knowledge from a departing team member."""

    id: str
    domain: str
    title: str
    detail: str
    importance: int
    category: str
    related_rule_ids: list[str] = field(default_factory=list)
    successor_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "title": self.title,
            "detail": self.detail,
            "importance": self.importance,
            "category": self.category,
            "related_rule_ids": self.related_rule_ids,
            "successor_notes": self.successor_notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeItem":
        return cls(
            id=d.get("id", ""),
            domain=d.get("domain", ""),
            title=d.get("title", ""),
            detail=d.get("detail", ""),
            importance=d.get("importance", 5),
            category=d.get("category", ""),
            related_rule_ids=d.get("related_rule_ids", []),
            successor_notes=d.get("successor_notes", ""),
        )


@dataclass
class SuccessionSession:
    """A succession capture session for a departing team member."""

    departing_member: str
    role: str
    date: str
    project: str
    knowledge_items: list[KnowledgeItem] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "departing_member": self.departing_member,
            "role": self.role,
            "date": self.date,
            "project": self.project,
            "knowledge_items": [k.to_dict() for k in self.knowledge_items],
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SuccessionSession":
        items = [
            KnowledgeItem.from_dict(ki)
            for ki in d.get("knowledge_items", [])
        ]
        return cls(
            departing_member=d.get("departing_member", ""),
            role=d.get("role", ""),
            date=d.get("date", ""),
            project=d.get("project", ""),
            knowledge_items=items,
            tags=d.get("tags", []),
        )


class SuccessionManager:
    """Manage succession knowledge capture sessions backed by a RuleStore."""

    def __init__(self, store: RuleStore, store_dir: Path):
        self._store = store
        self._sessions_dir = Path(store_dir) / "succession"
        self._sessions: dict[str, SuccessionSession] = {}
        self._active_session: SuccessionSession | None = None
        if self._sessions_dir.exists():
            self._load()

    # ── helpers ────────────────────────────────────────────────────

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _session_path(self, member_id: str) -> Path:
        return self._sessions_dir / f"{member_id}.json"

    def _member_id(self, name: str) -> str:
        """Derive a safe filesystem slug from a member name."""
        slug = name.lower().replace(" ", "-")
        # Keep only alphanumeric and hyphens
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        return slug.strip("-") or "unknown"

    def _make_item_id(self, domain: str, title: str) -> str:
        short = str(uuid.uuid4())[:8]
        slug = "".join(
            c for c in title.lower().replace(" ", "-") if c.isalnum() or c == "-"
        )[:40]
        return f"{domain}::{slug}::{short}"

    def _load(self):
        for fpath in sorted(self._sessions_dir.glob("*.json")):
            try:
                data = json.loads(fpath.read_text())
                session = SuccessionSession.from_dict(data)
                self._sessions[fpath.stem] = session
            except (json.JSONDecodeError, KeyError):
                continue

    def _save(self):
        from loom.storage.jsonio import atomic_write_json

        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        for member_id, session in self._sessions.items():
            atomic_write_json(self._session_path(member_id), session.to_dict())

    # ── session management ─────────────────────────────────────────

    def start_session(
        self,
        departing_member: str,
        role: str,
        project: str = "",
        tags: list[str] | None = None,
    ) -> SuccessionSession:
        """Begin a succession capture session.

        Args:
            departing_member: Name or handle of the departing person.
            role: Their role, e.g. "Staff Engineer, API Team".
            project: Primary project or area they worked on.
            tags: Optional tags for categorization.
        """
        member_id = self._member_id(departing_member)

        # Resume existing session if one is already in memory for this person
        if member_id in self._sessions:
            self._active_session = self._sessions[member_id]
            return self._active_session

        session = SuccessionSession(
            departing_member=departing_member,
            role=role,
            date=self._now(),
            project=project,
            tags=tags or [],
        )
        self._active_session = session
        return session

    def capture(
        self,
        title: str,
        detail: str,
        importance: int = 5,
        category: str = "tribal_knowledge",
        domain: str = "general",
        related_rule_ids: list[str] | None = None,
        successor_notes: str = "",
    ) -> KnowledgeItem | None:
        """Capture a knowledge item in the active session.

        Returns None if no session is active.
        """
        if self._active_session is None:
            return None

        item_id = self._make_item_id(domain, title)
        item = KnowledgeItem(
            id=item_id,
            domain=domain,
            title=title,
            detail=detail,
            importance=max(1, min(10, importance)),
            category=category,
            related_rule_ids=related_rule_ids or [],
            successor_notes=successor_notes,
        )
        self._active_session.knowledge_items.append(item)
        return item

    def import_from_rules(self, departing_member: str) -> list[KnowledgeItem]:
        """Auto-extract: pull ALL rules this person authored/confirmed.

        Searches the RuleStore for rules whose sources reference the
        departing member and flags them as succession-critical.

        Returns the list of imported KnowledgeItems.
        """
        member_id = self._member_id(departing_member)

        # Ensure we have an active session
        if self._active_session is None or self._member_id(
            self._active_session.departing_member
        ) != member_id:
            # Try to find an existing session, or start a new one
            if member_id in self._sessions:
                self._active_session = self._sessions[member_id]
            else:
                self._active_session = SuccessionSession(
                    departing_member=departing_member,
                    role="",
                    date=self._now(),
                    project="",
                )

        imported: list[KnowledgeItem] = []
        name_lower = departing_member.lower()

        for rule in self._store.get_active_rules(min_confidence=1):
            # Check if any source mentions this person
            match = False
            for src in rule.sources:
                if name_lower in src.lower():
                    match = True
                    break
            if not match:
                # Also check source_type for short-form attribution
                if name_lower in rule.source_type.lower():
                    match = True

            if not match:
                continue

            # Skip if a similar item already exists in this session
            already_captured = any(
                rid == rule.id
                for ki in self._active_session.knowledge_items
                for rid in ki.related_rule_ids
            )
            if already_captured:
                continue

            importance = min(10, rule.confidence)
            detail = (
                f"Rule '{rule.rule}' (confidence: {rule.confidence}/10, "
                f"confirmed {rule.times_confirmed} times)."
            )
            if rule.example:
                detail += f"\nExample: {rule.example}"

            item = KnowledgeItem(
                id=self._make_item_id(rule.domain, rule.rule_type),
                domain=rule.domain,
                title=f"Convention: {rule.rule_type}",
                detail=detail,
                importance=importance,
                category="convention",
                related_rule_ids=[rule.id],
                successor_notes=(
                    f"This rule was reinforced {rule.times_confirmed} times "
                    f"by {departing_member}."
                ),
            )
            self._active_session.knowledge_items.append(item)
            imported.append(item)

        return imported

    def finalize_session(self) -> SuccessionSession | None:
        """Compile the active session into a saved succession document.

        Returns the finalized session, or None if no session is active.
        """
        if self._active_session is None:
            return None

        member_id = self._member_id(self._active_session.departing_member)
        self._sessions[member_id] = self._active_session
        self._save()

        finalized = self._active_session
        self._active_session = None
        return finalized

    # ── queries ────────────────────────────────────────────────────

    def list_sessions(self) -> list[SuccessionSession]:
        """List all past succession captures, newest first."""
        return sorted(
            self._sessions.values(),
            key=lambda s: s.date,
            reverse=True,
        )

    def get_session(self, member_slug: str) -> SuccessionSession | None:
        """Retrieve a specific session by member slug or name."""
        member_id = self._member_id(member_slug)
        return self._sessions.get(member_id)

    # ── rendering ──────────────────────────────────────────────────

    def render_succession_doc(
        self, member_slug: str, fmt: str = "markdown"
    ) -> str:
        """Render a succession document as markdown or JSON.

        Args:
            member_slug: Member name or handle to look up.
            fmt: "markdown" or "json".
        """
        session = self.get_session(member_slug)
        if session is None:
            return ""
        if fmt == "json":
            return json.dumps(session.to_dict(), indent=2)

        return self._render_markdown(session)

    def _render_markdown(self, session: SuccessionSession) -> str:
        lines: list[str] = []

        role_str = f" ({session.role})" if session.role else ""
        lines.append(
            f"# 📋 Succession Knowledge: "
            f"{session.departing_member}{role_str}"
        )
        # Parse ISO date for friendlier display
        try:
            dt = datetime.fromisoformat(session.date)
            date_display = dt.strftime("%B %d, %Y")
        except (ValueError, TypeError):
            date_display = session.date
        lines.append(f"Captured: {date_display}")
        if session.project:
            lines.append(f"Project: {session.project}")
        lines.append("")

        # Sort items by importance descending, then by category
        items = sorted(
            session.knowledge_items,
            key=lambda k: (-k.importance, k.category),
        )

        # Group by importance bands for tiered display
        current_band = None
        for band_min, band_header in IMPORTANCE_BANDS:
            band_items = [
                i for i in items if i.importance >= band_min
            ]
            # Skip bands that overlap with a higher band we've already rendered
            if current_band is not None:
                band_items = [
                    i for i in band_items if i.importance < current_band
                ]
            if not band_items:
                continue

            lines.append(band_header)
            lines.append("")

            # Sub-group by category within the band
            by_category: dict[str, list[KnowledgeItem]] = {}
            for item in band_items:
                cat_label = CATEGORY_LABELS.get(
                    item.category, item.category.replace("_", " ").title()
                )
                by_category.setdefault(cat_label, []).append(item)

            for cat_label, cat_items in sorted(by_category.items()):
                lines.append(f"### {cat_label}")
                lines.append("")
                for item in cat_items:
                    lines.append(
                        f"- **{item.title}** (importance: {item.importance}/10)"
                    )
                    # Indent multi-line detail
                    for detail_line in item.detail.split("\n"):
                        lines.append(f"  {detail_line.strip()}")
                    lines.append("")

            current_band = band_min

        # Linked rules section — collect unique rule IDs
        linked_ids: list[str] = []
        seen = set()
        for item in session.knowledge_items:
            for rid in item.related_rule_ids:
                if rid not in seen:
                    linked_ids.append(rid)
                    seen.add(rid)

        if linked_ids:
            lines.append("## Linked Rules")
            lines.append("")
            lines.append(
                f"These Loom rules were authored or reinforced by "
                f"{session.departing_member}:"
            )
            lines.append("")
            for rid in linked_ids:
                rule = self._store.get_rule(rid)
                if rule:
                    lines.append(
                        f"- {rule.id} "
                        f"(confidence: {rule.confidence}/10, "
                        f"confirmed {rule.times_confirmed}x)"
                    )
            lines.append("")

        return "\n".join(lines)

    # ── conversion ─────────────────────────────────────────────────

    def transfer_to_onboarding(
        self,
        member_slug: str,
        successor_role: str,
    ) -> dict | None:
        """Convert captured succession knowledge into an onboarding payload.

        Returns a dict suitable for passing to OnboardingManager.create_pack(),
        or None if no session is found.
        """
        session = self.get_session(member_slug)
        if session is None:
            return None

        # Collect unique related rule IDs across all items
        rule_ids: list[str] = []
        seen = set()
        for item in session.knowledge_items:
            for rid in item.related_rule_ids:
                if rid not in seen:
                    rule_ids.append(rid)
                    seen.add(rid)

        # Build a description from the session metadata
        description = (
            f"Onboarding pack for {successor_role}, "
            f"created from succession knowledge captured from "
            f"{session.departing_member}"
        )
        if session.project:
            description += f" ({session.project})"

        # Collect successor notes into custom_notes
        notes_parts = []
        for item in session.knowledge_items:
            if item.successor_notes.strip():
                notes_parts.append(
                    f"### {item.title}\n{item.successor_notes}"
                )
        custom_notes = "\n\n".join(notes_parts) if notes_parts else ""

        return {
            "name": f"{successor_role.title()} Onboarding (via {session.departing_member})",
            "role": successor_role,
            "description": description,
            "rule_ids": rule_ids,
            "custom_notes": custom_notes,
        }

    def __len__(self) -> int:
        return len(self._sessions)

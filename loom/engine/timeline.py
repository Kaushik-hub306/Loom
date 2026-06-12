"""Timeline — auditable, append-only history of organizational learning."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path


@dataclass
class TimelineEntry:
    """A single entry in the organizational learning timeline."""

    timestamp: str  # ISO format
    action: str  # learned, taught, reflected, confirmed, violated, archived, onboarded, succeeded
    domain: str
    rule_id: str
    rule_text: str
    agent: str  # which agent/user triggered this
    project: str  # which project
    decision_context: str  # the reasoning/why
    confidence: int
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "domain": self.domain,
            "rule_id": self.rule_id,
            "rule_text": self.rule_text,
            "agent": self.agent,
            "project": self.project,
            "decision_context": self.decision_context,
            "confidence": self.confidence,
            "sources": self.sources,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TimelineEntry":
        return cls(
            timestamp=d.get("timestamp", ""),
            action=d.get("action", ""),
            domain=d.get("domain", ""),
            rule_id=d.get("rule_id", ""),
            rule_text=d.get("rule_text", d.get("rule", "")),
            agent=d.get("agent", ""),
            project=d.get("project", ""),
            decision_context=d.get("decision_context", ""),
            confidence=d.get("confidence", 5),
            sources=d.get("sources", []),
        )


class Timeline:
    """Append-only, queryable history of all organizational learning events.

    Backed by a JSONL file at ``{store_dir}/timeline.jsonl`` — each line
    is one TimelineEntry serialised as JSON.  Writes are append-only so
    the file doubles as an audit log.
    """

    VALID_ACTIONS = frozenset({
        "learned", "taught", "reflected", "confirmed", "violated",
        "archived", "onboarded", "succeeded", "amplified", "retained",
        "observed",
    })

    def __init__(self, store_dir: Path):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.store_dir / "timeline.jsonl"

    # ── helpers ─────────────────────────────────────────────────────

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _parse_ts(self, ts: str) -> datetime | None:
        try:
            return datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            return None

    # ── core: record ────────────────────────────────────────────────

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
        """Append a new entry to the timeline.

        Args:
            action: One of the valid action strings (learned, taught, …).
            rule_id: The rule identifier this entry relates to.
            rule_text: Human-readable text of the rule.
            agent: Who / what triggered this action.
            project: Which project this occurred in.
            decision_context: The reasoning or context for the decision.
            domain: Optional domain label.
            confidence: Confidence score at the time of the event.
            sources: Optional list of source references.
        """
        if action not in self.VALID_ACTIONS:
            raise ValueError(
                f"Invalid action '{action}'. Must be one of: "
                f"{', '.join(sorted(self.VALID_ACTIONS))}"
            )

        entry = TimelineEntry(
            timestamp=self._now(),
            action=action,
            domain=domain,
            rule_id=rule_id,
            rule_text=rule_text,
            agent=agent,
            project=project,
            decision_context=decision_context,
            confidence=confidence,
            sources=sources or [],
        )

        with open(self._path, "a") as fh:
            fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

        return entry

    # ── queries ─────────────────────────────────────────────────────

    def _iter_entries(self) -> list[TimelineEntry]:
        """Read all entries from the JSONL file."""
        entries: list[TimelineEntry] = []
        if not self._path.exists():
            return entries
        for line in self._path.read_text().strip().splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                entries.append(TimelineEntry.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                continue
        return entries

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
        """Query the timeline with optional filters.

        All parameters are optional — omit a filter to include everything.
        Results are returned in chronological order (oldest first).
        """
        from_dt = self._parse_ts(date_from) if date_from else None
        to_dt = self._parse_ts(date_to) if date_to else None

        results: list[TimelineEntry] = []
        for entry in self._iter_entries():
            if domain and entry.domain != domain:
                continue
            if project and entry.project.lower() != project.lower():
                continue
            if agent and entry.agent.lower() != agent.lower():
                continue
            if action and entry.action != action:
                continue

            ts = self._parse_ts(entry.timestamp)
            if from_dt and ts and ts < from_dt:
                continue
            if to_dt and ts and ts > to_dt:
                continue

            results.append(entry)

        if limit:
            results = results[:limit]
        return results

    def get_decision_trail(self, rule_id: str) -> list[TimelineEntry]:
        """Return the full history of a specific rule from creation to now."""
        entries = self._iter_entries()
        return [e for e in entries if e.rule_id == rule_id]

    def get_org_history(self, days: int = 7) -> list[TimelineEntry]:
        """Return everything that happened in the last N days across the org."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        results: list[TimelineEntry] = []
        for entry in self._iter_entries():
            ts = self._parse_ts(entry.timestamp)
            if ts and ts >= since:
                results.append(entry)
        return results

    def search_decisions(self, query: str) -> list[TimelineEntry]:
        """Full-text search across decision_context and rule_text fields."""
        q = query.lower()
        results: list[TimelineEntry] = []
        for entry in self._iter_entries():
            if q in entry.decision_context.lower() or q in entry.rule_text.lower():
                results.append(entry)
        return results

    # ── export ──────────────────────────────────────────────────────

    def export_timeline(
        self,
        format: str = "markdown",
        **filters,
    ) -> str:
        """Export timeline entries as markdown, JSON, or compact.

        Args:
            format: One of ``"markdown"``, ``"json"``, or ``"compact"``.
            **filters: Forwarded to :meth:`query` (domain, project, etc.).
        """
        entries = self.query(**filters)

        if format == "json":
            return json.dumps([e.to_dict() for e in entries], indent=2, ensure_ascii=False)

        if format == "compact":
            return "\n".join(
                f"[{e.timestamp[:10]}] {e.action.upper():12s} [{e.domain}] {e.rule_text[:80]}"
                for e in entries
            )

        # markdown (default)
        return self._format_markdown(entries)

    def _format_markdown(self, entries: list[TimelineEntry]) -> str:
        """Format entries as a human-readable Markdown timeline."""

        if not entries:
            # When there are no entries, show the current date range anyway
            now = datetime.now(timezone.utc)
            return (
                f"## Timeline: {now.strftime('%B %-d')}, {now.year}\n\n"
                f"_No entries for this period._"
            )

        # Group by date
        by_date: dict[str, list[TimelineEntry]] = {}
        for e in entries:
            date_key = e.timestamp[:10]  # YYYY-MM-DD
            by_date.setdefault(date_key, []).append(e)

        sorted_dates = sorted(by_date.keys())

        # Build a friendly date range header
        first = sorted_dates[0]
        last = sorted_dates[-1]
        first_dt = self._parse_ts(first + "T00:00:00+00:00")
        last_dt = self._parse_ts(last + "T00:00:00+00:00")

        if len(sorted_dates) == 1 and first_dt:
            header_date = first_dt.strftime("%B %-d, %Y")
        elif first_dt and last_dt:
            if first_dt.year == last_dt.year:
                if first_dt.month == last_dt.month:
                    header_date = (
                        f"{first_dt.strftime('%B %-d')}–{last_dt.day}, {first_dt.year}"
                    )
                else:
                    header_date = (
                        f"{first_dt.strftime('%B %-d')} – "
                        f"{last_dt.strftime('%B %-d')}, {first_dt.year}"
                    )
            else:
                header_date = (
                    f"{first_dt.strftime('%B %-d, %Y')} – "
                    f"{last_dt.strftime('%B %-d, %Y')}"
                )
        else:
            header_date = f"{first} to {last}"

        lines = [f"## Timeline: {header_date}", ""]

        for date_key in sorted_dates:
            dt = self._parse_ts(date_key + "T00:00:00+00:00")
            if dt:
                day_label = dt.strftime("%B %-d")
            else:
                day_label = date_key

            lines.append(f"### {day_label}")

            for entry in sorted(by_date[date_key], key=lambda e: e.timestamp, reverse=True):
                time_part = ""
                if len(entry.timestamp) >= 16:
                    time_part = entry.timestamp[11:16]  # HH:MM

                lines.append(
                    f"- {time_part} [{entry.domain}] {entry.action.capitalize()}: "
                    f'"{entry.rule_text}" (confidence: {entry.confidence}/10)'
                )
                lines.append(f"  Agent: {entry.agent} | Project: {entry.project}")
                # Include decision context when available
                if entry.decision_context:
                    lines.append(f"  Context: {entry.decision_context}")
                lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    # ── summaries ───────────────────────────────────────────────────

    def get_summary(self, period: str = "daily") -> dict:
        """Summarise learning activity for the given period.

        Args:
            period: One of ``"daily"``, ``"weekly"``, or ``"monthly"``.
        """
        now = datetime.now(timezone.utc)
        if period == "daily":
            since = now - timedelta(days=1)
        elif period == "weekly":
            since = now - timedelta(weeks=1)
        elif period == "monthly":
            since = now - timedelta(days=30)
        else:
            raise ValueError(f"Unknown period '{period}'. Use daily, weekly, or monthly.")

        entries = [e for e in self._iter_entries()
                   if self._parse_ts(e.timestamp) and self._parse_ts(e.timestamp) >= since]

        action_counts: dict[str, int] = {}
        domain_counts: dict[str, int] = {}
        project_counts: dict[str, int] = {}
        agent_counts: dict[str, int] = {}

        for e in entries:
            action_counts[e.action] = action_counts.get(e.action, 0) + 1
            if e.domain:
                domain_counts[e.domain] = domain_counts.get(e.domain, 0) + 1
            if e.project:
                project_counts[e.project] = project_counts.get(e.project, 0) + 1
            if e.agent:
                agent_counts[e.agent] = agent_counts.get(e.agent, 0) + 1

        return {
            "period": period,
            "total_entries": len(entries),
            "by_action": action_counts,
            "by_domain": domain_counts,
            "by_project": project_counts,
            "by_agent": agent_counts,
            "avg_confidence": (
                sum(e.confidence for e in entries) / len(entries)
                if entries else 0.0
            ),
        }

    def get_milestones(self) -> list[dict]:
        """Return significant events in the timeline.

        Includes: first rule learned, every hundredth rule, confidence
        rating milestones (first rule reaching confidence 10, etc.).
        """
        entries = self._iter_entries()
        if not entries:
            return []

        milestones: list[dict] = []

        # Track rule creation order by first appearance in timeline
        first_seen: dict[str, TimelineEntry] = {}
        rule_learned_count = 0
        confidence_milestones: set[int] = set()

        for entry in entries:
            if entry.action == "learned" and entry.rule_id not in first_seen:
                first_seen[entry.rule_id] = entry
                rule_learned_count += 1

        # First rule learned
        sorted_rules = sorted(first_seen.values(), key=lambda e: e.timestamp)
        if sorted_rules:
            e = sorted_rules[0]
            milestones.append({
                "event": "First rule learned",
                "timestamp": e.timestamp,
                "rule_id": e.rule_id,
                "rule_text": e.rule_text,
                "agent": e.agent,
            })

        # Every 100th rule
        for i, e in enumerate(sorted_rules):
            count = i + 1
            if count % 100 == 0:
                milestones.append({
                    "event": f"Rule #{count} learned",
                    "timestamp": e.timestamp,
                    "rule_id": e.rule_id,
                    "rule_text": e.rule_text,
                    "agent": e.agent,
                })

        # Confidence milestones (first rule to hit 8, 9, 10)
        for threshold in (8, 9, 10):
            for entry in entries:
                if entry.confidence >= threshold and threshold not in confidence_milestones:
                    confidence_milestones.add(threshold)
                    milestones.append({
                        "event": f"First rule reached confidence {threshold}/10",
                        "timestamp": entry.timestamp,
                        "rule_id": entry.rule_id,
                        "rule_text": entry.rule_text,
                        "confidence": entry.confidence,
                    })

        # Sort milestones by timestamp
        milestones.sort(key=lambda m: m["timestamp"])
        return milestones

    # ── counts ──────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._iter_entries())

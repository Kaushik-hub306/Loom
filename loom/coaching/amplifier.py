"""CoachingAmplifier — amplify top performers' judgment into reusable training.

Glen's vision: "coaching amplification" — when a top performer explains WHY a
rule matters, that context becomes reusable training for every other agent.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# ── data types ────────────────────────────────────────────────────────────────


@dataclass
class AmplifiedRule:
    """A rule that has been amplified with coaching context."""

    id: str
    rule_id: str
    coach: str
    coach_role: str
    original_rule: str
    amplification: str
    amplified_at: str
    reach: int = 0
    tags: list[str] = field(default_factory=list)
    effectiveness: float = 0.0

    # ── derived / metadata fields ─────────────────────────────────────────

    cross_project_source: str = ""  # project name this was cross-amplified from
    merged_from: list[str] = field(default_factory=list)  # ids of merged amplifications
    confirmations_before: int = 0
    confirmations_after: int = 0
    violations_before: int = 0
    violations_after: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "coach": self.coach,
            "coach_role": self.coach_role,
            "original_rule": self.original_rule,
            "amplification": self.amplification,
            "amplified_at": self.amplified_at,
            "reach": self.reach,
            "tags": self.tags,
            "effectiveness": self.effectiveness,
            "cross_project_source": self.cross_project_source,
            "merged_from": self.merged_from,
            "confirmations_before": self.confirmations_before,
            "confirmations_after": self.confirmations_after,
            "violations_before": self.violations_before,
            "violations_after": self.violations_after,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AmplifiedRule":
        return cls(
            id=d["id"],
            rule_id=d.get("rule_id", ""),
            coach=d.get("coach", ""),
            coach_role=d.get("coach_role", ""),
            original_rule=d.get("original_rule", ""),
            amplification=d.get("amplification", ""),
            amplified_at=d.get("amplified_at", ""),
            reach=d.get("reach", 0),
            tags=d.get("tags", []),
            effectiveness=d.get("effectiveness", 0.0),
            cross_project_source=d.get("cross_project_source", ""),
            merged_from=d.get("merged_from", []),
            confirmations_before=d.get("confirmations_before", 0),
            confirmations_after=d.get("confirmations_after", 0),
            violations_before=d.get("violations_before", 0),
            violations_after=d.get("violations_after", 0),
        )

    def render(self) -> str:
        """Render this amplified rule as a coaching brief for agent onboarding."""
        lines = []
        lines.append(f"## 📢 Coaching: \"{self.original_rule}\"")
        lines.append("")
        lines.append(f"**Coach:** {self.coach} ({self.coach_role})")
        pct = round(self.effectiveness * 100)
        lines.append(f"**Effectiveness:** {pct}% adoption rate")
        lines.append("")

        # The amplification text is natural language — coach's elaboration
        lines.append(self.amplification)
        lines.append("")

        if self.tags:
            lines.append("### Applies To")
            lines.append(", ".join(self.tags))

        if self.cross_project_source:
            lines.append("")
            lines.append(f"*Cross-amplified from: {self.cross_project_source}*")

        return "\n".join(lines)


# ── CoachingAmplifier ─────────────────────────────────────────────────────────


class CoachingAmplifier:
    """Amplify top performers' coaching into reusable training for every agent.

    Each amplification captures not just a rule but the coach's *judgment*:
    - Why the rule matters
    - Real examples (good and bad)
    - Common anti-patterns to avoid
    """

    def __init__(self, store_dir: str, rule_store=None):
        self._rule_store = rule_store
        self._store_dir = Path(store_dir)
        self._coaching_dir = self._store_dir / "coaching"
        self._path = self._coaching_dir / "amplifications.json"
        self._amplifications: dict[str, AmplifiedRule] = {}
        if self._path.exists():
            self._load()

    # ── persistence ─────────────────────────────────────────────────────────

    def _load(self):
        try:
            data = json.loads(self._path.read_text())
            for d in data.get("amplifications", []):
                rule = AmplifiedRule.from_dict(d)
                self._amplifications[rule.id] = rule
        except (json.JSONDecodeError, KeyError):
            self._amplifications = {}

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"amplifications": [r.to_dict() for r in self._amplifications.values()]}
        self._path.write_text(json.dumps(data, indent=2))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _generate_id(self) -> str:
        return uuid.uuid4().hex[:12]

    # ── coaching CRUD ────────────────────────────────────────────────────────

    def amplify(
        self,
        rule_id: str,
        coach: str,
        coach_role: str,
        amplification_text: str,
        target_roles: list[str] | None = None,
    ) -> AmplifiedRule:
        """Amplify a rule with coaching context from an experienced team member.

        If the same coach has already amplified this rule, merges the new
        amplification into the existing one instead of creating a duplicate.
        """
        target_roles = target_roles or []

        # Source rule text — prefer the rule store, fall back to rule_id
        original_rule = rule_id
        if self._rule_store:
            stored = self._rule_store.get_rule(rule_id)
            if stored:
                original_rule = stored.rule

        # Smart dedup: if this coach has already amplified this rule, merge
        existing = self._find_existing(rule_id, coach)
        if existing:
            return self._merge_amplification(
                existing, amplification_text, target_roles
            )

        amplified = AmplifiedRule(
            id=self._generate_id(),
            rule_id=rule_id,
            coach=coach,
            coach_role=coach_role,
            original_rule=original_rule,
            amplification=amplification_text,
            amplified_at=self._now(),
            reach=1,
            tags=list(target_roles),
        )

        # Boost the underlying rule's confidence when amplified
        if self._rule_store:
            self._rule_store.promote_rule(rule_id)

        self._amplifications[amplified.id] = amplified
        self._save()
        return amplified

    def _find_existing(self, rule_id: str, coach: str) -> AmplifiedRule | None:
        """Check if this coach already amplified the same rule."""
        for amp in self._amplifications.values():
            if amp.rule_id == rule_id and amp.coach == coach:
                return amp
        return None

    def _merge_amplification(
        self,
        existing: AmplifiedRule,
        new_text: str,
        target_roles: list[str],
    ) -> AmplifiedRule:
        """Merge a new amplification into an existing one for the same coach+rule."""
        existing.amplification = (
            existing.amplification + "\n\n─── Updated " + self._now() + " ───\n\n" + new_text
        )
        for role in target_roles:
            if role not in existing.tags:
                existing.tags.append(role)
        existing.reach += 1
        existing.amplified_at = self._now()
        self._save()
        return existing

    def get_amplification(self, amplification_id: str) -> AmplifiedRule | None:
        return self._amplifications.get(amplification_id)

    def delete_amplification(self, amplification_id: str) -> bool:
        if amplification_id in self._amplifications:
            del self._amplifications[amplification_id]
            self._save()
            return True
        return False

    # ── role-based coaching ──────────────────────────────────────────────────

    def get_coaching_for_role(self, role: str) -> list[AmplifiedRule]:
        """Return all amplified rules relevant to a specific role."""
        results = []
        for amp in self._amplifications.values():
            if role in amp.tags:
                results.append(amp)
        results.sort(key=lambda r: (r.effectiveness, r.reach), reverse=True)
        return results

    def broadcast(self, rule_id: str, target_roles: list[str]) -> AmplifiedRule | None:
        """Mark a rule for auto-inclusion in onboarding packs for the target roles.

        Finds the amplified rule by its source rule_id and adds the target roles
        to its tags. If the rule hasn't been amplified yet, returns None.
        """
        # Find the amplification for this rule_id — prefer the most recent
        candidates = [
            amp for amp in self._amplifications.values() if amp.rule_id == rule_id
        ]
        if not candidates:
            return None

        # Use the most recent amplification
        amp = max(candidates, key=lambda a: a.amplified_at)
        for role in target_roles:
            if role not in amp.tags:
                amp.tags.append(role)
        self._save()
        return amp

    # ── coach stats ─────────────────────────────────────────────────────────

    def get_coach_impact(self, coach: str) -> dict:
        """Stats on how many rules a coach has amplified and their effectiveness."""
        amplifications = [
            amp for amp in self._amplifications.values() if amp.coach == coach
        ]
        if not amplifications:
            return {"coach": coach, "amplifications": 0, "total_reach": 0, "avg_effectiveness": 0.0}

        return {
            "coach": coach,
            "amplifications": len(amplifications),
            "total_reach": sum(amp.reach for amp in amplifications),
            "avg_effectiveness": sum(amp.effectiveness for amp in amplifications)
            / len(amplifications),
            "coach_role": amplifications[0].coach_role,
        }

    def list_coaches(self) -> list[dict]:
        """Who has contributed coaching, with summary stats."""
        coach_map: dict[str, dict] = {}
        for amp in self._amplifications.values():
            if amp.coach not in coach_map:
                coach_map[amp.coach] = {
                    "coach": amp.coach,
                    "coach_role": amp.coach_role,
                    "amplification_count": 0,
                    "total_reach": 0,
                    "avg_effectiveness": 0.0,
                }
            c = coach_map[amp.coach]
            c["amplification_count"] += 1
            c["total_reach"] += amp.reach

        for coach_name, stats in coach_map.items():
            coach_amps = [
                a for a in self._amplifications.values() if a.coach == coach_name
            ]
            stats["avg_effectiveness"] = (
                sum(a.effectiveness for a in coach_amps) / len(coach_amps)
                if coach_amps
                else 0.0
            )

        coaches = list(coach_map.values())
        coaches.sort(key=lambda c: c["avg_effectiveness"], reverse=True)
        return coaches

    # ── effectiveness ────────────────────────────────────────────────────────

    def measure_effectiveness(self, rule_id: str) -> AmplifiedRule | None:
        """Compare confirmation rates before vs after amplification.

        Calculates effectiveness by comparing the ratio of confirmations to
        total events (confirmations + violations) before and after amplification.
        An effectiveness of 1.0 means perfect adoption after coaching.
        """
        candidates = [
            amp for amp in self._amplifications.values() if amp.rule_id == rule_id
        ]
        if not candidates:
            return None

        amp = max(candidates, key=lambda a: a.amplified_at)

        if self._rule_store:
            stored = self._rule_store.get_rule(rule_id)
            if stored:
                # The store tracks confirmations and violations for the rule.
                # We split them into before/after based on amplification time.
                # For now, treat all events as "after" since the rule was amplified.
                amp.confirmations_after = stored.times_confirmed
                amp.violations_after = stored.times_violated

        total_before = amp.confirmations_before + amp.violations_before
        total_after = amp.confirmations_after + amp.violations_after

        before_rate = (
            amp.confirmations_before / total_before if total_before > 0 else 0.5
        )
        after_rate = (
            amp.confirmations_after / total_after if total_after > 0 else 1.0
        )

        # Effectiveness is the improvement: how much better the after rate is
        # Clamped between 0 and 1
        amp.effectiveness = max(0.0, min(1.0, after_rate - before_rate + 0.5))

        self._save()
        return amp

    def get_top_amplified(self, limit: int = 10) -> list[AmplifiedRule]:
        """Return the most effective amplified rules."""
        sorted_amps = sorted(
            self._amplifications.values(),
            key=lambda a: (a.effectiveness, a.reach),
            reverse=True,
        )
        return sorted_amps[:limit]

    # ── cross-project amplification ─────────────────────────────────────────

    def cross_project_amplify(
        self,
        rule_id: str,
        from_project: str,
        to_project: str,
    ) -> AmplifiedRule | None:
        """Take a coaching rule from one project and propagate it to another.

        Returns the amplification tagged for the target project context.
        """
        amp = None
        for candidate in self._amplifications.values():
            if candidate.rule_id == rule_id:
                amp = candidate
                break
        if not amp:
            return None

        # Create a cross-project variant — same coaching, new project context
        cross = AmplifiedRule(
            id=self._generate_id(),
            rule_id=amp.rule_id,
            coach=amp.coach,
            coach_role=amp.coach_role,
            original_rule=amp.original_rule,
            amplification=f"*From {from_project}:*\n\n{amp.amplification}",
            amplified_at=self._now(),
            reach=1,
            tags=[to_project] + amp.tags,
            cross_project_source=from_project,
            merged_from=[amp.id],
        )
        self._amplifications[cross.id] = cross
        self._save()
        return cross

    def amplify_from_succession(
        self,
        succession_doc: str,
        coach: str,
        coach_role: str = "",
    ) -> list[AmplifiedRule]:
        """Take knowledge captured during succession and amplify critical items.

        The succession document is expected to contain multiple knowledge entries.
        Each paragraph or section is treated as a separate amplification.
        Returns the list of created amplifications.
        """
        created = []

        # Split on double newlines to get individual knowledge entries
        entries = [e.strip() for e in succession_doc.split("\n\n") if e.strip()]

        for entry in entries:
            # Use the first line as the rule text, rest as amplification
            lines = entry.split("\n", 1)
            rule_text = lines[0].strip()
            amp_text = lines[1].strip() if len(lines) > 1 else entry.strip()

            amplification_id = self._generate_id()
            rule_id = f"succession::{self._generate_id()}"

            amplified = AmplifiedRule(
                id=amplification_id,
                rule_id=rule_id,
                coach=coach,
                coach_role=coach_role or "departing team member",
                original_rule=rule_text,
                amplification=amp_text,
                amplified_at=self._now(),
                reach=1,
                tags=["succession", "critical-knowledge"],
            )
            self._amplifications[amplified.id] = amplified
            created.append(amplified)

        if created:
            self._save()
        return created

    # ── render ──────────────────────────────────────────────────────────────

    def render_brief(self, amplification_id: str) -> str | None:
        """Render an amplified rule as a coaching brief."""
        amp = self._amplifications.get(amplification_id)
        if not amp:
            return None
        return amp.render()

    def render_onboarding_pack(self, role: str) -> str:
        """Render all coaching for a role as an onboarding pack."""
        coaching = self.get_coaching_for_role(role)
        if not coaching:
            return f"## Coaching for {role}\n\nNo coaching available yet."

        parts = [f"# Coaching Onboarding Pack — {role}", ""]
        for amp in coaching:
            parts.append(amp.render())
            parts.append("\n---\n")
        return "\n".join(parts)

    # ── bulk ─────────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._amplifications)

    def get_all(self) -> list[AmplifiedRule]:
        return list(self._amplifications.values())

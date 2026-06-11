"""Rule store — persistent storage for learned conventions."""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class RuleStatus(str, Enum):
    ACTIVE = "active"
    HARD_RULE = "hard_rule"
    ARCHIVED = "archived"


@dataclass
class Domain:
    name: str
    description: str
    keywords: list[str] = field(default_factory=list)
    extractors: list[str] = field(default_factory=list)


@dataclass
class Rule:
    id: str
    domain: str
    rule_type: str
    rule: str
    example: str = ""
    confidence: float = 5.0
    status: str = "active"
    source_traces: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        return cls(**d)


class RuleStore:
    """Persistent store for rules in .loom/rules.json."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.rules_path = self.data_dir / "rules.json"
        self.rules: dict[str, Rule] = {}
        self._load()

    def _load(self):
        if self.rules_path.exists():
            try:
                data = json.loads(self.rules_path.read_text())
                for rule_dict in data.get("rules", []):
                    rule = Rule.from_dict(rule_dict)
                    self.rules[rule.id] = rule
            except (json.JSONDecodeError, KeyError):
                self.rules = {}

    def _save(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {"rules": [r.to_dict() for r in self.rules.values()]}
        self.rules_path.write_text(json.dumps(payload, indent=2))

    def get_rules(self, domain: str | None = None, status: str | None = None) -> list[Rule]:
        results = list(self.rules.values())
        if domain:
            results = [r for r in results if r.domain == domain]
        if status:
            results = [r for r in results if r.status == status]
        return results

    def search_rules(self, query: str, domain: str | None = None) -> list[Rule]:
        query_lower = query.lower()
        results = []
        for rule in self.rules.values():
            if domain and rule.domain != domain:
                continue
            if rule.status == "archived":
                continue
            score = 0
            if query_lower in rule.rule.lower():
                score += 3
            if query_lower in rule.rule_type.lower():
                score += 2
            if query_lower in rule.example.lower():
                score += 1
            if query_lower in " ".join(rule.source_traces).lower():
                score += 1
            if score > 0:
                results.append((score, rule))
        results.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in results]

    def find_similar_rule(self, domain: str, rule_type: str, rule_text: str) -> "Rule | None":
        """Find an existing rule that matches by type and text similarity."""
        text_lower = rule_text.lower()
        best = None
        best_score = 0
        for rule in self.rules.values():
            if rule.domain != domain or rule.rule_type != rule_type:
                continue
            if rule.status == "archived":
                continue
            overlap = len(set(text_lower.split()) & set(rule.rule.lower().split()))
            total = len(set(text_lower.split()) | set(rule.rule.lower().split()))
            if total == 0:
                continue
            jaccard = overlap / total
            if jaccard > 0.4 and jaccard > best_score:
                best_score = jaccard
                best = rule
        return best

    def add_rule(self, rule: Rule):
        now = datetime.now(timezone.utc).isoformat()
        rule.updated_at = now
        if not rule.created_at:
            rule.created_at = now
        self.rules[rule.id] = rule
        self._save()

    def update_rule(self, rule_id: str, **kwargs):
        if rule_id in self.rules:
            rule = self.rules[rule_id]
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            rule.updated_at = datetime.now(timezone.utc).isoformat()
            self._save()

    def archive_rule(self, rule_id: str):
        self.update_rule(rule_id, status="archived")

    def get_stats(self) -> dict:
        rules = list(self.rules.values())
        by_status: dict[str, int] = {}
        by_domain: dict[str, dict] = {}
        conf_dist: dict[str, int] = {"10": 0, "7-9": 0, "4-6": 0, "1-3": 0}
        recent_cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        recent_archived = 0

        for rule in rules:
            by_status[rule.status] = by_status.get(rule.status, 0) + 1

            dom = by_domain.setdefault(rule.domain, {
                "total": 0, "active": 0, "hard_rules": 0,
                "confidence_sum": 0.0, "active_confidence_count": 0,
            })
            dom["total"] += 1
            if rule.status in ("active", "hard_rule"):
                dom["active"] += 1
                dom["confidence_sum"] += rule.confidence
                dom["active_confidence_count"] += 1
            if rule.status == "hard_rule":
                dom["hard_rules"] += 1

            c = rule.confidence
            if c >= 10:
                conf_dist["10"] += 1
            elif c >= 7:
                conf_dist["7-9"] += 1
            elif c >= 4:
                conf_dist["4-6"] += 1
            else:
                conf_dist["1-3"] += 1

            if rule.status == "archived" and rule.updated_at:
                try:
                    updated = datetime.fromisoformat(rule.updated_at)
                    if updated >= recent_cutoff:
                        recent_archived += 1
                except ValueError:
                    pass

        by_domain_out = {}
        for name, dom in by_domain.items():
            count = dom["active_confidence_count"]
            avg = dom["confidence_sum"] / count if count > 0 else 0.0
            by_domain_out[name] = {
                "total": dom["total"],
                "active": dom["active"],
                "hard_rules": dom["hard_rules"],
                "avg_confidence": round(avg, 1),
            }

        return {
            "total_rules": len(rules),
            "by_status": by_status,
            "by_domain": by_domain_out,
            "confidence_distribution": conf_dist,
            "recently_archived": recent_archived,
        }

    def regenerate_conventions(self, path: Path):
        active = [r for r in self.rules.values() if r.status != "archived"]
        active.sort(key=lambda r: (-r.confidence, r.domain, r.rule_type))

        lines = ["<!-- Loom active conventions —— auto-generated -->\n"]
        if not active:
            lines.append("<!-- No active conventions yet. Use store_outcome to build memory. -->\n")
        else:
            current_domain = None
            for rule in active:
                if rule.domain != current_domain:
                    current_domain = rule.domain
                    lines.append(f"\n## {current_domain}\n")
                badge = "HARD" if rule.status == "hard_rule" else f"{rule.confidence:.0f}/10"
                lines.append(f"- **[{badge}]** {rule.rule}")
                if rule.example:
                    lines.append(f"  - _Example:_ `{rule.example}`")
                lines.append("")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines))

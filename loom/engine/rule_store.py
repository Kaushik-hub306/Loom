"""RuleStore — persistent, searchable store of learned conventions."""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Rule:
    """A single learned convention rule."""

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

    def to_dict(self) -> dict:
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
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        # Backward compat: migrate old "source_urls" key to "sources"
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
        )


class RuleStore:
    """Persistent store of convention rules backed by a JSON file."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.rules: dict[str, Rule] = {}
        if self.path.exists():
            self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text())
            for rule_dict in data.get("rules", []):
                rule = Rule.from_dict(rule_dict)
                self.rules[rule.id] = rule
        except (json.JSONDecodeError, KeyError):
            self.rules = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"rules": [r.to_dict() for r in self.rules.values()]}
        self.path.write_text(json.dumps(data, indent=2))

    def _make_id(self, domain: str, rule_type: str, rule_text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", rule_text.lower().strip())[:60].strip("-")
        return f"{domain}::{rule_type}::{slug}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── CRUD ──────────────────────────────────────────────────────

    def get_rule(self, rule_id: str) -> Rule | None:
        return self.rules.get(rule_id)

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
        rule_id = self._make_id(domain, rule_type, rule)
        now = self._now()

        # Build sources list: new `sources` param takes priority,
        # `source_url` is a deprecated kwarg for backward compat.
        source_list = list(sources) if sources else []
        if source_url and source_url not in source_list:
            source_list.append(source_url)

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
            self._save()
            return existing

        new_rule = Rule(
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
        )
        self.rules[new_rule.id] = new_rule
        self._save()
        return new_rule

    def promote_rule(self, rule_id: str) -> Rule | None:
        rule = self.rules.get(rule_id)
        if rule:
            rule.confidence = min(10, rule.confidence + 1)
            rule.times_confirmed += 1
            rule.updated_at = self._now()
            self._save()
        return rule

    def demote_rule(self, rule_id: str) -> Rule | None:
        rule = self.rules.get(rule_id)
        if rule:
            rule.confidence = max(1, rule.confidence - 1)
            rule.times_violated += 1
            rule.updated_at = self._now()
            self._save()
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        if rule_id in self.rules:
            del self.rules[rule_id]
            self._save()
            return True
        return False

    # ── queries ───────────────────────────────────────────────────

    def get_active_rules(self, min_confidence: int = 1) -> list[Rule]:
        return [r for r in self.rules.values() if r.confidence >= min_confidence]

    def get_rules_by_domain(self, domain: str, min_confidence: int = 1) -> list[Rule]:
        return [
            r
            for r in self.rules.values()
            if r.domain == domain and r.confidence >= min_confidence
        ]

    def search_rules(
        self,
        query: str,
        domain: str | None = None,
        min_confidence: int = 1,
        limit: int | None = None,
        rule_type: str | None = None,
    ) -> list[Rule]:
        query_lower = query.lower()
        results = []
        for rule in self.rules.values():
            if rule.confidence < min_confidence:
                continue
            if domain and rule.domain != domain:
                continue
            if rule_type and rule.rule_type != rule_type:
                continue
            # Search across all text fields including sources and source_type
            searchable = (
                rule.rule.lower() + " "
                + rule.rule_type.lower() + " "
                + rule.id.lower() + " "
                + rule.domain.lower() + " "
                + " ".join(rule.sources).lower() + " "
                + rule.source_type.lower()
            )
            if query_lower in searchable:
                results.append(rule)

        results.sort(key=lambda r: (r.confidence, r.times_confirmed), reverse=True)
        if limit:
            results = results[:limit]
        return results

    def get_all_domain_stats(self) -> dict[str, dict]:
        stats: dict[str, dict] = {}
        for rule in self.rules.values():
            if rule.domain not in stats:
                stats[rule.domain] = {"total": 0, "by_type": {}, "avg_confidence": 0.0}
            s = stats[rule.domain]
            s["total"] += 1
            s["by_type"][rule.rule_type] = s["by_type"].get(rule.rule_type, 0) + 1
        for domain, s in stats.items():
            domain_rules = [r for r in self.rules.values() if r.domain == domain]
            s["avg_confidence"] = sum(r.confidence for r in domain_rules) / max(len(domain_rules), 1)
        return stats

    def get_domain_stats(self, domain: str | None = None) -> dict:
        rules = (
            self.get_rules_by_domain(domain)
            if domain
            else list(self.rules.values())
        )
        total = len(rules)
        by_type: dict[str, int] = {}
        for r in rules:
            by_type[r.rule_type] = by_type.get(r.rule_type, 0) + 1

        return {
            "total": total,
            "by_type": by_type,
            "avg_confidence": sum(r.confidence for r in rules) / max(total, 1),
        }

    def __len__(self) -> int:
        return len(self.rules)

"""RuleStore — persistent, searchable store of learned conventions."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loom.storage.jsonio import atomic_write_json, load_entries, load_json_dict


def _clamp_confidence(value: int) -> int:
    try:
        return max(1, min(10, int(value)))
    except (TypeError, ValueError):
        return 5


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
        if not isinstance(sources, list):
            sources = []
        return cls(
            id=d["id"],
            domain=d["domain"],
            rule_type=d["rule_type"],
            rule=d.get("rule", d.get("pattern", "")),
            example=d.get("example", "") or "",
            confidence=_clamp_confidence(d.get("confidence", 5)),
            times_confirmed=int(d.get("times_confirmed", 0) or 0),
            times_violated=int(d.get("times_violated", 0) or 0),
            sources=[str(s) for s in sources],
            source_type=d.get("source_type", "") or "",
            created_at=d.get("created_at", "") or "",
            updated_at=d.get("updated_at", "") or "",
        )


def _normalize_rule_text(text: str) -> str:
    """Normalize rule text for equality comparison (dedup)."""
    return re.sub(r"\s+", " ", text.strip().lower())


class RuleStore:
    """Persistent store of convention rules backed by a JSON file.

    Storage safety:

    * Loads skip individually malformed entries instead of discarding the
      whole store, and corrupt files are quarantined — a bad load can
      never lead to a save that wipes prior data.
    * Saves are atomic (temp file + fsync + rename) under an advisory
      file lock, so crashes and concurrent writers cannot corrupt the
      store.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.rules: dict[str, Rule] = {}
        self._loaded_sig: tuple | None = None
        if self.path.exists():
            self._load()

    def _load(self):
        data = load_json_dict(self.path)
        self.rules = {}
        for rule in load_entries(
            data.get("rules"), Rule.from_dict, source_name=self.path.name
        ):
            self.rules[rule.id] = rule
        self._loaded_sig = self._file_signature()

    def _file_signature(self) -> tuple | None:
        """Cheap change-detection signature (atomic writes change the inode)."""
        try:
            st = self.path.stat()
            return (st.st_mtime_ns, st.st_ino, st.st_size)
        except OSError:
            return None

    def reload_if_stale(self) -> bool:
        """Re-read the file if it changed on disk since the last load.

        Returns True when a reload happened. Lets a long-lived server
        cache one RuleStore instance while staying consistent with
        other writers (e.g. a second Loom process on the same project).
        """
        if self._file_signature() != self._loaded_sig:
            if self.path.exists():
                self._load()
            else:
                self.rules = {}
                self._loaded_sig = None
            return True
        return False

    def _save(self):
        data = {"rules": [r.to_dict() for r in self.rules.values()]}
        atomic_write_json(self.path, data)
        self._loaded_sig = self._file_signature()

    def _make_id(self, domain: str, rule_type: str, rule_text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", rule_text.lower().strip())[:60].strip("-")
        if not slug:
            # Rule text with no alphanumeric content — fall back to a hash
            # so distinct rules can't collide on an empty slug.
            slug = hashlib.sha1(
                _normalize_rule_text(rule_text).encode("utf-8")
            ).hexdigest()[:12]
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

        existing = self.rules.get(rule_id)
        if existing is not None and _normalize_rule_text(
            existing.rule
        ) != _normalize_rule_text(rule):
            # Slug collision: two DIFFERENT rules truncated to the same
            # slug. Disambiguate deterministically with a content hash so
            # the new rule is stored instead of silently merged away.
            digest = hashlib.sha1(
                _normalize_rule_text(rule).encode("utf-8")
            ).hexdigest()[:8]
            rule_id = f"{rule_id}-{digest}"
            existing = self.rules.get(rule_id)

        if existing is not None:
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
            confidence=_clamp_confidence(confidence),
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
        conf_sums: dict[str, int] = {}
        for rule in self.rules.values():
            if rule.domain not in stats:
                stats[rule.domain] = {"total": 0, "by_type": {}, "avg_confidence": 0.0}
                conf_sums[rule.domain] = 0
            s = stats[rule.domain]
            s["total"] += 1
            s["by_type"][rule.rule_type] = s["by_type"].get(rule.rule_type, 0) + 1
            conf_sums[rule.domain] += rule.confidence
        for domain, s in stats.items():
            s["avg_confidence"] = conf_sums[domain] / max(s["total"], 1)
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

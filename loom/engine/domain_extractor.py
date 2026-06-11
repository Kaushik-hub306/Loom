"""DomainExtractor — extracts convention rules from feedback using domain configs."""

import re
from pathlib import Path

import yaml


class DomainConfig:
    """Configuration for a single domain."""

    def __init__(self, name: str, keywords: list[str], rule_types: list[str]):
        self.name = name
        self.keywords = keywords
        self.rule_types = rule_types

    @classmethod
    def from_yaml(cls, path: Path) -> "DomainConfig":
        data = yaml.safe_load(path.read_text()) or {}
        return cls(
            name=data.get("name", path.stem),
            keywords=data.get("keywords", []),
            rule_types=data.get("rule_types", []),
        )


class DomainExtractor:
    """Extracts rules from feedback text, matching against domain configs."""

    KEYWORD_PATTERNS = {
        "type_safety": [
            "type hint", "type annotation", "typing", "mypy", "return type",
            "type safety", "type-check",
        ],
        "testing": [
            "test", "testing", "unit test", "integration test", "pytest",
            "coverage", "test case",
        ],
        "error_handling": [
            "error handling", "try-except", "try/except", "exception",
            "error", "result type", "unwrap", "abort",
        ],
        "naming": [
            "camelcase", "snake_case", "pascalcase", "naming convention",
            "rename", "variable name",
        ],
        "architecture": [
            "separation of concerns", "module", "service layer",
            "util", "architecture", "design pattern",
        ],
        "documentation": [
            "docstring", "comment", "readme", "document", "docs",
        ],
        "formatting": [
            "tab", "space", "indent", "formatting", "prettier", "black",
            "formatter",
        ],
        "security": [
            "security", "vulnerability", "injection", "xss", "csrf",
            "authentication", "authorization",
        ],
    }

    def __init__(self, domains_dir: Path | None = None):
        self.domains: dict[str, DomainConfig] = {}
        if domains_dir and domains_dir.exists():
            for yml_file in domains_dir.glob("*.yml"):
                config = DomainConfig.from_yaml(yml_file)
                self.domains[config.name] = config

    def detect_domain(self, feedback: str) -> str | None:
        """Detect which domain this feedback belongs to."""
        feedback_lower = feedback.lower()
        for name, config in self.domains.items():
            for kw in config.keywords:
                if kw.lower() in feedback_lower:
                    return name
        return None

    def extract_rules(
        self, feedback: str, domain: str = "coding"
    ) -> list[dict]:
        """Extract convention rules from feedback text for a domain."""
        feedback_lower = feedback.lower()
        rules = []

        for rule_type, keywords in self.KEYWORD_PATTERNS.items():
            for kw in keywords:
                if kw in feedback_lower:
                    # Try to extract a meaningful rule sentence
                    rule_text = self._extract_rule_sentence(feedback, kw)
                    rules.append({
                        "rule_type": rule_type,
                        "rule": rule_text,
                        "example": "",
                        "confidence": 5,
                    })
                    break

        return rules

    def _extract_rule_sentence(self, feedback: str, keyword: str) -> str:
        """Extract the best sentence containing the keyword."""
        sentences = re.split(r"[.!?]+", feedback)
        for s in sentences:
            if keyword.lower() in s.lower():
                return s.strip()[:200]
        return feedback.strip()[:200]

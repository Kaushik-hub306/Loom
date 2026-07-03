"""DomainExtractor — extracts convention rules from feedback using domain configs."""

import re
from pathlib import Path

import yaml

# Fallback patterns used when a domain config has no patterns block.
# Each key is a rule_type, each value is a list of trigger keywords.
_FALLBACK_PATTERNS: dict[str, list[str]] = {
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
    "process": [
        "commit message", "git workflow", "branch", "merge", "PR",
        "pull request", "review", "CI/CD", "deploy", "release",
    ],
    "style": [
        "style", "format", "indent", "spacing", "line length",
        "whitespace", "quote", "trailing comma", "brace",
    ],
    "preference": [
        "prefer", "always", "never", "should", "must", "convention",
        "best practice", "guideline", "rule of thumb",
    ],
}


class DomainConfig:
    """Configuration for a single domain."""

    def __init__(
        self,
        name: str,
        keywords: list[str] | None = None,
        rule_types: list[str] | None = None,
        patterns: dict[str, list[str]] | None = None,
        description: str = "",
        use_llm: bool = False,
    ):
        self.name = name
        self.keywords = keywords or []
        self.rule_types = rule_types or []
        self.patterns = patterns or {}
        self.description = description
        self.use_llm = use_llm

    @classmethod
    def from_yaml(cls, path: Path) -> "DomainConfig":
        data = yaml.safe_load(path.read_text()) or {}
        return cls(
            name=data.get("name", path.stem),
            keywords=data.get("keywords", []),
            rule_types=data.get("rule_types", []),
            patterns=data.get("patterns", {}),
            description=data.get("description", ""),
            use_llm=data.get("use_llm", False),
        )


class DomainExtractor:
    """Extracts rules from feedback text, matching against domain configs.

    Patterns are loaded from domain YAML configs.  When a domain config
    has no ``patterns`` block, the built-in ``_FALLBACK_PATTERNS`` are used
    as a sensible default.
    """

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

    def _get_patterns(self, domain: str) -> dict[str, list[str]]:
        """Return the extraction patterns for *domain*.

        Uses domain-config patterns when available, otherwise the built-in
        fallback.  This guarantees that extraction always works even when a
        domain YAML omits the ``patterns`` block.
        """
        config = self.domains.get(domain)
        if config and config.patterns:
            return config.patterns
        return _FALLBACK_PATTERNS

    def extract_rules(
        self, feedback: str, domain: str = "coding"
    ) -> list[dict]:
        """Extract convention rules from feedback text for a domain.

        Uses the domain's configured patterns (or the built-in fallback)
        to match keywords against *feedback* and produce structured rules.
        """
        feedback_lower = feedback.lower()
        patterns = self._get_patterns(domain)
        rules = []

        for rule_type, keywords in patterns.items():
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
                    break  # one rule per rule_type

        return rules

    def _extract_rule_sentence(self, feedback: str, keyword: str) -> str:
        """Extract the best sentence containing the keyword."""
        sentences = re.split(r"[.!?]+", feedback)
        for s in sentences:
            if keyword.lower() in s.lower():
                return s.strip()[:200]
        return feedback.strip()[:200]

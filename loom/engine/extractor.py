"""Domain-aware convention extraction from outcome feedback."""

import re
from dataclasses import dataclass, field


@dataclass
class Convention:
    type: str
    rule: str
    example: str = ""


@dataclass
class ExtractionResult:
    domain: str
    conventions: list[Convention] = field(default_factory=list)
    raw_feedback: str = ""


# Domain-specific extraction patterns
DOMAIN_PATTERNS: dict[str, dict[str, list[str]]] = {
    "coding": {
        "type-annotation": [
            r"type\s*(hint|annotation|signature)",
            r"missing\s*(type|return\s*type)",
            r"add\s*type",
            r":\s*\w+\s*(is|should|must)\s*be\s*typed",
            r"mypy|pyright|pyre",
        ],
        "naming": [
            r"(re)?name\s*(it|the|this|variable|function|class|method)",
            r"naming\s*convention",
            r"(snake|Pascal|camel)\s*case",
            r"should\s*be\s*(called|named)",
            r"rename\s*\w+\s*(to|as)",
        ],
        "test-location": [
            r"(add|write|include|missing)\s*test",
            r"(test|spec)\s*(file|coverage|for)",
            r"untested",
            r"needs?\s*(a\s*)?test",
            r"test\s*suite",
        ],
        "error-handling": [
            r"(error|exception)\s*(handling|handling|case)",
            r"try\s*(/|except|catch)",
            r"handle\s*(the|errors?|exceptions?)",
            r"(missing|no)\s*(error|exception)\s*(handling|check)",
            r"(raise|throw)s?\s*\w*[Ee]rror",
        ],
        "import-style": [
            r"import\s*(order|style|convention)",
            r"unused\s*import",
            r"wildcard\s*import",
            r"from\s+\w+\s+import\s*\*",
            r"isort|ruff\s*import",
        ],
        "formatting": [
            r"(formatting|format|style|indent)",
            r"black|prettier|autopep8|yapf",
            r"too\s*(long|many)\s*line",
            r"(line|column)\s*(length|width)",
            r"(trailing|leading)\s*whitespace",
        ],
        "architecture": [
            r"(architecture|design|pattern|structure)",
            r"(separate|split|break)\s*(out|up|into)",
            r"single\s*responsibility",
            r"(circular|cyclic)\s*dependenc",
            r"too\s*(big|large|complex|many)\s*(file|module|class|function)",
        ],
        "documentation": [
            r"(doc|document|comment)\s*(string|this|the|missing)",
            r"(add|write|include)\s*(doc|comment)",
            r"(docstring|README|CHANGELOG)",
            r"(explain|describe)\s*(what|why|how)",
            r"undocumented",
        ],
    },
    "support": {
        "escalation": [
            r"escalat",
            r"(bump|elevate)\s*(to|up)",
            r"next\s*(tier|level)",
        ],
        "resolution": [
            r"resolv",
            r"(fix|solve|close)\s*(ticket|issue)",
            r"root\s*cause",
        ],
        "communication": [
            r"(reply|respond|message|update)\s*(the|customer|user)",
            r"acknowledge?ment",
            r"follow[-\s]?up",
        ],
        "documentation": [
            r"(doc|document|wiki|KB|knowledge)",
            r"runbook",
            r"(record|log|note)\s*(this|the|solution)",
        ],
    },
    "sales": {
        "follow-up": [
            r"follow[-\s]?up",
            r"(check|circle)\s*back",
            r"remind",
        ],
        "qualification": [
            r"qualif",
            r"BANT|MEDDIC",
            r"budget|authority|need|timeline",
        ],
        "objection": [
            r"objection",
            r"concern",
            r"push[-\s]?back",
        ],
        "closing": [
            r"clos(e|ing)",
            r"commit(ment)?",
            r"sign(ed|ing)",
            r"won|converted",
        ],
    },
}

RULE_TEMPLATES: dict[str, dict[str, str]] = {
    "coding": {
        "type-annotation": "Always add type hints to function signatures and public APIs",
        "naming": "Follow {} naming conventions consistently",
        "test-location": "Add tests alongside changed code — never merge untested changes",
        "error-handling": "Handle errors explicitly — never swallow exceptions silently",
        "import-style": "Organize imports: stdlib, third-party, local — remove unused imports",
        "formatting": "Run auto-formatter before committing — consistent style matters",
        "architecture": "Keep modules focused — split large files into single-responsibility units",
        "documentation": "Document public APIs with docstrings — explain why, not what",
    },
    "support": {
        "escalation": "Escalate issues that can't be resolved within SLA to next tier",
        "resolution": "Always identify and document the root cause before closing",
        "communication": "Acknowledge customer messages within 5 minutes, even if just to say you're looking",
        "documentation": "Create or update a runbook entry for every novel issue resolved",
    },
    "sales": {
        "follow-up": "Follow up within 24 hours of every call — no lead goes cold",
        "qualification": "Use BANT framework to qualify every lead before advancing stage",
        "objection": "Document every objection and address it directly — don't deflect",
        "closing": "Always define clear next steps before ending a call — no open-ended closes",
    },
}


class DomainExtractor:
    """Extracts conventions from outcome feedback text using domain-aware patterns."""

    def extract(self, feedback: str, domain: str) -> ExtractionResult:
        patterns = DOMAIN_PATTERNS.get(domain, {})
        templates = RULE_TEMPLATES.get(domain, {})
        conventions: list[Convention] = []
        seen_types: set[str] = set()

        for conv_type, pat_list in patterns.items():
            for pat in pat_list:
                match = re.search(pat, feedback, re.IGNORECASE)
                if match:
                    if conv_type not in seen_types:
                        template = templates.get(conv_type, f"Follow best practices for {conv_type}")
                        rule_text = template
                        if "{}" in rule_text and match.groups():
                            rule_text = rule_text.format(match.group(1))
                        conventions.append(Convention(
                            type=conv_type,
                            rule=rule_text,
                            example=self._extract_example(feedback, match),
                        ))
                        seen_types.add(conv_type)
                    break

        # Fallback: if no patterns matched, extract generic conventions
        if not conventions:
            conventions.extend(self._generic_extract(feedback))

        return ExtractionResult(
            domain=domain,
            conventions=conventions,
            raw_feedback=feedback,
        )

    def _extract_example(self, feedback: str, match: re.Match) -> str:
        """Try to extract a short example from the feedback around the match."""
        start = max(0, match.start() - 50)
        end = min(len(feedback), match.end() + 80)
        snippet = feedback[start:end].strip()
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        return snippet

    def _generic_extract(self, feedback: str) -> list[Convention]:
        """Extract generic conventions when no domain patterns match."""
        conventions: list[Convention] = []
        sentences = re.split(r"[.;!]\s+", feedback)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 10:
                continue
            for keyword, conv_type in [
                (r"\b(?:should|must|always|never|don'?t|avoid)\b", "other"),
                (r"\b(?:fix|change|update|add|remove|replace)\b", "other"),
                (r"\b(?:use|prefer|switch to)\b", "other"),
            ]:
                if re.search(keyword, sentence, re.IGNORECASE):
                    conventions.append(Convention(
                        type=conv_type,
                        rule=sentence[:200],
                    ))
                    break
            if len(conventions) >= 3:
                break
        return conventions

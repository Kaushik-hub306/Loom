"""Abstract base class for LLM providers."""

from __future__ import annotations

import json
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass

#: Default cap on a single extraction API call, in seconds. One slow or
#: hanging provider call must never stall the MCP server indefinitely.
DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass
class ExtractedRule:
    """A single rule extracted by an LLM provider."""

    rule_type: str
    rule: str
    example: str = ""
    confidence: int = 5


class BaseLLMProvider(ABC):
    """Pluggable LLM provider for convention extraction.

    Each provider wraps a vendor SDK (Anthropic, OpenAI-compatible, Gemini)
    and exposes a single async ``extract()`` method with identical semantics.
    """

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        **kwargs,
    ):
        self.api_key = api_key
        self.model = model or self.default_model
        self.timeout = timeout
        self.extra_config = kwargs

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model ID for this provider."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name ('anthropic', 'deepseek', 'gemini')."""
        ...

    @abstractmethod
    async def extract(
        self,
        text: str,
        domain: str = "general",
        domain_description: str = "",
        rule_types: list[str] | None = None,
        max_input_chars: int = 8000,
    ) -> list[ExtractedRule]:
        """Extract convention rules from *text*.

        Args:
            text: The observation text to extract rules from.
            domain: Domain name (e.g. 'coding', 'security').
            domain_description: One-line description of the domain.
            rule_types: Known rule types for this domain.
            max_input_chars: Truncate text to this length before sending.

        Returns:
            List of ExtractedRule objects (empty if nothing found).
        """
        ...

    def _log_failure(self, error: BaseException) -> None:
        """Report an extraction failure to stderr (never stdout — this may
        run inside an MCP stdio server) so failures are diagnosable instead
        of perfectly silent."""
        print(
            f"[loom] {self.provider_name} extraction failed "
            f"({type(error).__name__}: {error}). Falling back to keyword "
            f"extraction for this batch.",
            file=sys.stderr,
        )

    def _build_prompt(
        self,
        text: str,
        domain: str,
        domain_description: str,
        rule_types: list[str] | None,
        max_input_chars: int = 8000,
    ) -> str:
        """Build the extraction prompt — shared across providers."""
        types_str = ", ".join(rule_types) if rule_types else "any (free-form)"
        desc = domain_description or f"{domain} conventions"

        return f"""\
You are a convention extraction engine. Given a text describing a coding \
experience (feedback, observation, reflection, teaching, or review), extract \
clear, reusable convention rules.

## Domain context

Domain: {domain}
Description: {desc}
Known rule types: {types_str}

## Instructions

1. Extract 1-5 specific, actionable convention rules from the input.
2. Each rule should be a concise statement of what to do (or not do).
3. The rule_type should match one of the known types above IF relevant. \
If none fits, use a descriptive free-form type (e.g., "preference", "git_workflow").
4. If the input contains an explicit lesson (someone stating "the rule is X"), \
extract it verbatim.
5. If the input describes a pattern observed across work, abstract it into \
a general rule.
6. Assign confidence 1-10 based on how clearly the rule is supported:
   - 1-3: vague mention, unclear
   - 4-6: suggested or implied
   - 7-8: explicitly stated
   - 9-10: explicitly stated AND reinforced by examples or outcomes
7. If no conventions can be extracted, return an empty list.

## Output format

Respond with ONLY a JSON object (no prose, no markdown fences) shaped exactly:
{{"rules": [{{"rule_type": "string", "rule": "string", "example": "string", "confidence": 1}}]}}

## Input text

{text[:max_input_chars]}"""

    @staticmethod
    def _parse_rules_json(raw: str) -> list[ExtractedRule]:
        """Parse a model response into ExtractedRule objects.

        Tolerates markdown fences and surrounding prose: falls back to the
        first ``{...}`` block found in the response. Returns ``[]`` on any
        parse failure — never raises.
        """
        if not raw:
            return []
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Strip an opening fence (with optional language tag) and a
            # closing fence if present.
            cleaned = re.sub(r"^```[a-zA-Z0-9]*\s*", "", cleaned)
            if cleaned.endswith("```"):
                cleaned = cleaned[: -3]
            cleaned = cleaned.strip()

        result = None
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            # Last resort: find the outermost JSON object in the text.
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                try:
                    result = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return []
        if not isinstance(result, dict):
            return []
        rules = result.get("rules")
        if not isinstance(rules, list):
            return []

        extracted: list[ExtractedRule] = []
        for r in rules:
            if not isinstance(r, dict) or not r.get("rule"):
                continue
            try:
                confidence = int(r.get("confidence", 5))
            except (TypeError, ValueError):
                confidence = 5
            extracted.append(
                ExtractedRule(
                    rule_type=str(r.get("rule_type", "convention") or "convention"),
                    rule=str(r["rule"]),
                    example=str(r.get("example", "") or ""),
                    confidence=min(10, max(1, confidence)),
                )
            )
        return extracted

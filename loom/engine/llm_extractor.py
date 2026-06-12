"""LLMExtractor — uses Claude API for nuanced rule extraction from any text.

When enabled (API key is set), this replaces keyword-based extraction with
LLM-powered extraction that understands context, abstracts patterns from
concrete examples, and extracts style preferences from code.

Falls back gracefully when no API key is available.
"""

import json
import os
from dataclasses import dataclass
from typing import Any


# JSON schema for the structured output — a list of extracted rules.
_EXTRACTION_SCHEMA: dict = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "rules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rule_type": {
                            "type": "string",
                            "description": "Type of rule (e.g., type_safety, naming, preference)",
                        },
                        "rule": {
                            "type": "string",
                            "description": "The rule statement — what to do or not do",
                        },
                        "example": {
                            "type": "string",
                            "description": "Concrete example from the input text, or empty",
                        },
                        "confidence": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": "Confidence 1-10",
                        },
                    },
                    "required": ["rule_type", "rule", "confidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["rules"],
        "additionalProperties": False,
    },
}


@dataclass
class ExtractedRule:
    """A single rule extracted by the LLM."""

    rule_type: str
    rule: str
    example: str = ""
    confidence: int = 5


class LLMExtractor:
    """Uses Claude API for nuanced rule extraction from arbitrary text.

    This understands feedback beyond keyword matching — it can abstract
    patterns, detect coding style, and extract conventions from any
    natural-language description of an experience.
    """

    EXTRACTION_PROMPT = """\
You are a convention extraction engine. Given a text describing a coding \
experience (feedback, observation, reflection, teaching, or review), extract \
clear, reusable convention rules.

## Domain context

Domain: {domain}
Description: {description}
Known rule types: {rule_types}

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

## Input text

{text}"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        max_input_chars: int = 8000,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.max_input_chars = max_input_chars

    @property
    def is_available(self) -> bool:
        """True when an API key is configured and extraction can run."""
        return bool(self.api_key)

    async def extract(
        self,
        text: str,
        domain: str = "general",
        domain_config: Any | None = None,
    ) -> list[ExtractedRule]:
        """Extract convention rules from *text* using an LLM.

        Returns an empty list when no API key is available, the optional
        ``anthropic`` dependency is not installed, or no rules are found.
        """
        if not self.is_available:
            return []

        try:
            import anthropic
        except ImportError:
            return []  # optional dependency not installed

        description = "General conventions and preferences"
        rule_types = "any (free-form)"
        if domain_config is not None:
            description = getattr(domain_config, "description", description)
            rule_types = ", ".join(getattr(domain_config, "rule_types", []) or [])

        truncated = text[: self.max_input_chars]
        if len(text) > self.max_input_chars:
            truncated += "\n\n[text truncated]"

        prompt = self.EXTRACTION_PROMPT.format(
            domain=domain,
            description=description,
            rule_types=rule_types,
            text=truncated,
        )

        try:
            async_client = anthropic.AsyncAnthropic(api_key=self.api_key)
            response = await async_client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": _EXTRACTION_SCHEMA},
            )

            # The first text block is guaranteed to be valid JSON
            text_blocks = [b for b in response.content if b.type == "text"]
            if not text_blocks:
                return []

            result = json.loads(text_blocks[0].text)
            if not isinstance(result, dict) or "rules" not in result:
                return []

            return [
                ExtractedRule(
                    rule_type=r.get("rule_type", "convention"),
                    rule=r.get("rule", ""),
                    example=r.get("example", ""),
                    confidence=min(10, max(1, r.get("confidence", 5))),
                )
                for r in result["rules"]
                if r.get("rule")
            ]
        except Exception:
            return []

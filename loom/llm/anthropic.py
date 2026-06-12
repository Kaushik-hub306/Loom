"""Anthropic provider — uses the official anthropic Python SDK."""

from loom.llm.base import BaseLLMProvider, ExtractedRule

# JSON schema for structured output
_EXTRACTION_SCHEMA = {
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


class AnthropicProvider(BaseLLMProvider):
    """Claude-powered extraction via the anthropic SDK."""

    @property
    def default_model(self) -> str:
        return "claude-sonnet-4-6"

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def extract(self, text, domain="general",
                      domain_description="", rule_types=None,
                      max_input_chars=8000):
        try:
            import anthropic
        except ImportError:
            return []

        prompt = self._build_prompt(
            text=text,
            domain=domain,
            domain_description=domain_description,
            rule_types=rule_types,
        )
        # Truncate inside the prompt builder isn't applied to raw text,
        # so truncate here as well.
        truncated = text[:max_input_chars]
        prompt = self._build_prompt(
            text=truncated,
            domain=domain,
            domain_description=domain_description,
            rule_types=rule_types,
        )

        try:
            async_client = anthropic.AsyncAnthropic(api_key=self.api_key)
            response = await async_client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": _EXTRACTION_SCHEMA},
            )

            text_blocks = [b for b in response.content if b.type == "text"]
            if not text_blocks:
                return []

            import json
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

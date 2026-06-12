"""DeepSeek provider — uses the OpenAI-compatible SDK."""

from loom.llm.base import BaseLLMProvider, ExtractedRule

_EXTRACTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "extracted_rules",
        "strict": True,
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
    },
}


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek extraction via the OpenAI-compatible API.

    Uses the ``openai`` Python SDK pointed at ``https://api.deepseek.com``.
    Set ``LOOM_DEEPSEEK_API_KEY`` (not ``LOOM_OPENAI_API_KEY``) in your env.
    """

    @property
    def default_model(self) -> str:
        return "deepseek-chat"

    @property
    def provider_name(self) -> str:
        return "deepseek"

    async def extract(self, text, domain="general",
                      domain_description="", rule_types=None,
                      max_input_chars=8000):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return []

        prompt = self._build_prompt(
            text=text[:max_input_chars],
            domain=domain,
            domain_description=domain_description,
            rule_types=rule_types,
        )

        try:
            client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com",
            )
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                response_format=_EXTRACTION_SCHEMA,
            )

            import json
            content = response.choices[0].message.content or "{}"
            result = json.loads(content)
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

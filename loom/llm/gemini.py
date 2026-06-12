"""Gemini provider — uses the google-generativeai SDK."""

import json
from loom.llm.base import BaseLLMProvider, ExtractedRule


class GeminiProvider(BaseLLMProvider):
    """Gemini-powered extraction via the google-generativeai SDK."""

    @property
    def default_model(self) -> str:
        return "gemini-2.5-flash"

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def extract(self, text, domain="general",
                      domain_description="", rule_types=None,
                      max_input_chars=8000):
        try:
            import google.generativeai as genai
        except ImportError:
            return []

        prompt = self._build_prompt(
            text=text[:max_input_chars],
            domain=domain,
            domain_description=domain_description,
            rule_types=rule_types,
        )

        # Append structured output instruction for Gemini
        prompt += """

## Output format

Return ONLY a JSON object with this exact structure:
```json
{
  "rules": [
    {
      "rule_type": "string",
      "rule": "string",
      "example": "string",
      "confidence": integer
    }
  ]
}
```
Do NOT include markdown fences. Return ONLY valid JSON."""

        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            response = await model.generate_content_async(prompt)

            raw = response.text or "{}"
            # Strip markdown fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                if raw.endswith("```"):
                    raw = raw[:-3]
            raw = raw.strip()

            result = json.loads(raw)
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

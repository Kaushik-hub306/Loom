"""Gemini provider — uses the google-generativeai SDK."""

import asyncio

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
                      max_input_chars=8000) -> list[ExtractedRule]:
        try:
            import google.generativeai as genai
        except ImportError:
            return []

        prompt = self._build_prompt(
            text=text,
            domain=domain,
            domain_description=domain_description,
            rule_types=rule_types,
            max_input_chars=max_input_chars,
        )

        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            response = await asyncio.wait_for(
                model.generate_content_async(prompt), timeout=self.timeout
            )
            return self._parse_rules_json(response.text or "")
        except Exception as e:
            self._log_failure(e)
            return []

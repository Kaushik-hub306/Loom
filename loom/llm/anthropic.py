"""Anthropic provider — uses the official anthropic Python SDK."""

from loom.llm.base import BaseLLMProvider, ExtractedRule


class AnthropicProvider(BaseLLMProvider):
    """Claude-powered extraction via the anthropic SDK."""

    @property
    def default_model(self) -> str:
        return "claude-sonnet-5"

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def extract(self, text, domain="general",
                      domain_description="", rule_types=None,
                      max_input_chars=8000) -> list[ExtractedRule]:
        try:
            import anthropic
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
            async_client = anthropic.AsyncAnthropic(
                api_key=self.api_key, timeout=self.timeout
            )
            response = await async_client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            text_blocks = [
                b for b in response.content if getattr(b, "type", "") == "text"
            ]
            if not text_blocks:
                return []
            return self._parse_rules_json(text_blocks[0].text)
        except Exception as e:
            self._log_failure(e)
            return []

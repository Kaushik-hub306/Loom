"""DeepSeek provider — uses the OpenAI-compatible SDK."""

from loom.llm.base import BaseLLMProvider, ExtractedRule


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
                      max_input_chars=8000) -> list[ExtractedRule]:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return []

        # The shared prompt already demands JSON-only output (and contains
        # the word "json", which DeepSeek's json_object mode requires).
        prompt = self._build_prompt(
            text=text,
            domain=domain,
            domain_description=domain_description,
            rule_types=rule_types,
            max_input_chars=max_input_chars,
        )

        try:
            client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com",
                timeout=self.timeout,
            )
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                # DeepSeek supports OpenAI's json_object response format;
                # the stricter json_schema variant is NOT supported and
                # would fail every request.
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content or ""
            return self._parse_rules_json(content)
        except Exception as e:
            self._log_failure(e)
            return []

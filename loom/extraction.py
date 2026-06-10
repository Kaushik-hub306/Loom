"""LLM-based convention extraction from PR feedback.

Auto-detects API keys: ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY.
Falls back to keyword extraction if no key is available (free, always works).
"""

import json
import os

import httpx


def _get_api_keys():
    """Detect available API keys from env, Codex auth, etc."""
    keys = {}

    # Direct env vars
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        val = os.getenv(var, "")
        if val:
            keys[var] = val

    # Codex auth.json
    codex_auth = os.path.expanduser("~/.codex/auth.json")
    if os.path.exists(codex_auth):
        try:
            data = json.load(open(codex_auth))
            if data.get("OPENAI_API_KEY"):
                keys.setdefault("OPENAI_API_KEY", data["OPENAI_API_KEY"])
        except (json.JSONDecodeError, KeyError):
            pass

    return keys


EXTRACTION_PROMPT = """You are analyzing a rejected PR to extract coding conventions for future AI agents.

Read the PR review comments below. For each distinct convention violation mentioned, extract:
1. The rule type (type-annotation, naming, test-location, error-handling, import-style, formatting, architecture, documentation, or other)
2. The specific convention/rule the developer wants followed (be concrete and actionable)
3. A positive example of the correct pattern if one is mentioned

Return ONLY valid JSON:
{{
  "conventions": [
    {{
      "type": "type-annotation",
      "rule": "All function parameters and return values must have type annotations",
      "example": "def get_user(user_id: int) -> User:"
    }}
  ]
}}

PR REVIEW COMMENTS:
{comments}

PR DIFF (for context):
{diff}
"""


async def extract_conventions(comments: list[str], diff: str = "") -> list[dict]:
    """Extract coding conventions from PR review comments.

    Tries: Anthropic (Claude) → OpenAI → OpenRouter → keyword fallback.
    """
    if not comments:
        return []

    comments_text = "\n---\n".join(comments)
    prompt = EXTRACTION_PROMPT.format(
        comments=comments_text[:8000],
        diff=diff[:4000],
    )

    keys = _get_api_keys()

    # Anthropic (Claude)
    if "ANTHROPIC_API_KEY" in keys:
        result = await _call_anthropic(prompt, keys["ANTHROPIC_API_KEY"])
        if result:
            return result

    # OpenAI
    if "OPENAI_API_KEY" in keys:
        result = await _call_openai(prompt, keys["OPENAI_API_KEY"])
        if result:
            return result

    # OpenRouter (works with any model)
    if "OPENROUTER_API_KEY" in keys:
        result = await _call_openrouter(prompt, keys["OPENROUTER_API_KEY"])
        if result:
            return result

    # Keyword fallback (free, always works)
    return _extract_with_keywords(comments)


async def _call_anthropic(prompt: str, api_key: str) -> list[dict] | None:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return _parse_json_response(data["content"][0]["text"])
    except Exception:
        return None


async def _call_openai(prompt: str, api_key: str) -> list[dict] | None:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return _parse_json_response(data["choices"][0]["message"]["content"])
    except Exception:
        return None


async def _call_openrouter(prompt: str, api_key: str) -> list[dict] | None:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": "anthropic/claude-sonnet-4",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return _parse_json_response(data["choices"][0]["message"]["content"])
    except Exception:
        return None


def _extract_with_keywords(comments: list[str]) -> list[dict]:
    """Fallback: basic keyword extraction, no API key needed."""
    patterns = {
        "type-annotation": ["type hint", "type annotation", "typing", "mypy", "return type"],
        "naming": ["camelCase", "snake_case", "PascalCase", "naming convention", "rename"],
        "test-location": ["__tests__", "test file", "test directory", "conftest"],
        "error-handling": ["error handling", "result type", "try-except", "unwrap", "abort"],
        "import-style": ["absolute import", "relative import", "import order", "isort"],
        "formatting": ["tab", "space", "indent", "formatting", "prettier", "black"],
        "architecture": ["separation of concerns", "module", "service layer", "util"],
        "documentation": ["docstring", "comment", "readme", "document"],
    }
    results, seen = [], set()
    for comment in comments:
        lower = comment.lower()
        for rule_type, keywords in patterns.items():
            if rule_type in seen:
                continue
            for kw in keywords:
                if kw in lower:
                    results.append({
                        "type": rule_type,
                        "rule": comment.strip()[:200],
                        "example": "",
                    })
                    seen.add(rule_type)
                    break
    return results


def _parse_json_response(text: str) -> list[dict]:
    try:
        data = json.loads(text)
        return data.get("conventions", [])
    except json.JSONDecodeError:
        if "```json" in text:
            block = text.split("```json")[1].split("```")[0]
            return json.loads(block).get("conventions", [])
        if "```" in text:
            block = text.split("```")[1].split("```")[0]
            return json.loads(block).get("conventions", [])
        return []

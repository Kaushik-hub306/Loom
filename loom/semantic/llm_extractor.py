"""LLMExtractor — extract structured observations from unstructured text.

Uses Claude or OpenAI APIs when available, with a regex-based fallback that
works without any API key.  The fallback looks for labelled patterns like
"rule:", "fact:", "decision:", etc. in the input text.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


# ── Observation extraction via LLM APIs ─────────────────────────────────────

_EXTRACTION_PROMPT = """You are a knowledge extraction assistant.  From the
user's text, identify every observation that could be useful for a coding
agent's memory.  Return a JSON array of observation objects — each object
must have exactly these keys:

- "content"   (string): the observation text, as a clear standalone sentence.
- "category"  (string): a short slug like "type_safety", "style", "testing",
  "security", "performance", "architecture", "tooling", "convention", etc.
- "observation_type" (string): one of "rule", "fact", "decision", "context",
  or "technique".
- "tags"      (list of strings): 1-3 concise tags.
- "confidence" (integer 1-10): how confidently this can be extracted from the
  given text.  Use 7-10 for explicitly stated observations; 4-6 for strongly
  implied; 1-3 for speculative.

Classification guidelines
--------------------------
- "rule"       — a normative guideline, best practice, or style rule
- "fact"       — a verifiable statement about a language, framework, or tool
- "decision"   — a design choice, architectural decision, or trade-off
- "context"    — situational information (env, version, constraint, assumption)
- "technique"  — a reusable pattern, idiom, or trick

Return ONLY the JSON array on a single line — no markdown fences, no
explanatory text, no trailing comma.

Text to analyse:
"""


class LLMExtractor:
    """Extract structured observations from unstructured text.

    When an API key is available (Anthropic or OpenAI) the extractor calls the
    respective API with a structured prompt.  Without any API key it falls back
    to regex-based pattern extraction.
    """

    _CLAUDE_MODEL = "claude-sonnet-4-20250514"
    _OPENAI_MODEL = "gpt-4o"

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        openai_api_key: str | None = None,
        claude_model: str | None = None,
        openai_model: str | None = None,
    ):
        """Initialise the extractor.

        Parameters
        ----------
        anthropic_api_key:
            Anthropic API key.  If *None*, reads ``ANTHROPIC_API_KEY`` env var.
        openai_api_key:
            OpenAI API key.  If *None*, reads ``OPENAI_API_KEY`` env var.
        claude_model:
            Claude model ID.  Defaults to ``claude-sonnet-4-20250514``.
        openai_model:
            OpenAI model ID.  Defaults to ``gpt-4o``.
        """
        self._anthropic_key = anthropic_api_key or os.environ.get(
            "ANTHROPIC_API_KEY", ""
        )
        self._openai_key = openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        self._claude_model = claude_model or self._CLAUDE_MODEL
        self._openai_model = openai_model or self._OPENAI_MODEL

    # ── public API ──────────────────────────────────────────────────────

    def extract(self, text: str, domain: str = "general") -> list[dict[str, Any]]:
        """Extract observations from *text*.

        Returns a list of observation dicts, each with keys:
        ``content``, ``category``, ``observation_type``, ``tags``,
        ``confidence``, ``domain``.

        Where possible, ``domain`` is injected into every returned dict.
        """
        if not text.strip():
            return []

        # Try Anthropic first, then OpenAI, then fallback
        if self._anthropic_key:
            try:
                return self._extract_with_claude(text, domain)
            except Exception:
                pass  # fall through
        if self._openai_key:
            try:
                return self._extract_with_openai(text, domain)
            except Exception:
                pass  # fall through

        return self._extract_keyword_fallback(text, domain)

    # ── Claude API ───────────────────────────────────────────────────────

    def _extract_with_claude(self, text: str, domain: str) -> list[dict[str, Any]]:
        """Call the Anthropic Messages API for extraction."""
        body = json.dumps({
            "model": self._claude_model,
            "max_tokens": 2048,
            "temperature": 0.2,
            "messages": [
                {"role": "user", "content": _EXTRACTION_PROMPT + "\n\n" + text}
            ],
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._anthropic_key,
            "anthropic-version": "2023-06-01",
        }

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        content_block = data["content"][0]
        response_text = content_block.get("text", "")
        return self._parse_llm_response(response_text, domain)

    # ── OpenAI API ───────────────────────────────────────────────────────

    def _extract_with_openai(self, text: str, domain: str) -> list[dict[str, Any]]:
        """Call the OpenAI Chat Completions API for extraction."""
        body = json.dumps({
            "model": self._openai_model,
            "max_tokens": 2048,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _EXTRACTION_PROMPT},
                {"role": "user", "content": text},
            ],
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._openai_key}",
        }

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        response_text = data["choices"][0]["message"]["content"]
        return self._parse_llm_response(response_text, domain)

    # ── LLM response parsing ─────────────────────────────────────────────

    @staticmethod
    def _parse_llm_response(response_text: str, domain: str) -> list[dict[str, Any]]:
        """Parse JSON array from an LLM response, handling common wrappers."""
        # Strip markdown fences if present
        stripped = response_text.strip()
        if stripped.startswith("```"):
            # Remove opening fence line
            lines = stripped.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove closing fence line
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()

        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            # Try to extract just the JSON array with a regex
            match = re.search(r"\[.*]", stripped, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return []
            else:
                return []

        if not isinstance(parsed, list):
            return []

        results: list[dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            obs = {
                "content": str(item.get("content", "")),
                "category": str(item.get("category", "general")),
                "observation_type": str(item.get("observation_type", "rule")),
                "tags": [
                    str(t)
                    for t in item.get("tags", [])
                    if isinstance(t, str)
                ],
                "confidence": int(item.get("confidence", 5)),
                "domain": domain,
            }
            # Clamp / validate
            obs["confidence"] = max(1, min(10, obs["confidence"]))
            valid_types = {"rule", "fact", "decision", "context", "technique"}
            if obs["observation_type"] not in valid_types:
                obs["observation_type"] = "rule"
            results.append(obs)

        return results

    # ── Keyword / regex fallback ─────────────────────────────────────────

    @staticmethod
    def _extract_keyword_fallback(
        text: str, domain: str
    ) -> list[dict[str, Any]]:
        """Regex-based extraction when no LLM API is available.

        Looks for labelled patterns such as:

        - ``rule:  <content>``
        - ``fact:  <content>``
        - ``decision:  <content>``
        - ``context:  <content>``
        - ``technique:  <content>``
        - ``// RULE: <content>`` (comment-style)
        """
        results: list[dict[str, Any]] = []

        # Pattern: optional comment-style prefix, then a label, colon, then content
        _PATTERN = re.compile(
            r"(?:(?://|#|--|<!--)\s*)?"           # optional comment prefix
            r"\b(rule|fact|decision|context|technique)\b"
            r"\s*:\s*"
            r"(.+?)(?=$|(?:\n\s*(?://|#|--|<!--)\s*)?\b(?:rule|fact|decision|context|technique)\b|\n\n)"
            r"",
            re.IGNORECASE | re.DOTALL,
        )

        for match in _PATTERN.finditer(text):
            obs_type = match.group(1).lower()
            content = match.group(2).strip()
            if not content:
                continue

            # Infer a simple category from the content
            category = "general"
            content_lower = content.lower()
            if any(w in content_lower for w in ("type", "hint", "annotation", "mypy")):
                category = "type_safety"
            elif any(w in content_lower for w in ("style", "format", "lint", "convention", "naming")):
                category = "style"
            elif any(w in content_lower for w in ("test", "assert", "mock", "coverage")):
                category = "testing"
            elif any(w in content_lower for w in ("security", "encrypt", "auth", "sanitize", "validate")):
                category = "security"
            elif any(w in content_lower for w in ("performance", "perf", "slow", "fast", "optimize")):
                category = "performance"
            elif any(w in content_lower for w in ("architecture", "design", "pattern", "module")):
                category = "architecture"
            elif any(w in content_lower for w in ("error", "exception", "handle")):
                category = "error_handling"
            elif any(w in content_lower for w in ("async", "await", "promise", "callback")):
                category = "async"

            results.append({
                "content": content,
                "category": category,
                "observation_type": obs_type,
                "tags": [],
                "confidence": 5,
                "domain": domain,
            })

        return results

"""AutoObserver — passive observation engine for automatic convention capture.

Loom's answer to Glen's "automatic capture — nothing to write down, nothing to
maintain."  AutoObserver passively watches agent sessions and automatically
extracts conventions without requiring explicit tool calls.

It accumulates observations in an in-memory buffer, filters out noise, deduplicates
against existing rules, and periodically flushes batch extractions to the RuleStore.
"""

import re
import time
from dataclasses import dataclass, field
from typing import Any

from .domain_extractor import DomainExtractor
from .llm_extractor import ExtractedRule, LLMExtractor
from .rule_store import RuleStore


# ── Configuration ───────────────────────────────────────────────────────────


@dataclass
class ObserverConfig:
    """Configuration for AutoObserver sensitivity and flush behaviour.

    Attributes
    ----------
    sensitivity
        How aggressively observations are captured and extracted:

        * ``"silent"`` — only extract very clear, high-confidence patterns
        * ``"normal"`` — balanced extraction (default)
        * ``"eager"`` — extract everything, including borderline patterns

    min_observations_before_flush
        Minimum number of buffered observations before ``should_flush()``
        returns True.

    max_buffer_size
        Maximum number of observations to buffer.  When exceeded the oldest
        observations are dropped.

    auto_flush_enabled
        When True, ``observe()`` will automatically call ``flush()`` when
        ``should_flush()`` is True.

    confidence_threshold
        Only write rules whose confidence meets this threshold.  The effective
        threshold is lowered in eager mode and raised in silent mode.
    """

    sensitivity: str = "normal"  # "silent" | "normal" | "eager"
    min_observations_before_flush: int = 3
    max_buffer_size: int = 20
    auto_flush_enabled: bool = True
    confidence_threshold: int = 3

    def effective_confidence_threshold(self) -> int:
        """Return the real confidence threshold adjusted for sensitivity."""
        if self.sensitivity == "silent":
            return max(7, self.confidence_threshold)
        if self.sensitivity == "eager":
            return max(1, self.confidence_threshold - 1)
        return self.confidence_threshold

    def effective_min_observations(self) -> int:
        """Return the minimum-observation count adjusted for sensitivity."""
        if self.sensitivity == "silent":
            return max(5, self.min_observations_before_flush)
        if self.sensitivity == "eager":
            return max(1, self.min_observations_before_flush - 1)
        return self.min_observations_before_flush

    def effective_max_buffer(self) -> int:
        """Return the max buffer size adjusted for sensitivity."""
        if self.sensitivity == "eager":
            return self.max_buffer_size * 2
        if self.sensitivity == "silent":
            return max(10, self.max_buffer_size // 2)
        return self.max_buffer_size


# ── Observation data model ──────────────────────────────────────────────────


@dataclass
class Observation:
    """A single passively-captured observation."""

    context: str          # e.g. "tool_call", "conversation", "code_diff"
    observation: str      # the actual text observed
    domain: str | None = None  # detected domain, or None for auto-detect
    timestamp: float = field(default_factory=time.time)
    source: str = ""      # e.g. tool name, speaker role

    def summary(self) -> str:
        """Short single-line summary for session reports."""
        domain_part = f"[{self.domain}]" if self.domain else "[auto]"
        text_preview = self.observation[:80].replace("\n", " ")
        return f"{domain_part} {self.source}: {text_preview}"


# ── Noise filter helpers ────────────────────────────────────────────────────

# Phrases that suggest a casual remark, not a learnable convention.
_NOISE_PATTERNS: list[str] = [
    r"^ok(ay)?[\s,.!]*$",
    r"^nice[\s,.!]*$",
    r"^thanks[\s,.!]*$",
    r"^got it[\s,.!]*$",
    r"^will do[\s,.!]*$",
    r"^sure[\s,.!]*$",
    r"^no+\b",           # "no", "noo", "nooo..."
    r"^\?+$",            # "???"
    r"^hm+\b",           # "hmm", "hmmm..."
]

# Patterns that suggest a real convention being stated.
_CONVENTION_CLUE_PATTERNS: list[str] = [
    r"\b(always|never)\b",
    r"\b(should|must|ought to)\b",
    r"\b(convention|best practice|guideline)\b",
    r"\b(rule of thumb)\b",
    r"\b(pattern|anti-pattern)\b",
    r"\b(prefer|avoid|don't|do not)\b",
    r"\b(the way we)\b",
    r"\b(consistent)\b",
    r"\b(every time)\b",
    r"\b(make sure|ensure|be sure)\b",
]

# Words strongly associated with specific domains — for auto-detection.
_DOMAIN_CLUE_WORDS: dict[str, list[str]] = {
    "coding": [
        "type hint", "type annotation", "typing", "mypy",
        "function", "class", "variable", "import", "module",
        "decorator", "async", "await", "lambda", "list comprehension",
    ],
    "testing": [
        "test", "testing", "unit test", "integration", "pytest",
        "coverage", "mock", "fixture", "assert", "test case",
    ],
    "error_handling": [
        "error", "exception", "try-except", "try/except", "catch",
        "raise", "traceback", "fallback", "retry",
    ],
    "naming": [
        "camelcase", "snake_case", "pascalcase", "naming", "rename",
        "variable name", "function name",
    ],
    "architecture": [
        "separation of concerns", "service layer", "module",
        "architecture", "design pattern", "dependency", "interface",
    ],
    "security": [
        "security", "vulnerability", "injection", "xss", "csrf",
        "authentication", "authorization", "sanitize", "escape",
    ],
    "style": [
        "indent", "spacing", "line length", "formatting", "prettier",
        "black", "formatter", "quote", "trailing comma",
    ],
    "process": [
        "commit", "branch", "merge", "PR", "pull request", "review",
        "deploy", "release", "CI/CD", "workflow",
    ],
    "documentation": [
        "docstring", "comment", "readme", "document", "docs",
        "doc", "documentation",
    ],
}


# ── AutoObserver ────────────────────────────────────────────────────────────


class AutoObserver:
    """Passive observation engine for automatic convention capture.

    Watches agent sessions (tool calls, conversations, code changes) and
    silently accumulates observations.  Periodically batch-extracts rules
    from those observations and writes them to the RuleStore, filtering
    noise and deduplicating against existing rules.

    Parameters
    ----------
    store
        The RuleStore to write extracted rules into.

    domain_extractor
        DomainExtractor instance for keyword-based domain detection.

    llm_extractor
        Optional LLMExtractor for nuanced rule extraction.  When None
        (or when the LLM is unavailable), falls back to the
        DomainExtractor's keyword-based extraction.

    config
        ObserverConfig controlling sensitivity, thresholds, and auto-flush.
    """

    def __init__(
        self,
        store: RuleStore,
        domain_extractor: DomainExtractor,
        llm_extractor: LLMExtractor | None = None,
        config: ObserverConfig | None = None,
    ):
        self.store = store
        self.domain_extractor = domain_extractor
        self.llm_extractor = llm_extractor
        self.config = config or ObserverConfig()

        # Per-domain observation buffer.
        self._buffer: dict[str, list[Observation]] = {}
        self._session_started_at: float | None = None
        self._flush_count: int = 0
        self._rules_extracted_this_session: int = 0

    # ── Session lifecycle ───────────────────────────────────────────

    def on_session_start(self) -> None:
        """Reset state at the start of a new agent session."""
        self._buffer.clear()
        self._session_started_at = time.time()
        self._flush_count = 0
        self._rules_extracted_this_session = 0

    def on_session_end(self) -> dict[str, Any]:
        """Flush all remaining observations and return a session report.

        Call this at the end of every agent session.  It flushes every
        domain buffer and returns a structured summary of what was
        extracted.
        """
        total_rules = 0
        flushed_domains: list[str] = []

        for domain in list(self._buffer.keys()):
            result = self.flush(domain)
            if result["extracted"] > 0:
                total_rules += result["extracted"]
                flushed_domains.append(domain)

        # Also flush any observations that never got a domain assignment.
        orphan = self._buffer.pop("", None)
        if orphan:
            result = self.auto_flush()
            total_rules += result["extracted"]

        report = {
            "session_duration_seconds": (
                time.time() - (self._session_started_at or time.time())
            ),
            "total_observations": sum(len(v) for v in self._buffer.values()),
            "total_flushes": self._flush_count,
            "total_rules_extracted": total_rules,
            "flushed_domains": flushed_domains,
            "rules_extracted_this_session": self._rules_extracted_this_session,
        }
        return report

    # ── Core observation ────────────────────────────────────────────

    def observe(
        self,
        context: str,
        observation: str,
        domain: str | None = None,
    ) -> Observation | None:
        """Passively record an observation without extracting rules yet.

        Parameters
        ----------
        context
            What was being observed (e.g. "tool_call", "conversation",
            "code_diff").

        observation
            The actual text of what was observed.

        domain
            Known domain for this observation.  When None (the common
            case), the domain is auto-detected on flush.

        Returns
        -------
        Observation or None
            The recorded Observation object, or None if the observation
            was filtered as noise.
        """
        # Noise filter: skip things that are clearly not conventions.
        if _is_noise(observation):
            return None

        if self._session_started_at is None:
            self._session_started_at = time.time()

        # Auto-detect domain if not provided.
        detected_domain = domain or _auto_detect_domain(observation)
        key = detected_domain or ""

        obs = Observation(
            context=context,
            observation=observation,
            domain=detected_domain,
            source=context,
        )

        if key not in self._buffer:
            self._buffer[key] = []
        self._buffer[key].append(obs)

        # Trim buffer if too large.
        effective_max = self.config.effective_max_buffer()
        if len(self._buffer[key]) > effective_max:
            self._buffer[key] = self._buffer[key][-effective_max:]

        # Auto-flush if enabled and threshold reached.
        if self.config.auto_flush_enabled and self.should_flush():
            self.auto_flush()

        return obs

    def should_flush(self) -> bool:
        """Return True when enough observations have accumulated to warrant extraction."""
        effective_min = self.config.effective_min_observations()
        total = sum(len(v) for v in self._buffer.values())
        return total >= effective_min

    def flush(self, domain: str) -> dict[str, Any]:
        """Extract rules from all buffered observations for *domain*."""
        import asyncio

        observations = self._buffer.pop(domain, [])
        if not observations:
            return {"extracted": 0, "written": 0, "boosted": 0, "skipped": 0}

        # If we're inside an event loop, schedule async extraction
        # as a background task — blocking would deadlock.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._flush_domain_async(domain))
                # Put observations back so the async task can process them
                # _flush_domain_async pops from the buffer, so we need to
                # store them for the async path.
                self._buffer[domain] = observations
                return {"extracted": 0, "written": 0, "boosted": 0, "skipped": 0,
                        "scheduled": True, "count": len(observations)}
        except RuntimeError:
            pass  # no event loop — do sync extraction below

        rules = self.extract_from_observations(observations, domain=domain)
        return self._write_rules(rules, domain=domain)

    def auto_flush(self) -> dict[str, Any]:
        """Auto-detect the most-represented domain and flush it."""
        import asyncio

        if not self._buffer:
            return {"extracted": 0, "written": 0, "boosted": 0, "skipped": 0}

        known = [(d, len(obs)) for d, obs in self._buffer.items() if d]
        domain = max(known, key=lambda x: x[1])[0] if known else ""

        # If inside event loop, schedule background flush
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running() and domain:
                loop.create_task(self._flush_domain_async(domain))
                return {"extracted": 0, "written": 0, "boosted": 0, "skipped": 0,
                        "scheduled": True, "domain": domain}
        except RuntimeError:
            pass

        return self.flush(domain)

    # ── Extraction ─────────────────────────────────────────────────

    def extract_from_observations(
        self,
        observations: list[Observation],
        domain: str = "general",
    ) -> list[dict]:
        """Extract rules from a batch of observations for a domain.

        Groups observations by context before extracting to get better
        patterns.  When an LLMExtractor is available, uses it for nuanced
        extraction; otherwise falls back to keyword-based extraction via
        the DomainExtractor.
        """
        if not observations:
            return []

        # Group related observations by context for better batch extraction.
        grouped = _group_by_context(observations)

        # Build a composite text that presents each observation as a
        # separate data point the LLM can reason about.
        text = ""
        for ctx, items in grouped.items():
            text += f"\n## {ctx}\n\n"
            for i, obs in enumerate(items, 1):
                text += f"Observation {i}: {obs.observation}\n"

        # Prefer LLM extraction when available.
        if self.llm_extractor and self.llm_extractor.is_available:
            extracted = self._extract_with_llm(text, domain)
            if extracted:
                import sys
                print(f"[Loom] LLM extraction ({self.llm_extractor.active_provider_name}): "
                      f"{len(extracted)} rules from {len(observations)} observations",
                      file=sys.stderr, flush=True)
                return extracted
            import sys
            print(f"[Loom] LLM extraction returned empty — check API key and network",
                  file=sys.stderr, flush=True)

        # Fall back to keyword-based extraction.
        return self._extract_with_domain_extractor(text, domain)

    def extract_from_conversation(
        self,
        messages: list[dict],
        domain: str = "general",
    ) -> list[dict]:
        """Given a list of conversation turns, extract all learnable patterns.

        Each message dict should have ``role`` and ``content`` keys.  The
        function converts them into Observations and batches extraction.

        Parameters
        ----------
        messages
            List of message dicts (role + content), e.g. from an MCP
            conversation log.

        domain
            Domain hint for extraction.

        Returns
        -------
        list[dict]
            Extracted rule dicts ready to write.
        """
        observations: list[Observation] = []
        for msg in messages:
            content = msg.get("content", "")
            if not content or not isinstance(content, str):
                continue
            obs = Observation(
                context="conversation",
                observation=content,
                domain=domain,
                source=msg.get("role", "unknown"),
            )
            # Apply noise filter individually.
            if not _is_noise(obs.observation):
                observations.append(obs)

        if not observations:
            return []

        return self.extract_from_observations(observations, domain=domain)

    # ── Private extraction helpers ──────────────────────────────────

    async def _extract_with_llm_async(self, text: str, domain: str) -> list[dict]:
        """Run LLM extraction asynchronously (callable from event loop)."""
        try:
            result = await self.llm_extractor.extract(  # type: ignore[union-attr]
                text, domain=domain
            )
            return _extracted_rules_to_dicts(result)
        except Exception:
            return []

    def _extract_with_llm(self, text: str, domain: str) -> list[dict]:
        """Run LLM extraction synchronously (fallback for non-async callers)."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside a running event loop — cannot block.
                # Schedule extraction as a background task instead.
                # The result will be available on next flush.
                loop.create_task(
                    self._flush_domain_async(domain)
                )
                return []  # don't block — extraction happens in background
            else:
                return asyncio.run(
                    self._extract_with_llm_async(text, domain)
                )
        except Exception:
            return []

    async def _flush_domain_async(self, domain: str):
        """Extract and write rules for a domain — async, safe from event loop."""
        observations = self._buffer.pop(domain, [])
        if not observations:
            return

        text = ""
        grouped = _group_by_context(observations)
        for ctx, items in grouped.items():
            text += f"\n## {ctx}\n\n"
            for i, obs in enumerate(items, 1):
                text += f"Observation {i}: {obs.observation}\n"

        if self.llm_extractor and self.llm_extractor.is_available:
            extracted = await self._extract_with_llm_async(text, domain)
            import sys
            print(f"[Loom] LLM extraction ({self.llm_extractor.active_provider_name}): "
                  f"{len(extracted)} rules from {len(observations)} observations",
                  file=sys.stderr, flush=True)
        else:
            extracted = self._extract_with_domain_extractor(text, domain)

        if extracted:
            self._write_rules(extracted, domain=domain)

    def _extract_with_domain_extractor(
        self, text: str, domain: str
    ) -> list[dict]:
        """Keyword-based fallback extraction via DomainExtractor."""
        if not domain or domain == "general":
            # Try each known domain and collect results.
            all_rules: list[dict] = []
            for d in self.domain_extractor.domains:
                rules = self.domain_extractor.extract_rules(text, domain=d)
                all_rules.extend(rules)
            return all_rules
        return self.domain_extractor.extract_rules(text, domain=domain)

    def _write_rules(
        self, rules: list[dict], domain: str = "general"
    ) -> dict[str, Any]:
        """Write extracted rules to the store, handling dedup and boosting.

        Returns
        -------
        dict
            Keys: ``extracted``, ``written``, ``boosted``, ``skipped``.
        """
        threshold = self.config.effective_confidence_threshold()
        written = 0
        boosted = 0
        skipped = 0

        for rule_dict in rules:
            confidence = rule_dict.get("confidence", 5)
            if confidence < threshold:
                skipped += 1
                continue

            rule_domain = rule_dict.get("domain", domain)
            rule_type = rule_dict.get("rule_type", "convention")
            rule_text = rule_dict.get("rule", "")
            example = rule_dict.get("example", "")

            if not rule_text:
                skipped += 1
                continue

            # Check dedup: does the store already have a matching rule?
            rule_id = self.store._make_id(rule_domain, rule_type, rule_text)
            existing = self.store.get_rule(rule_id)
            if existing:
                # Boost confidence of the existing rule.
                self.store.promote_rule(rule_id)
                boosted += 1
            else:
                # Write as a new rule.
                self.store.add_rule(
                    domain=rule_domain,
                    rule_type=rule_type,
                    rule=rule_text,
                    example=example,
                    confidence=confidence,
                    source_type="auto_observer",
                )
                written += 1
                self._rules_extracted_this_session += 1

        self._flush_count += 1
        return {
            "extracted": len(rules),
            "written": written,
            "boosted": boosted,
            "skipped": skipped,
        }

    # ── Session summary ─────────────────────────────────────────────

    def get_session_summary(self) -> dict[str, Any]:
        """Return a summary of what has been observed this session.

        This does not flush — it reports on the current in-memory state.
        """
        buffer_by_domain: dict[str, int] = {}
        for domain, observations in self._buffer.items():
            buffer_by_domain[domain or "(unassigned)"] = len(observations)

        total = sum(buffer_by_domain.values())

        return {
            "session_active": self._session_started_at is not None,
            "session_duration_seconds": (
                time.time() - (self._session_started_at or time.time())
            ),
            "total_observations_buffered": total,
            "observations_by_domain": buffer_by_domain,
            "flushes_so_far": self._flush_count,
            "rules_extracted_so_far": self._rules_extracted_this_session,
            "sensitivity": self.config.sensitivity,
            "auto_flush_enabled": self.config.auto_flush_enabled,
        }

    # ── Integration hooks ───────────────────────────────────────────

    def on_tool_call(
        self, tool_name: str, args: dict | None, result: Any
    ) -> Observation | None:
        """Observe what an agent does via a tool call.

        Designed as an integration hook for future MCP middleware: the
        MCP server can call this whenever an agent invokes a tool.

        For now it simply records the tool name and result as an
        observation.  Smarter extraction (e.g. examining tool output for
        conventions) can be layered on later.

        Parameters
        ----------
        tool_name
            The name of the tool that was called (e.g. "read", "edit").

        args
            The arguments passed to the tool.

        result
            The result returned by the tool.

        Returns
        -------
        Observation or None
        """
        # Extract the instructive portion of the result for observation.
        observation_text = _extract_tool_observation(tool_name, args, result)
        if not observation_text:
            return None

        return self.observe(
            context="tool_call",
            observation=observation_text,
            source=tool_name,
        )

    @property
    def buffer_size(self) -> int:
        """Total number of buffered observations across all domains."""
        return sum(len(v) for v in self._buffer.values())


# ── Module-level helpers ────────────────────────────────────────────────────


def _is_noise(text: str) -> bool:
    """Return True when *text* looks like noise, not a learnable convention."""
    stripped = text.strip()

    # Very short utterances are rarely conventions.
    if len(stripped) < 12:
        for pattern in _NOISE_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                return True
        # Empty or whitespace-only is noise.
        if not stripped:
            return True

    return False


def _has_convention_signal(text: str) -> bool:
    """Return True when *text* contains phrasing that suggests a convention."""
    for pattern in _CONVENTION_CLUE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _auto_detect_domain(text: str) -> str | None:
    """Guess a domain from observation content.

    Returns a domain name string, or None if no domain is clearly indicated.
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for domain, keywords in _DOMAIN_CLUE_WORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[domain] = score

    if not scores:
        return None

    return max(scores, key=lambda d: scores[d])  # type: ignore[arg-type]


def _group_by_context(
    observations: list[Observation],
) -> dict[str, list[Observation]]:
    """Group observations by their context field for batch extraction."""
    grouped: dict[str, list[Observation]] = {}
    for obs in observations:
        ctx = obs.context or "general"
        if ctx not in grouped:
            grouped[ctx] = []
        grouped[ctx].append(obs)
    return grouped


def _extracted_rules_to_dicts(
    rules: list[ExtractedRule],
) -> list[dict]:
    """Convert ExtractedRule objects to plain dicts used by _write_rules."""
    return [
        {
            "rule_type": r.rule_type,
            "rule": r.rule,
            "example": r.example,
            "confidence": r.confidence,
        }
        for r in rules
    ]


def _extract_tool_observation(
    tool_name: str,
    args: dict | None,
    result: Any,
) -> str:
    """Extract an observation string from a tool call and its result.

    This is intentionally simple for the initial implementation — it
    captures the tool name and result structure.  Future versions can
    apply smarter extraction per tool type (e.g. examining code diffs
    from Edit tool calls for style conventions).
    """
    args = args or {}
    # Try to extract meaningful content from the result.
    if isinstance(result, str) and len(result) > 10:
        return f"Tool '{tool_name}' returned: {result[:500]}"
    if isinstance(result, dict) and result:
        # Pick out a summary from the result dict.
        summary_keys = ["output", "result", "message", "content", "summary"]
        for key in summary_keys:
            val = result.get(key)
            if isinstance(val, str) and val.strip():
                return f"Tool '{tool_name}': {val[:500]}"
        return f"Tool '{tool_name}' called with {len(result)} result fields"
    if isinstance(result, (list, tuple)) and len(result) > 0:
        return f"Tool '{tool_name}' returned {len(result)} items"
    # Fallback: just note the tool was called.
    arg_summary = ", ".join(f"{k}={_summarize_val(v)}" for k, v in args.items())
    extras = f" with args {arg_summary}" if arg_summary else ""
    return f"Tool '{tool_name}' called{extras}"


def _summarize_val(val: Any) -> str:
    """Return a short string summary of an arbitrary value."""
    if isinstance(val, str):
        return f"'{val[:50]}'" if len(val) > 50 else repr(val)
    if isinstance(val, (int, float, bool)):
        return str(val)
    if isinstance(val, (list, tuple)):
        return f"[{len(val)} items]"
    if isinstance(val, dict):
        return f"{{{len(val)} keys}}"
    return type(val).__name__

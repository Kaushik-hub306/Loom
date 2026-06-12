"""Default routing templates for integration connectors.

Each dict maps an event-type / channel-pattern / team-pattern to a
``{domain, observation_type}`` pair.  The ``IngestRouter`` uses these as
fallbacks when no custom routing is configured.
"""

from __future__ import annotations

# ── GitHub routing templates ──────────────────────────────────────────────────

DEFAULT_GITHUB_ROUTES: dict[str, dict[str, str]] = {
    "pull_request_review": {
        "domain": "coding",
        "observation_type": "rule",
    },
    "pull_request_review_comment": {
        "domain": "coding",
        "observation_type": "rule",
    },
    "issue_comment": {
        "domain": "coding",
        "observation_type": "decision",
    },
    "issues": {
        "domain": "coding",
        "observation_type": "decision",
    },
    "push": {
        "domain": "coding",
        "observation_type": "fact",
    },
    "commit_comment": {
        "domain": "coding",
        "observation_type": "rule",
    },
}

# ── Slack routing templates ──────────────────────────────────────────────────

DEFAULT_SLACK_ROUTES: dict[str, dict[str, str]] = {
    "eng": {
        "domain": "coding",
        "observation_type": "context",
    },
    "dev": {
        "domain": "coding",
        "observation_type": "context",
    },
    "engineering": {
        "domain": "coding",
        "observation_type": "context",
    },
    "sales": {
        "domain": "sales",
        "observation_type": "context",
    },
    "support": {
        "domain": "support",
        "observation_type": "context",
    },
    "help": {
        "domain": "support",
        "observation_type": "context",
    },
    "design": {
        "domain": "design",
        "observation_type": "context",
    },
    "product": {
        "domain": "decisions",
        "observation_type": "decision",
    },
}

# ── Linear routing templates ────────────────────────────────────────────────

DEFAULT_LINEAR_ROUTES: dict[str, dict[str, str]] = {
    "engineering": {
        "domain": "coding",
        "observation_type": "context",
    },
    "product": {
        "domain": "decisions",
        "observation_type": "decision",
    },
    "design": {
        "domain": "design",
        "observation_type": "decision",
    },
    "customer": {
        "domain": "support",
        "observation_type": "context",
    },
    "infrastructure": {
        "domain": "coding",
        "observation_type": "technique",
    },
    "security": {
        "domain": "coding",
        "observation_type": "rule",
    },
    "data": {
        "domain": "coding",
        "observation_type": "technique",
    },
    "mobile": {
        "domain": "coding",
        "observation_type": "context",
    },
}

# ── Jira routing templates ──────────────────────────────────────────────────

DEFAULT_JIRA_ROUTES: dict[str, dict[str, str]] = {
    "dev": {
        "domain": "coding",
        "observation_type": "context",
    },
    "eng": {
        "domain": "coding",
        "observation_type": "context",
    },
    "engineering": {
        "domain": "coding",
        "observation_type": "context",
    },
    "product": {
        "domain": "decisions",
        "observation_type": "decision",
    },
    "design": {
        "domain": "design",
        "observation_type": "decision",
    },
    "support": {
        "domain": "support",
        "observation_type": "context",
    },
    "ops": {
        "domain": "coding",
        "observation_type": "technique",
    },
    "security": {
        "domain": "coding",
        "observation_type": "rule",
    },
    "platform": {
        "domain": "coding",
        "observation_type": "technique",
    },
}

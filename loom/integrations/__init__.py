"""Integration connectors for auto-ingesting observations from external tools.

Each connector is independently usable — you can use just the GitHub handler
without Slack, etc.  Webhook handlers parse JSON payloads without requiring
any provider SDK.  SDK usage is optional for enhanced features (e.g. Slack
Events API verification).
"""

from __future__ import annotations

from loom.integrations.github_webhook import GitHubWebhookHandler
from loom.integrations.slack_connector import SlackConnector
from loom.integrations.linear_connector import LinearWebhookHandler
from loom.integrations.jira_connector import JiraWebhookHandler
from loom.integrations.ingest_router import IngestRouter
from loom.integrations.templates import (
    DEFAULT_GITHUB_ROUTES,
    DEFAULT_SLACK_ROUTES,
    DEFAULT_LINEAR_ROUTES,
    DEFAULT_JIRA_ROUTES,
)

__all__ = [
    "GitHubWebhookHandler",
    "SlackConnector",
    "LinearWebhookHandler",
    "JiraWebhookHandler",
    "IngestRouter",
    "DEFAULT_GITHUB_ROUTES",
    "DEFAULT_SLACK_ROUTES",
    "DEFAULT_LINEAR_ROUTES",
    "DEFAULT_JIRA_ROUTES",
]

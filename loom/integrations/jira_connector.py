"""Jira connector — parses Jira webhook payloads into observations.

No Jira SDK required.  Payloads follow the Atlassian webhook format.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class JiraWebhookHandler:
    """Parses Jira webhook payloads into observations.

    No signature verification is implemented by default; Jira webhooks
    use a shared secret approach that varies by deployment (Cloud vs. Server).
    """

    def parse_event(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse a Jira webhook payload into observation dicts.

        Parameters
        ----------
        payload:
            Parsed JSON body from the Jira webhook.

        Returns
        -------
        list[dict]
            Observation dicts extracted from the payload.
        """
        results: list[dict[str, Any]] = []

        webhook_event = payload.get("webhookEvent", "")
        issue = payload.get("issue") or {}
        comment = payload.get("comment") or {}

        # Issue created or updated — capture summary + description
        if webhook_event in ("jira:issue_created", "jira:issue_updated"):
            fields = issue.get("fields", {})
            summary = fields.get("summary", "")
            description = fields.get("description", "")
            text = summary
            if description:
                text = f"{summary}\n{description}"
            if text.strip():
                project_key = (fields.get("project") or {}).get("key", "")
                results.append(
                    {
                        "source": "jira",
                        "event": webhook_event,
                        "domain": "coding",  # Default; IngestRouter re-routes
                        "observation_type": "context",
                        "raw_text": text,
                        "metadata": {
                            "issue_key": issue.get("key", ""),
                            "project": project_key,
                            "issue_type": (fields.get("issuetype") or {}).get("name", ""),
                            "url": issue.get("self", ""),
                        },
                    }
                )

        # Comment added
        if webhook_event == "comment_created":
            body = comment.get("body", "")
            if body.strip():
                project_key = (
                    (issue.get("fields") or {}).get("project") or {}
                ).get("key", "")
                results.append(
                    {
                        "source": "jira",
                        "event": webhook_event,
                        "domain": "coding",  # Default; IngestRouter re-routes
                        "observation_type": "context",
                        "raw_text": body,
                        "metadata": {
                            "issue_key": issue.get("key", ""),
                            "project": project_key,
                            "author": (comment.get("author") or {}).get("displayName", ""),
                            "url": issue.get("self", ""),
                        },
                    }
                )

        return results

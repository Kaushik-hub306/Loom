"""GitHub webhook handler — parses GitHub webhook payloads and extracts observations.

No GitHub SDK required.  Payload verification uses HMAC-SHA256 as specified in the
GitHub webhook documentation.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class GitHubWebhookHandler:
    """Parses and verifies GitHub webhook payloads.

    Parameters
    ----------
    webhook_secret:
        The secret token configured in the GitHub App / repo webhook settings.
        If ``None``, signature verification is skipped (useful for local dev).
    """

    webhook_secret: str | None = None

    # ── signature verification ────────────────────────────────────────────

    def verify_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """Verify an HMAC-SHA256 signature against the webhook secret.

        Parameters
        ----------
        payload_body:
            The raw request body bytes.
        signature_header:
            The value of the ``X-Hub-Signature-256`` header (e.g.
            ``"sha256=abc123..."``).

        Returns
        -------
        bool
            ``True`` if the signature matches or no secret is configured.
        """
        if not self.webhook_secret:
            return True
        if not signature_header:
            return False
        try:
            algo, sig = signature_header.split("=", 1)
        except ValueError:
            return False
        if algo != "sha256":
            return False
        expected = hmac.new(
            self.webhook_secret.encode(), payload_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, sig)

    # ── event parsing ─────────────────────────────────────────────────────

    def parse_event(self, event_type: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse a GitHub webhook payload into a list of observation dicts.

        Parameters
        ----------
        event_type:
            The ``X-GitHub-Event`` header value (e.g. ``"pull_request_review"``).
        payload:
            The parsed JSON body.

        Returns
        -------
        list[dict]
            One or more observation dicts with keys ``source``, ``event``,
            ``domain``, ``observation_type``, ``raw_text``, and ``metadata``.
        """
        handler = self._HANDLERS.get(event_type)
        if handler is None:
            return []
        return handler(self, payload)

    def _parse_pr_review(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse a ``pull_request_review`` event.

        Handles both the review body and any inline review comments attached
        to the review.  Multiple inline comments each become a separate
        observation; the review body becomes one if no inline comments exist.
        """
        review = payload.get("review", {})
        results: list[dict[str, Any]] = []

        # Check for inline review comments first
        comments = review.get("comments", [])
        if comments:
            for comment in comments:
                body = comment.get("body", "")
                if not body or not body.strip():
                    continue
                results.append(
                    {
                        "source": "github",
                        "event": "pull_request_review",
                        "domain": "coding",
                        "observation_type": "rule",
                        "raw_text": body,
                        "metadata": {
                            "user": comment.get("user", {}).get("login", ""),
                            "path": comment.get("path", ""),
                            "line": comment.get("line"),
                            "html_url": comment.get("html_url", ""),
                        },
                    }
                )
            return results

        # No inline comments — fall back to the review body
        body = review.get("body", "")
        if not body or not body.strip():
            return []
        results.append(
            {
                "source": "github",
                "event": "pull_request_review",
                "domain": "coding",
                "observation_type": "rule",
                "raw_text": body,
                "metadata": {
                    "user": review.get("user", {}).get("login", ""),
                    "state": review.get("state", ""),
                    "submitted_at": review.get("submitted_at", ""),
                    "html_url": review.get("html_url", ""),
                    "pr_url": (payload.get("pull_request") or {}).get("html_url", ""),
                },
            }
        )
        return results

    def _parse_issue_comment(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse an ``issue_comment`` event."""
        comment = payload.get("comment", {})
        body = comment.get("body", "")
        if not body or not body.strip():
            return []
        issue = payload.get("issue", {})
        return [
            {
                "source": "github",
                "event": "issue_comment",
                "domain": "coding",
                "observation_type": "decision",
                "raw_text": body,
                "metadata": {
                    "user": comment.get("user", {}).get("login", ""),
                    "issue_title": issue.get("title", ""),
                    "html_url": comment.get("html_url", ""),
                },
            }
        ]

    def _parse_push(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse a ``push`` event — extracts commit messages."""
        results: list[dict[str, Any]] = []
        commits = payload.get("commits", [])
        for commit in commits:
            message = commit.get("message", "")
            if not message or not message.strip():
                continue
            results.append(
                {
                    "source": "github",
                    "event": "push",
                    "domain": "coding",
                    "observation_type": "fact",
                    "raw_text": message,
                    "metadata": {
                        "author": commit.get("author", {}).get("name", ""),
                        "sha": commit.get("id", ""),
                        "url": commit.get("url", ""),
                    },
                }
            )
        return results

    _HANDLERS: ClassVar[dict[str, Any]] = {
        "pull_request_review": _parse_pr_review,
        "issue_comment": _parse_issue_comment,
        "push": _parse_push,
    }

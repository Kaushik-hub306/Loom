"""Tests for GitHubWebhookHandler — HMAC verification and event parsing."""

import hashlib
import hmac
import json

import pytest

from loom.integrations.github_webhook import GitHubWebhookHandler


# ── shared constants ──────────────────────────────────────────────────────

SECRET = "my-secret-token"
PAYLOAD = b'{"action":"submitted","review":{"body":"Add type hints"}}'


def _make_signature(secret: str, body: bytes) -> str:
    """Build a sha256 HMAC signature header value."""
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# ── signature verification tests ──────────────────────────────────────────


class TestSignatureVerification:
    """Tests for verify_signature()."""

    def test_valid_signature_passes(self):
        """A correctly computed signature should verify as True."""
        handler = GitHubWebhookHandler(webhook_secret=SECRET)
        sig = _make_signature(SECRET, PAYLOAD)

        assert handler.verify_signature(PAYLOAD, sig) is True

    def test_invalid_signature_fails(self):
        """An incorrect signature should verify as False."""
        handler = GitHubWebhookHandler(webhook_secret=SECRET)
        bad_sig = "sha256=deadbeef" + "0" * 56

        assert handler.verify_signature(PAYLOAD, bad_sig) is False

    def test_different_secret_fails(self):
        """A signature computed with a different secret should fail."""
        handler = GitHubWebhookHandler(webhook_secret=SECRET)
        sig = _make_signature("wrong-secret", PAYLOAD)

        assert handler.verify_signature(PAYLOAD, sig) is False

    def test_missing_secret_allows_all(self):
        """When webhook_secret is None, any signature (or none) passes."""
        handler = GitHubWebhookHandler(webhook_secret=None)

        assert handler.verify_signature(PAYLOAD, "") is True
        assert handler.verify_signature(PAYLOAD, "sha256=abc") is True

    def test_missing_signature_header_when_secret_configured(self):
        """Empty signature header is rejected when a secret is set."""
        handler = GitHubWebhookHandler(webhook_secret=SECRET)

        assert handler.verify_signature(PAYLOAD, "") is False


# ── event parsing tests ───────────────────────────────────────────────────


class TestParseEvent:
    """Tests for parse_event() with various GitHub webhook event types."""

    def test_pr_review_extracts_review_body(self):
        """pull_request_review events extract the review body text."""
        handler = GitHubWebhookHandler()
        payload = {
            "action": "submitted",
            "review": {
                "body": "Please add type hints and docstrings",
                "user": {"login": "reviewer1"},
                "state": "changes_requested",
                "submitted_at": "2025-06-01T12:00:00Z",
                "html_url": "https://github.com/a/b/pull/1#review-1",
            },
            "pull_request": {"html_url": "https://github.com/a/b/pull/1"},
        }

        results = handler.parse_event("pull_request_review", payload)

        assert len(results) == 1
        obs = results[0]
        assert obs["source"] == "github"
        assert obs["event"] == "pull_request_review"
        assert obs["domain"] == "coding"
        assert obs["observation_type"] == "rule"
        assert "type hints" in obs["raw_text"]
        assert obs["metadata"]["user"] == "reviewer1"
        assert obs["metadata"]["state"] == "changes_requested"

    def test_pr_review_with_empty_body_returns_empty(self):
        """PR reviews with no body text produce no observations."""
        handler = GitHubWebhookHandler()
        payload = {
            "action": "submitted",
            "review": {"body": "", "user": {"login": "r"}, "state": "approved"},
        }

        results = handler.parse_event("pull_request_review", payload)

        assert results == []

    def test_pr_review_with_multiple_comments(self):
        """PR review with multiple inline comments extracts from each."""
        handler = GitHubWebhookHandler()
        payload = {
            "action": "submitted",
            "review": {
                "body": "Overall: use type hints",
                "user": {"login": "reviewer1"},
                "state": "changes_requested",
                "comments": [
                    {
                        "body": "Add type annotations here",
                        "user": {"login": "reviewer1"},
                        "path": "src/main.py",
                        "line": 42,
                        "html_url": "https://github.com/a/b/pull/1#r1",
                    },
                    {
                        "body": "Add unit tests for this",
                        "user": {"login": "reviewer1"},
                        "path": "tests/test_main.py",
                        "line": 10,
                        "html_url": "https://github.com/a/b/pull/1#r2",
                    },
                ],
            },
        }

        results = handler.parse_event("pull_request_review", payload)

        assert len(results) == 2
        assert results[0]["raw_text"] == "Add type annotations here"
        assert results[0]["metadata"]["path"] == "src/main.py"
        assert results[1]["raw_text"] == "Add unit tests for this"
        assert results[1]["metadata"]["path"] == "tests/test_main.py"

    def test_issue_comment_extracts_body(self):
        """issue_comment events extract the comment body."""
        handler = GitHubWebhookHandler()
        payload = {
            "action": "created",
            "comment": {
                "body": "We should standardize on pytest fixtures",
                "user": {"login": "dev1"},
                "html_url": "https://github.com/a/b/issues/1#comment-1",
            },
            "issue": {"title": "Testing conventions"},
        }

        results = handler.parse_event("issue_comment", payload)

        assert len(results) == 1
        obs = results[0]
        assert obs["source"] == "github"
        assert obs["event"] == "issue_comment"
        assert obs["observation_type"] == "decision"
        assert "pytest fixtures" in obs["raw_text"]
        assert obs["metadata"]["issue_title"] == "Testing conventions"

    def test_push_event_extracts_commit_messages(self):
        """push events extract messages from all commits."""
        handler = GitHubWebhookHandler()
        payload = {
            "ref": "refs/heads/main",
            "commits": [
                {
                    "id": "abc123",
                    "message": "Add type hints to engine module",
                    "author": {"name": "dev1"},
                    "url": "https://github.com/a/b/commit/abc123",
                },
                {
                    "id": "def456",
                    "message": "Fix CI pipeline",
                    "author": {"name": "dev2"},
                    "url": "https://github.com/a/b/commit/def456",
                },
            ],
        }

        results = handler.parse_event("push", payload)

        assert len(results) == 2
        assert results[0]["raw_text"] == "Add type hints to engine module"
        assert results[1]["raw_text"] == "Fix CI pipeline"
        assert results[0]["metadata"]["sha"] == "abc123"
        assert results[1]["metadata"]["sha"] == "def456"

    def test_push_with_empty_commits_returns_empty(self):
        """Push event with no commits produces no observations."""
        handler = GitHubWebhookHandler()
        payload = {"ref": "refs/heads/main", "commits": []}

        results = handler.parse_event("push", payload)

        assert results == []

    def test_unhandled_event_returns_empty(self):
        """Unknown event types produce an empty list."""
        handler = GitHubWebhookHandler()
        payload = {"action": "opened"}

        results = handler.parse_event("watch", payload)

        assert results == []

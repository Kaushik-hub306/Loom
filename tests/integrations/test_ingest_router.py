"""Tests for IngestRouter — routing observations to domains and types."""

import pytest

from loom.integrations.ingest_router import IngestRouter


# ── helpers ───────────────────────────────────────────────────────────────


def _make_obs(source: str, event: str, metadata: dict | None = None) -> dict:
    """Create a minimal observation dict for routing."""
    obs: dict = {
        "source": source,
        "event": event,
        "domain": "coding",
        "observation_type": "context",
        "raw_text": "",
    }
    if metadata:
        obs["metadata"] = metadata
    return obs


# ── routing tests ─────────────────────────────────────────────────────────


class TestRouteDefaults:
    """Tests for default routing templates."""

    def test_routes_github_pr_review_to_coding_rule(self):
        """PR review events route to coding domain, rule type."""
        router = IngestRouter()
        obs = _make_obs("github", "pull_request_review")

        result = router.route(obs)

        assert result["domain"] == "coding"
        assert result["observation_type"] == "rule"

    def test_routes_slack_sales_channel_to_sales(self):
        """Slack #sales channel messages route to sales domain."""
        router = IngestRouter()
        obs = _make_obs("slack", "message", {"channel": "sales"})

        result = router.route(obs)

        assert result["domain"] == "sales"
        assert result["observation_type"] == "context"

    def test_routes_slack_support_channel_to_support(self):
        """Slack #support channel messages route to support domain."""
        router = IngestRouter()
        obs = _make_obs("slack", "message", {"channel": "support"})

        result = router.route(obs)

        assert result["domain"] == "support"

    def test_unregistered_source_returns_defaults(self):
        """An unregistered source gets sensible defaults."""
        router = IngestRouter()
        obs = _make_obs("zendesk", "ticket_created")

        result = router.route(obs)

        assert result["domain"] == "coding"
        assert result["observation_type"] == "context"

    def test_unregistered_event_returns_defaults(self):
        """An unrecognized event type gets sensible defaults."""
        router = IngestRouter()
        obs = _make_obs("github", "fork")

        result = router.route(obs)

        assert result["domain"] == "coding"
        assert result["observation_type"] == "context"

    def test_routes_github_push_to_coding_fact(self):
        """Push events route to coding domain, fact type."""
        router = IngestRouter()
        obs = _make_obs("github", "push")

        result = router.route(obs)

        assert result["domain"] == "coding"
        assert result["observation_type"] == "fact"

    def test_routes_slack_eng_channel_to_coding(self):
        """Slack #eng channel messages route to coding domain."""
        router = IngestRouter()
        obs = _make_obs("slack", "message", {"channel": "eng"})

        result = router.route(obs)

        assert result["domain"] == "coding"
        assert result["observation_type"] == "context"


class TestCustomRoutes:
    """Tests for custom route registration."""

    def test_custom_route_overrides_defaults(self):
        """register() overrides default routing for a specific event."""
        router = IngestRouter()
        router.register("github", {
            "push": {"domain": "ops", "observation_type": "fact"},
        })
        obs = _make_obs("github", "push")

        result = router.route(obs)

        assert result["domain"] == "ops"
        assert result["observation_type"] == "fact"

    def test_custom_routes_preserve_other_defaults(self):
        """Registering one route doesn't affect other routes for the same source."""
        router = IngestRouter()
        router.register("github", {
            "push": {"domain": "ops", "observation_type": "technique"},
        })

        # Push uses the custom route
        result_push = router.route(_make_obs("github", "push"))
        assert result_push["domain"] == "ops"

        # PR review still uses the default
        result_pr = router.route(_make_obs("github", "pull_request_review"))
        assert result_pr["domain"] == "coding"
        assert result_pr["observation_type"] == "rule"

    def test_custom_route_for_new_source(self):
        """register() can add routes for a new source."""
        router = IngestRouter()
        router.register("zendesk", {
            "ticket_created": {"domain": "support", "observation_type": "context"},
        })
        obs = _make_obs("zendesk", "ticket_created")

        result = router.route(obs)

        assert result["domain"] == "support"

    def test_custom_slack_channel_route(self):
        """Custom Slack routes work with channel-based routing."""
        router = IngestRouter()
        router.register("slack", {
            "random": {"domain": "misc", "observation_type": "context"},
        })
        obs = _make_obs("slack", "message", {"channel": "random"})

        result = router.route(obs)

        assert result["domain"] == "misc"


class TestMetadataRouting:
    """Tests for source-specific metadata-based routing."""

    def test_slack_routes_by_channel_not_event(self):
        """Slack uses channel name (from metadata), not the event field."""
        router = IngestRouter()
        # Register a route for event="message" → but Slack routes by channel
        router.register("slack", {
            "message": {"domain": "should-not-match", "observation_type": "context"},
        })
        obs = _make_obs("slack", "message", {"channel": "design"})

        result = router.route(obs)

        # Should route by channel "design", not the event "message"
        assert result["domain"] == "design"

    def test_jira_routes_by_project(self):
        """Jira uses project key (from metadata), not the event field."""
        router = IngestRouter()
        # Jira default routes include "support" for the "support" project
        obs = _make_obs("jira", "jira:issue_created", {
            "project": "SUPPORT",
            "issue_key": "SUP-123",
        })

        result = router.route(obs)

        assert result["domain"] == "support"

    def test_linear_routes_by_team(self):
        """Linear uses team name (from metadata), not the event field."""
        router = IngestRouter()
        obs = _make_obs("linear", "create", {"team": "design"})

        result = router.route(obs)

        assert result["domain"] == "design"


class TestGetRoutes:
    """Tests for get_routes() introspection."""

    def test_get_all_routes(self):
        """get_routes() returns all source routing tables."""
        router = IngestRouter()

        routes = router.get_routes()

        assert "github" in routes
        assert "slack" in routes
        assert "linear" in routes
        assert "jira" in routes

    def test_get_routes_for_specific_source(self):
        """get_routes(source) returns only that source's routes."""
        router = IngestRouter()

        github_routes = router.get_routes("github")

        assert "pull_request_review" in github_routes
        assert "push" in github_routes

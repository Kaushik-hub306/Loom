"""IngestRouter — routes external events to Loom domains and observation types.

Each integration connector produces a raw observation dict with a default
``domain`` and ``observation_type``.  The IngestRouter refines these using
configurable routing templates so, for example, Slack messages from #sales
land in the ``sales`` domain instead of the default ``coding``.
"""

from __future__ import annotations

from typing import Any

from loom.integrations.templates import (
    DEFAULT_GITHUB_ROUTES,
    DEFAULT_SLACK_ROUTES,
    DEFAULT_LINEAR_ROUTES,
    DEFAULT_JIRA_ROUTES,
)


class IngestRouter:
    """Routes incoming observation dicts to the correct domain / observation_type.

    Routing is driven by registered route templates.  Built-in defaults handle
    GitHub, Slack, Linear, and Jira.  Callers can register custom routes that
    take precedence over the defaults.

    Usage::

        router = IngestRouter()
        router.register("github", {"push": {"domain": "ops", "observation_type": "fact"}})

        obs = {"source": "github", "event": "push", ...}
        router.route(obs)  # -> observation_type = "fact", domain = "ops"
    """

    def __init__(self):
        # Default templates applied first; custom registrations override
        self._routes: dict[str, dict[str, dict[str, str]]] = {
            "github": dict(DEFAULT_GITHUB_ROUTES),
            "slack": dict(DEFAULT_SLACK_ROUTES),
            "linear": dict(DEFAULT_LINEAR_ROUTES),
            "jira": dict(DEFAULT_JIRA_ROUTES),
        }

    # ── registration ──────────────────────────────────────────────────────

    def register(
        self, source: str, routes: dict[str, dict[str, str]]
    ) -> None:
        """Register or override route templates for a source.

        Parameters
        ----------
        source:
            The integration source name (``"github"``, ``"slack"``, etc.).
        routes:
            A mapping of event/channel/team keys to ``{domain, observation_type}``
            dicts.  These merge with (and override) any existing routes for
            this source.
        """
        if source not in self._routes:
            self._routes[source] = {}
        self._routes[source].update(routes)

    # ── routing ───────────────────────────────────────────────────────────

    def route(self, observation: dict[str, Any]) -> dict[str, Any]:
        """Route an observation dict, filling in domain/observation_type.

        Parameters
        ----------
        observation:
            A raw observation dict with at minimum ``source`` and ``event`` keys.
            May also include a ``metadata`` dict with source-specific keys like
            ``channel`` (Slack) or ``project`` (Jira).

        Returns
        -------
        dict
            The observation dict with ``domain`` and ``observation_type``
            filled in (defaults to ``"coding"`` / ``"context"`` if no route matches).
        """
        source = observation.get("source", "")
        event = observation.get("event", "")
        metadata = observation.get("metadata", {}) or {}

        # Look up the routing template for this source
        source_routes = self._routes.get(source, {})

        # Try to find a matching route key
        route = None

        # For Slack: route by channel name
        if source == "slack":
            channel = metadata.get("channel", "")
            route = source_routes.get(channel)

        # For Jira: route by project key
        elif source == "jira":
            project = metadata.get("project", "")
            route = source_routes.get(project.lower())

        # For Linear: route by team name
        elif source == "linear":
            team = metadata.get("team", "")
            route = source_routes.get(team.lower())

        # For GitHub (and others): route by event type
        if route is None:
            route = source_routes.get(event)

        # Apply the route
        if route:
            observation["domain"] = route.get("domain", "coding")
            observation["observation_type"] = route.get("observation_type", "context")
        else:
            # Sensible defaults for unregistered source/event
            observation.setdefault("domain", "coding")
            observation.setdefault("observation_type", "context")

        return observation

    # ── introspection ─────────────────────────────────────────────────────

    def get_routes(self, source: str | None = None) -> dict:
        """Return registered routes, optionally filtered by source."""
        if source:
            return self._routes.get(source, {})
        return dict(self._routes)

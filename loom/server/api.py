"""FastAPI application — REST API wrapping the Loom engine.

Endpoint prefix: ``/api/v2/``

This module is **optional**.  Import it only after installing::

    pip install loom-agent[server]

Usage::

    from loom.server.api import create_app
    from loom.storage import JSONFileBackend

    backend = JSONFileBackend(".loom")
    app = create_app(backend)

Or run directly::

    python -m loom.server.api
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ══════════════════════════════════════════════════════════════════════
# Guarded imports — fastapi, uvicorn, pydantic, jose, httpx are all
# optional.  If any are missing, create_app / main become no-ops that
# raise a clear error rather than crashing at import time.
# ══════════════════════════════════════════════════════════════════════

_MISSING: list[str] = []

try:
    from fastapi import FastAPI, Request, HTTPException, Depends, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, RedirectResponse
except ImportError:
    _MISSING.append("fastapi")

try:
    import uvicorn
except ImportError:
    _MISSING.append("uvicorn")

try:
    from pydantic import BaseModel, Field
except ImportError:
    _MISSING.append("pydantic")

try:
    import jose  # noqa: F401
except ImportError:
    _MISSING.append("python-jose")

try:
    import httpx  # noqa: F401
except ImportError:
    _MISSING.append("httpx")

# Only import local auth/deps/orgs when all dependencies are present
if not _MISSING:
    from loom.server.auth import (
        create_jwt,
        create_jwt_refresh,
        decode_jwt,
        get_github_authorization_url,
        exchange_github_code,
        get_google_authorization_url,
        exchange_google_code,
    )
    from loom.server.deps import (
        get_current_user,
        get_current_org,
        get_store,
        get_security_middleware,
        get_auth_context,
    )
    from loom.server.orgs import (
        OrgCreate,
        OrgResponse,
        MemberAdd,
        MemberResponse,
        create_default_org,
        get_user_orgs,
        get_org_members,
    )
    from loom.storage.backend import StorageBackend


# ── Pydantic models ──────────────────────────────────────────────────────

class ObservationCreate(BaseModel):
    """Request body for creating an observation."""
    domain: str = Field("general", description="Domain name, e.g. 'coding'")
    category: str = Field("general", description="Category, e.g. 'type_safety'")
    content: str = Field(..., min_length=1, description="The observation text")
    observation_type: str = Field("rule", description="One of: rule, fact, decision, context, technique")
    confidence: int = Field(5, ge=1, le=10, description="Initial confidence (1-10)")
    source_url: str = Field("", description="Optional source URL for provenance")
    source_agent: str = Field("", description="Optional agent identifier")
    source_session: str = Field("", description="Optional session identifier")
    tags: list[str] = Field(default_factory=list, description="Optional tags")
    access_scope: str = Field("team", description="Access scope: public, team, org, private")
    context: dict[str, Any] | None = Field(None, description="Optional structured context")


class ObservationUpdate(BaseModel):
    """Request body for updating an observation (all fields optional)."""
    content: str | None = None
    domain: str | None = None
    category: str | None = None
    observation_type: str | None = None
    confidence: int | None = Field(None, ge=1, le=10)
    tags: list[str] | None = None
    access_scope: str | None = None
    context: dict[str, Any] | None = None
    source_urls: list[str] | None = None


class SearchRequest(BaseModel):
    """Request body for hybrid search."""
    query: str = Field("", description="Free-text search query")
    domain: str | None = Field(None, description="Optional domain filter")
    observation_type: str | None = Field(None, description="Optional type filter")
    tags: list[str] | None = Field(None, description="Optional tags filter (AND logic)")
    min_confidence: int = Field(1, ge=1, le=10, description="Minimum confidence threshold")
    limit: int = Field(50, ge=1, le=500, description="Maximum results to return")


class GraphLinkRequest(BaseModel):
    """Request body for creating a knowledge graph link."""
    source_id: str = Field(..., description="Source observation ID")
    target_id: str = Field(..., description="Target observation ID")
    relation_type: str = Field("related_to", description="Relation: caused, implies, related_to, supersedes, refines")


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    org_id: str
    user_id: str


class UserResponse(BaseModel):
    """Authenticated user info."""
    user_id: str
    org_id: str
    scope: str


class ObservationResponse(BaseModel):
    """Observation as returned by the API."""
    id: str
    observation_type: str
    domain: str
    category: str
    content: str
    confidence: int
    times_confirmed: int
    times_violated: int
    source_urls: list[str]
    source_agent: str
    source_session: str
    tags: list[str]
    access_scope: str
    created_at: str
    updated_at: str
    context: dict[str, Any] | None = None


# ══════════════════════════════════════════════════════════════════════
# App factory
# ══════════════════════════════════════════════════════════════════════

def create_app(backend: StorageBackend) -> FastAPI:
    """Build and return a fully-configured FastAPI application.

    Parameters
    ----------
    backend:
        Any ``StorageBackend`` implementation (e.g. ``JSONFileBackend``
        for self-hosted or ``SQLiteBackend`` for multi-org SaaS).

    Returns
    -------
    FastAPI
        The configured application, ready to serve via uvicorn.
    """
    if _MISSING:
        raise ImportError(
            f"Missing optional server dependencies: {', '.join(_MISSING)}. "
            f"Install them with: pip install loom-agent[server]"
        )

    app = FastAPI(
        title="Loom API",
        description="REST API for the Loom memory layer — store, search, and analyse observations.",
        version="2.0.0",
    )

    # ── CORS — permissive for development ───────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Attach backend and graph to app state ───────────────────────
    app.state.store = backend

    # Lazy-init the knowledge graph (loaded from graph_store if available)
    try:
        from loom.engine.knowledge_graph import KnowledgeGraph
        from loom.engine.graph_store import GraphStore

        graph_path = Path(os.environ.get("LOOM_GRAPH_PATH", ".loom/graph.json"))
        graph_store = GraphStore(graph_path)
        app.state.graph = graph_store.load()
        app.state.graph_store = graph_store
    except Exception:
        app.state.graph = None
        app.state.graph_store = None

    # ── Auth middleware ─────────────────────────────────────────────
    try:
        from loom.security import SecurityMiddleware

        store_dir = Path(os.environ.get("LOOM_STORE_DIR", ".loom"))
        app.state.security_middleware = SecurityMiddleware(store_dir=store_dir)
    except Exception:
        app.state.security_middleware = None

    # ═══════════════════════════════════════════════════════════════
    # Health
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/v2/health")
    async def health():
        """Health check — no authentication required."""
        return {"status": "ok", "version": "2.0.0"}

    # ═══════════════════════════════════════════════════════════════
    # Auth endpoints
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/v2/auth/login/{provider}")
    async def auth_login(provider: str):
        """Redirect to the OAuth provider's authorization page."""
        if provider == "github":
            url = get_github_authorization_url()
        elif provider == "google":
            url = get_google_authorization_url()
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
        return RedirectResponse(url=url)

    @app.get("/api/v2/auth/callback/{provider}", response_model=TokenResponse)
    async def auth_callback(provider: str, code: str = Query(...)):
        """Handle OAuth callback, create/find user, return JWT.

        On first login a default org is created for the user.
        """
        # Exchange code for user info
        if provider == "github":
            oauth_user = await exchange_github_code(code)
        elif provider == "google":
            oauth_user = await exchange_google_code(code)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

        if not oauth_user.email:
            raise HTTPException(status_code=400, detail="OAuth provider did not return an email address")

        # Find or create user
        if hasattr(backend, "get_or_create_user"):
            user = backend.get_or_create_user(
                email=oauth_user.email,
                oauth_provider=oauth_user.provider,
                oauth_subject=oauth_user.subject,
            )
            user_id = user["id"]
        else:
            # FileBackend — use email hash as stable user ID
            import hashlib
            user_id = f"user-{hashlib.sha256(oauth_user.email.encode()).hexdigest()[:16]}"

        # Get or create orgs for this user
        orgs = get_user_orgs(backend, user_id)
        if not orgs:
            org = create_default_org(backend, user_id, oauth_user.email)
            orgs = [org]

        org_id = orgs[0]["id"]
        token = create_jwt(user_id=user_id, org_id=org_id, scope="read write")

        return TokenResponse(
            access_token=token,
            org_id=org_id,
            user_id=user_id,
        )

    @app.get("/api/v2/auth/me", response_model=UserResponse)
    async def auth_me(ctx: dict[str, Any] = Depends(get_auth_context)):
        """Return the current user's info from the JWT."""
        return UserResponse(
            user_id=ctx["user_id"],
            org_id=ctx["org_id"],
            scope=ctx["scope"],
        )

    @app.post("/api/v2/auth/refresh", response_model=TokenResponse)
    async def auth_refresh(request: Request):
        """Refresh a still-valid JWT, issuing a new token."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        token = auth_header[len("Bearer "):]

        try:
            payload = decode_jwt(token)
            new_token = create_jwt_refresh(token)
            return TokenResponse(
                access_token=new_token,
                org_id=payload.get("org", "default"),
                user_id=payload.get("sub", ""),
            )
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    # ═══════════════════════════════════════════════════════════════
    # Observations CRUD
    # ═══════════════════════════════════════════════════════════════

    @app.post("/api/v2/observations", response_model=ObservationResponse, status_code=201)
    async def create_observation(
        body: ObservationCreate,
        ctx: dict[str, Any] = Depends(get_auth_context),
        store: StorageBackend = Depends(get_store),
    ):
        """Create a new observation (or bump an existing one)."""
        data = body.model_dump(exclude_none=True)
        data.setdefault("context", data.pop("context", None) or {})
        obs = store.add_observation(data, org_id=ctx["org_id"])
        return _obs_to_response(obs)

    @app.get("/api/v2/observations", response_model=list[ObservationResponse])
    async def list_observations(
        domain: str | None = Query(None),
        observation_type: str | None = Query(None, alias="type"),
        tags: str | None = Query(None, description="Comma-separated tags"),
        min_confidence: int = Query(1, ge=1, le=10),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        ctx: dict[str, Any] = Depends(get_auth_context),
        store: StorageBackend = Depends(get_store),
    ):
        """List observations with optional filters."""
        filters: dict[str, Any] = {
            "min_confidence": min_confidence,
            "limit": limit,
            "offset": offset,
        }
        if domain:
            filters["domain"] = domain
        if observation_type:
            filters["observation_type"] = observation_type
        if tags:
            filters["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
        results = store.get_observations(filters, org_id=ctx["org_id"])
        return [_obs_to_response(o) for o in results]

    @app.get("/api/v2/observations/{obs_id}", response_model=ObservationResponse)
    async def get_observation(
        obs_id: str,
        ctx: dict[str, Any] = Depends(get_auth_context),
        store: StorageBackend = Depends(get_store),
    ):
        """Get a single observation by ID."""
        results = store.get_observations(
            {"limit": 1}, org_id=ctx["org_id"]
        )
        # Since get_observations uses filters but not ID-lookup directly,
        # we search through results.  Backends can override this pattern.
        obs = next((o for o in results if o.id == obs_id), None)
        # Try a broader search if not found in the first page
        if obs is None:
            obs = _get_obs_by_id(store, obs_id, ctx["org_id"])

        if obs is None:
            raise HTTPException(status_code=404, detail=f"Observation not found: {obs_id}")
        return _obs_to_response(obs)

    @app.patch("/api/v2/observations/{obs_id}", response_model=ObservationResponse)
    async def update_observation(
        obs_id: str,
        body: ObservationUpdate,
        ctx: dict[str, Any] = Depends(get_auth_context),
        store: StorageBackend = Depends(get_store),
    ):
        """Partially update an observation."""
        data = body.model_dump(exclude_none=True)
        obs = store.update_observation(obs_id, data, org_id=ctx["org_id"])
        if obs is None:
            raise HTTPException(status_code=404, detail=f"Observation not found: {obs_id}")
        return _obs_to_response(obs)

    @app.delete("/api/v2/observations/{obs_id}")
    async def delete_observation(
        obs_id: str,
        ctx: dict[str, Any] = Depends(get_auth_context),
        store: StorageBackend = Depends(get_store),
    ):
        """Delete an observation."""
        deleted = store.delete_observation(obs_id, org_id=ctx["org_id"])
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Observation not found: {obs_id}")
        return {"deleted": True, "id": obs_id}

    # ═══════════════════════════════════════════════════════════════
    # Search
    # ═══════════════════════════════════════════════════════════════

    @app.post("/api/v2/search", response_model=list[ObservationResponse])
    async def search_observations(
        body: SearchRequest,
        ctx: dict[str, Any] = Depends(get_auth_context),
        store: StorageBackend = Depends(get_store),
    ):
        """Hybrid (keyword + optional semantic) search across observations."""
        results = store.search(
            query=body.query,
            org_id=ctx["org_id"],
            domain=body.domain,
            observation_type=body.observation_type,
            tags=body.tags,
            min_confidence=body.min_confidence,
            limit=body.limit,
        )
        return [_obs_to_response(o) for o in results]

    # ═══════════════════════════════════════════════════════════════
    # Stats
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/v2/stats")
    async def get_stats(
        domain: str | None = Query(None),
        ctx: dict[str, Any] = Depends(get_auth_context),
        store: StorageBackend = Depends(get_store),
    ):
        """Return aggregate observation statistics."""
        return store.get_stats(org_id=ctx["org_id"], domain=domain)

    # ═══════════════════════════════════════════════════════════════
    # Webhook endpoints — external tool integrations
    # No JWT auth required; each uses provider-specific verification.
    # ═══════════════════════════════════════════════════════════════

    # Lazy-init integration components (created once on first use).
    _gh_handler: Any = None
    _slack_handler: Any = None
    _linear_handler: Any = None
    _jira_handler: Any = None
    _router: Any = None

    def _get_gh_handler():
        nonlocal _gh_handler
        if _gh_handler is None:
            from loom.integrations.github_webhook import GitHubWebhookHandler
            secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
            _gh_handler = GitHubWebhookHandler(
                webhook_secret=secret if secret else None
            )
        return _gh_handler

    def _get_slack_handler():
        nonlocal _slack_handler
        if _slack_handler is None:
            from loom.integrations.slack_connector import SlackConnector
            secret = os.environ.get("SLACK_SIGNING_SECRET", "")
            _slack_handler = SlackConnector(
                signing_secret=secret if secret else None
            )
        return _slack_handler

    def _get_linear_handler():
        nonlocal _linear_handler
        if _linear_handler is None:
            from loom.integrations.linear_connector import LinearWebhookHandler
            secret = os.environ.get("LINEAR_WEBHOOK_SECRET", "")
            _linear_handler = LinearWebhookHandler(
                webhook_secret=secret if secret else None
            )
        return _linear_handler

    def _get_jira_handler():
        nonlocal _jira_handler
        if _jira_handler is None:
            from loom.integrations.jira_connector import JiraWebhookHandler
            _jira_handler = JiraWebhookHandler()
        return _jira_handler

    def _get_router():
        nonlocal _router
        if _router is None:
            from loom.integrations.ingest_router import IngestRouter
            _router = IngestRouter()
        return _router

    async def _persist_observations(
        obs_list: list[dict[str, Any]], store: StorageBackend
    ) -> list[dict[str, Any]]:
        """Persist a list of observation dicts via the storage backend.

        Each observation dict is expected to have keys ``source``, ``event``,
        ``domain``, ``observation_type``, ``raw_text``, and ``metadata``
        as produced by the integration connectors.
        """
        stored: list[dict[str, Any]] = []
        for obs_dict in obs_list:
            try:
                metadata = obs_dict.get("metadata", {}) or {}
                obs = store.add_observation(
                    data={
                        "domain": obs_dict.get("domain", "general"),
                        "category": "general",
                        "content": obs_dict.get("raw_text", ""),
                        "observation_type": obs_dict.get(
                            "observation_type", "context"
                        ),
                        "source_url": metadata.get("url", metadata.get("html_url", "")),
                        "tags": [
                            obs_dict.get("source", ""),
                            obs_dict.get("event", ""),
                        ],
                        "context": metadata,
                    },
                )
                stored.append(
                    _obs_to_response(obs).model_dump()
                    if hasattr(_obs_to_response(obs), "model_dump")
                    else _obs_to_response(obs)
                )
            except Exception:
                continue
        return stored

    # ── GitHub webhook ────────────────────────────────────────────────

    @app.post("/webhook/github")
    async def webhook_github(request: Request):
        """Receive GitHub webhook events.

        Verifies the HMAC signature, parses the event, routes it, and
        stores the resulting observations.

        Headers used:
        - ``X-GitHub-Event`` — event type
        - ``X-Hub-Signature-256`` — HMAC-SHA256 signature
        """
        handler = _get_gh_handler()
        router = _get_router()

        raw_body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")
        event_type = request.headers.get("X-GitHub-Event", "")

        if not handler.verify_signature(raw_body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        observations = handler.parse_event(event_type, payload)
        if not observations:
            return JSONResponse(
                {"status": "ok", "stored": 0, "observations": []},
                status_code=200,
            )

        # Route each observation through the router
        enriched = [router.route(obs) for obs in observations]

        store: StorageBackend = app.state.store
        stored = await _persist_observations(enriched, store)

        return JSONResponse(
            {"status": "ok", "stored": len(stored), "observations": stored},
            status_code=200,
        )

    # ── Slack events ───────────────────────────────────────────────────

    @app.post("/webhook/slack/events")
    async def webhook_slack_events(request: Request):
        """Receive Slack Events API events.

        Handles URL verification challenges (returns the challenge token)
        and processes message events into observations.

        Headers used:
        - ``X-Slack-Request-Timestamp`` — request timestamp
        - ``X-Slack-Signature`` — HMAC signature
        """
        handler = _get_slack_handler()

        raw_body = await request.body()
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        if not handler.verify_request(raw_body, timestamp, signature):
            raise HTTPException(status_code=401, detail="Invalid Slack signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        # Handle Slack URL verification challenge
        if payload.get("type") == "url_verification":
            challenge = payload.get("challenge", "")
            return JSONResponse({"challenge": challenge}, status_code=200)

        # Process event callbacks
        event = payload.get("event", {})
        event_type = event.get("type", "")

        if event_type not in ("message", "app_mention"):
            return JSONResponse({"status": "ok", "stored": 0}, status_code=200)

        # Skip bot messages and message_changed subtype to avoid loops
        subtype = event.get("subtype", "")
        if subtype in ("bot_message", "message_changed", "message_deleted"):
            return JSONResponse({"status": "ok", "stored": 0}, status_code=200)

        channel = event.get("channel", "")
        user = event.get("user", "")
        text = event.get("text", "")

        obs = handler.parse_message(channel=channel, text=text, user=user)
        if obs is None:
            return JSONResponse(
                {"status": "ok", "stored": 0, "observations": []},
                status_code=200,
            )

        router = _get_router()
        enriched = [router.route(obs)]

        store: StorageBackend = app.state.store
        stored = await _persist_observations(enriched, store)

        return JSONResponse(
            {"status": "ok", "stored": len(stored), "observations": stored},
            status_code=200,
        )

    # ── Slack slash commands ────────────────────────────────────────────

    @app.post("/webhook/slack/commands")
    async def webhook_slack_commands(request: Request):
        """Receive Slack slash commands (/loom-record).

        Verifies the Slack signature, then parses the command into an
        observation stored via the backend.

        Handles both application/x-www-form-urlencoded and JSON bodies.
        """
        handler = _get_slack_handler()

        raw_body = await request.body()
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        if not handler.verify_request(raw_body, timestamp, signature):
            raise HTTPException(status_code=401, detail="Invalid Slack signature")

        # Slack slash commands may arrive as form-encoded data
        content_type = request.headers.get("Content-Type", "")
        body_str = raw_body.decode("utf-8")

        if "application/json" in content_type:
            try:
                payload = json.loads(body_str)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON payload")
            command = payload.get("command", "")
            text = payload.get("text", "")
            user = payload.get("user_id", payload.get("user_name", ""))
            channel = payload.get("channel_id", payload.get("channel_name", ""))
        else:
            from urllib.parse import parse_qs

            parsed = parse_qs(body_str)
            command = (parsed.get("command", [""])[0]).strip()
            text = (parsed.get("text", [""])[0]).strip()
            user = (
                parsed.get("user_id", parsed.get("user_name", [""]))[0]
            ).strip()
            channel = (
                parsed.get("channel_id", parsed.get("channel_name", [""]))[0]
            ).strip()

        if command != "/loom-record" or not text.strip():
            return JSONResponse(
                {"response_type": "ephemeral", "text": "Usage: /loom-record <text>"},
                status_code=200,
            )

        obs = handler.parse_message(channel=channel, text=text, user=user)
        if obs is None:
            return JSONResponse(
                {"response_type": "ephemeral", "text": "No text provided."},
                status_code=200,
            )

        # Force observation_type to "rule" for explicit slash commands
        obs["observation_type"] = "rule"

        router = _get_router()
        enriched = [router.route(obs)]

        store: StorageBackend = app.state.store
        stored = await _persist_observations(enriched, store)

        count = len(stored)
        return JSONResponse(
            {
                "response_type": "ephemeral",
                "text": (
                    f"Recorded {count} observation"
                    f"{'s' if count != 1 else ''}."
                ),
                "stored": count,
            },
            status_code=200,
        )

    # ── Linear webhook ──────────────────────────────────────────────────

    @app.post("/webhook/linear")
    async def webhook_linear(request: Request):
        """Receive Linear webhook events.

        Verifies the HMAC signature, parses Issue and Comment events,
        routes them, and stores the resulting observations.

        Headers used:
        - ``Linear-Signature`` — HMAC-SHA256 signature
        """
        handler = _get_linear_handler()
        router = _get_router()

        raw_body = await request.body()
        signature = request.headers.get("Linear-Signature", "")

        if not handler.verify_signature(raw_body, signature):
            raise HTTPException(status_code=401, detail="Invalid Linear signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        observations = handler.parse_event(payload)
        if not observations:
            return JSONResponse(
                {"status": "ok", "stored": 0, "observations": []},
                status_code=200,
            )

        enriched = [router.route(obs) for obs in observations]

        store: StorageBackend = app.state.store
        stored = await _persist_observations(enriched, store)

        return JSONResponse(
            {"status": "ok", "stored": len(stored), "observations": stored},
            status_code=200,
        )

    # ── Jira webhook ────────────────────────────────────────────────────

    @app.post("/webhook/jira")
    async def webhook_jira(request: Request):
        """Receive Jira webhook events.

        Parses issue and comment events, maps Jira projects to Loom
        domains, and stores the resulting observations.
        """
        handler = _get_jira_handler()
        router = _get_router()

        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        observations = handler.parse_event(payload)
        if not observations:
            return JSONResponse(
                {"status": "ok", "stored": 0, "observations": []},
                status_code=200,
            )

        enriched = [router.route(obs) for obs in observations]

        store: StorageBackend = app.state.store
        stored = await _persist_observations(enriched, store)

        return JSONResponse(
            {"status": "ok", "stored": len(stored), "observations": stored},
            status_code=200,
        )

    # ═══════════════════════════════════════════════════════════════
    # Knowledge graph
    # ═══════════════════════════════════════════════════════════════

    @app.post("/api/v2/graph/links")
    async def add_graph_link(
        body: GraphLinkRequest,
        ctx: dict[str, Any] = Depends(get_auth_context),
    ):
        """Add a directed link between two observations."""
        graph = app.state.graph
        if graph is None:
            raise HTTPException(status_code=501, detail="Knowledge graph not available")
        graph.add_link(body.source_id, body.target_id, body.relation_type)
        # Persist if a graph store is attached
        if app.state.graph_store:
            app.state.graph_store.save(graph)
        return {
            "source": body.source_id,
            "target": body.target_id,
            "relation": body.relation_type,
        }

    @app.get("/api/v2/graph/related/{obs_id}")
    async def get_related(
        obs_id: str,
        depth: int = Query(1, ge=1, le=5),
    ):
        """Return observation IDs related to the given ID."""
        graph = app.state.graph
        if graph is None:
            raise HTTPException(status_code=501, detail="Knowledge graph not available")
        related = graph.get_related(obs_id, depth=depth)
        links = graph.get_links(obs_id)
        return {"id": obs_id, "related": related, "depth": depth, "links": links}

    # ═══════════════════════════════════════════════════════════════
    # Organisations
    # ═══════════════════════════════════════════════════════════════

    @app.get("/api/v2/orgs", response_model=list[OrgResponse])
    async def list_orgs(
        ctx: dict[str, Any] = Depends(get_auth_context),
        store: StorageBackend = Depends(get_store),
    ):
        """List all organisations the current user belongs to."""
        orgs = get_user_orgs(store, ctx["user_id"])
        return [
            OrgResponse(
                id=o["id"],
                name=o["name"],
                slug=o["slug"],
                role=o.get("role", "member"),
                created_at=o.get("created_at", ""),
            )
            for o in orgs
        ]

    @app.post("/api/v2/orgs", response_model=OrgResponse, status_code=201)
    async def create_org(
        body: OrgCreate,
        ctx: dict[str, Any] = Depends(get_auth_context),
        store: StorageBackend = Depends(get_store),
    ):
        """Create a new organisation."""
        from loom.server.orgs import _slugify

        slug = body.slug or _slugify(body.name)

        if hasattr(store, "create_org"):
            org = store.create_org(body.name, slug, ctx["user_id"])
        else:
            # FileBackend does not support multi-org
            raise HTTPException(status_code=400, detail="Multi-org is not supported with the current storage backend")

        return OrgResponse(
            id=org["id"],
            name=org["name"],
            slug=org["slug"],
            role="owner",
            created_at=org.get("created_at", ""),
        )

    @app.get("/api/v2/orgs/{org_id}/members", response_model=list[MemberResponse])
    async def list_members(
        org_id: str,
        ctx: dict[str, Any] = Depends(get_auth_context),
        store: StorageBackend = Depends(get_store),
    ):
        """List all members of an organisation."""
        members = get_org_members(store, org_id)
        return [
            MemberResponse(
                id=m["id"],
                email=m["email"],
                oauth_provider=m.get("oauth_provider", ""),
                role=m.get("role", "member"),
            )
            for m in members
        ]

    @app.post("/api/v2/orgs/{org_id}/members", response_model=MemberResponse, status_code=201)
    async def add_member(
        org_id: str,
        body: MemberAdd,
        ctx: dict[str, Any] = Depends(get_auth_context),
        store: StorageBackend = Depends(get_store),
    ):
        """Add a member to an organisation by email.

        The user must already exist (have logged in at least once).
        """
        if not hasattr(store, "add_member"):
            raise HTTPException(status_code=400, detail="Member management is not supported with the current storage backend")

        # Look up user by email (a simple scan; SQLiteBackend can do better)
        # For now this is an invitation pattern — in production you'd store
        # pending invites.
        raise HTTPException(status_code=501, detail="Invitation flow not yet implemented")

    return app


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════


def _obs_to_response(obs: Any) -> ObservationResponse:
    """Convert an ``Observation`` (or dict) to an ``ObservationResponse``."""
    if isinstance(obs, dict):
        return ObservationResponse(**obs)
    return ObservationResponse(
        id=obs.id,
        observation_type=obs.observation_type,
        domain=obs.domain,
        category=obs.category,
        content=obs.content,
        confidence=obs.confidence,
        times_confirmed=obs.times_confirmed,
        times_violated=obs.times_violated,
        source_urls=obs.source_urls,
        source_agent=obs.source_agent,
        source_session=obs.source_session,
        tags=obs.tags,
        access_scope=obs.access_scope,
        created_at=obs.created_at,
        updated_at=obs.updated_at,
        context=obs.context,
    )


def _get_obs_by_id(store: Any, obs_id: str, org_id: str) -> Any | None:
    """Try to retrieve an observation by ID via search fallback."""
    results = store.search(query=obs_id, org_id=org_id, limit=10)
    return next((o for o in results if o.id == obs_id), None)


# ══════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════


def main():
    """Run the API server via uvicorn.

    Uses the ``PORT`` env var (default 8000) and ``DATABASE_URL`` env
    var to select the storage backend.  When ``DATABASE_URL`` is unset
    or set to an ``.json`` path, ``JSONFileBackend`` is used.
    """
    if _MISSING:
        raise ImportError(
            f"Missing optional server dependencies: {', '.join(_MISSING)}. "
            f"Install them with: pip install loom-agent[server]"
        )

    from loom.storage.file_backend import JSONFileBackend
    from loom.storage.sqlite_backend import SQLiteBackend

    db_url = os.environ.get("DATABASE_URL", "")
    store_dir = os.environ.get("LOOM_STORE_DIR", ".loom")

    if db_url and not db_url.endswith(".json"):
        # SQLite backend: DATABASE_URL=sqlite:///path/to/loom.db
        # Strip sqlite:/// prefix if present
        db_path = db_url.removeprefix("sqlite:///").removeprefix("sqlite://")
        backend: StorageBackend = SQLiteBackend(db_path)
    else:
        # File backend (default)
        store_path = db_url if db_url else Path(store_dir) / "store.json"
        backend = JSONFileBackend(store_path)

    app = create_app(backend)
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

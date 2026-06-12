"""FastAPI dependency injection for the Loom API server.

Provides reusable dependencies that extract the current user, org,
storage backend, and security middleware from each request.
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import Request, HTTPException, Depends
except ImportError:  # pragma: no cover
    Request = None  # type: ignore[assignment,misc]
    HTTPException = None  # type: ignore[assignment,misc]
    Depends = None  # type: ignore[assignment,misc]

from loom.server.auth import decode_jwt
from loom.storage.backend import StorageBackend


async def get_current_user(request: Request) -> dict[str, Any]:
    """Extract and verify JWT from the ``Authorization`` header.

    Returns the decoded token payload with ``sub`` (user_id), ``org``,
    and ``scope`` claims.

    Raises ``HTTPException(401)`` if the token is missing or invalid.
    """
    auth_header: str = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[len("Bearer "):]
    try:
        payload = decode_jwt(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return payload


async def get_current_org(request: Request) -> str:
    """Extract the active org ID from the JWT claims."""
    user = await get_current_user(request)
    org_id = user.get("org", "default")
    if not org_id:
        raise HTTPException(status_code=401, detail="No organisation scope in token")
    return org_id


async def get_store(request: Request) -> StorageBackend:
    """Return the storage backend from application state."""
    store: StorageBackend | None = getattr(request.app.state, "store", None)
    if store is None:
        raise HTTPException(status_code=500, detail="Storage backend not configured")
    return store


async def get_security_middleware(request: Request) -> Any:
    """Return the security middleware from application state.

    Returns *None* when no middleware is configured (API server mode
    does not always require the full security pipeline).
    """
    return getattr(request.app.state, "security_middleware", None)


# ── Composite dependency: user + org in one call ────────────────────────


async def get_auth_context(
    user: dict[str, Any] = Depends(get_current_user),
    org_id: str = Depends(get_current_org),
) -> dict[str, Any]:
    """Return a dict with both ``user_id`` and ``org_id`` for convenience."""
    return {"user_id": user["sub"], "org_id": org_id, "scope": user.get("scope", "read")}

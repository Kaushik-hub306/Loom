"""OAuth 2.1 authentication — JWT creation, verification, and OAuth flows.

Environment variables
--------------------
GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
    GitHub OAuth App credentials.
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    Google OAuth credentials.
JWT_SECRET
    Secret key for signing JWTs (HMAC-SHA256).
LOOM_BASE_URL
    Base URL for constructing redirect URIs, e.g. ``https://loom.example.com``.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any

# ── Guarded imports ──────────────────────────────────────────────────────
import json as _json

try:
    from jose import jwt as _jose_jwt
    from jose.exceptions import JWTError as _JWTError
except ImportError:  # pragma: no cover
    _jose_jwt = None  # type: ignore[assignment]
    _JWTError = Exception  # type: ignore[assignment]

try:
    import httpx as _httpx
except ImportError:  # pragma: no cover
    _httpx = None  # type: ignore[assignment]


# ── token helpers ────────────────────────────────────────────────────────

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_SECONDS = 24 * 60 * 60  # 24 hours


def create_jwt(user_id: str, org_id: str, scope: str = "read") -> str:
    """Create a signed JWT for the given user and org.

    Parameters
    ----------
    user_id:
        The user's unique ID in the storage backend.
    org_id:
        The active organisation ID for this token.
    scope:
        Token scope, e.g. ``"read"`` or ``"read write"``.
    """
    secret = _require_env("JWT_SECRET")
    now = int(time.time())
    payload = {
        "sub": user_id,
        "org": org_id,
        "scope": scope,
        "iat": now,
        "exp": now + _JWT_EXPIRY_SECONDS,
    }
    return _jose_jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def decode_jwt(token: str) -> dict[str, Any]:
    """Decode and verify a JWT.

    Returns the payload dict on success.  Raises ``ValueError`` if the
    token is invalid, expired, or tampered with.
    """
    secret = _require_env("JWT_SECRET")
    try:
        payload = _jose_jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
        return payload
    except _JWTError as exc:
        raise ValueError(f"Invalid or expired token: {exc}") from exc


def create_jwt_refresh(token: str) -> str:
    """Refresh a still-valid JWT, issuing a new one with the same claims."""
    payload = decode_jwt(token)
    return create_jwt(
        user_id=payload["sub"],
        org_id=payload["org"],
        scope=payload.get("scope", "read"),
    )


# ── OAuth providers ──────────────────────────────────────────────────────

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


@dataclass
class OAuthUser:
    """Normalised user info returned by any OAuth provider."""

    provider: str
    subject: str
    email: str
    name: str = ""
    avatar_url: str = ""


def get_github_authorization_url() -> str:
    """Build the GitHub OAuth authorization URL."""
    client_id = _require_env("GITHUB_CLIENT_ID")
    base_url = _require_env("LOOM_BASE_URL").rstrip("/")
    redirect_uri = f"{base_url}/api/v2/auth/callback/github"
    scope = "read:user user:email"
    return (
        f"{GITHUB_AUTHORIZE_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
    )


async def exchange_github_code(code: str) -> OAuthUser:
    """Exchange a GitHub OAuth code for user info."""
    client_id = _require_env("GITHUB_CLIENT_ID")
    client_secret = _require_env("GITHUB_CLIENT_SECRET")
    base_url = _require_env("LOOM_BASE_URL").rstrip("/")

    async with _httpx.AsyncClient() as client:
        # Exchange code for access token
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": f"{base_url}/api/v2/auth/callback/github",
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(f"GitHub token exchange failed: {token_data}")

        # Fetch user info
        user_resp = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        user_resp.raise_for_status()
        user_info = user_resp.json()

        # Fetch emails if primary is not public
        email = user_info.get("email")
        if not email:
            email_resp = await client.get(
                f"{GITHUB_USER_URL}/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            email_resp.raise_for_status()
            emails = email_resp.json()
            primary = next((e for e in emails if e.get("primary")), emails[0] if emails else {})
            email = primary.get("email", "")

        return OAuthUser(
            provider="github",
            subject=str(user_info.get("id", "")),
            email=email,
            name=user_info.get("name", user_info.get("login", "")),
            avatar_url=user_info.get("avatar_url", ""),
        )


def get_google_authorization_url() -> str:
    """Build the Google OAuth authorization URL."""
    client_id = _require_env("GOOGLE_CLIENT_ID")
    base_url = _require_env("LOOM_BASE_URL").rstrip("/")
    redirect_uri = f"{base_url}/api/v2/auth/callback/google"
    scope = "openid email profile"
    return (
        f"{GOOGLE_AUTHORIZE_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={scope}"
    )


async def exchange_google_code(code: str) -> OAuthUser:
    """Exchange a Google OAuth code for user info."""
    client_id = _require_env("GOOGLE_CLIENT_ID")
    client_secret = _require_env("GOOGLE_CLIENT_SECRET")
    base_url = _require_env("LOOM_BASE_URL").rstrip("/")

    async with _httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{base_url}/api/v2/auth/callback/google",
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(f"Google token exchange failed: {token_data}")

        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_resp.raise_for_status()
        user_info = user_resp.json()

        return OAuthUser(
            provider="google",
            subject=user_info.get("sub", ""),
            email=user_info.get("email", ""),
            name=user_info.get("name", ""),
            avatar_url=user_info.get("picture", ""),
        )


# ── API token hashing ────────────────────────────────────────────────────


def hash_token(token: str) -> str:
    """SHA-256 hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── helpers ──────────────────────────────────────────────────────────────


def _require_env(name: str) -> str:
    """Read a required environment variable, raising a clear error if missing."""
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(
            f"Environment variable {name} is required but not set. "
            f"Copy .env.example to .env and fill in the values."
        )
    return value

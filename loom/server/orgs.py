"""Multi-organisation management — CRUD orgs, invites, and memberships.

Pydantic models for request/response bodies and helper functions that
delegate to a ``StorageBackend``.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    BaseModel = object  # type: ignore[assignment,misc]
    Field = None  # type: ignore[assignment]


# ── Pydantic models ──────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    """Request body for creating an organisation."""
    name: str = Field(..., min_length=1, max_length=100, description="Organisation display name")
    slug: str | None = Field(None, min_length=1, max_length=40, pattern=r"^[a-z0-9-]+$", description="URL-friendly slug; auto-generated from name if omitted")


class OrgResponse(BaseModel):
    """Organisation as returned by the API."""
    id: str
    name: str
    slug: str
    role: str = "member"
    created_at: str = ""


class MemberAdd(BaseModel):
    """Request body for adding a member."""
    email: str = Field(..., description="Email of the user to invite")
    role: str = Field("member", pattern=r"^(owner|admin|member|viewer)$", description="Role to assign")


class MemberResponse(BaseModel):
    """Membership as returned by the API."""
    id: str
    email: str
    oauth_provider: str = ""
    role: str = "member"


# ── helper functions ─────────────────────────────────────────────────────


def _slugify(name: str) -> str:
    """Convert a name to a URL-friendly slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or f"org-{uuid.uuid4().hex[:8]}"


def create_default_org(
    backend: Any,
    user_id: str,
    user_email: str,
) -> dict[str, Any]:
    """Create a default personal organisation for a new user.

    Called on first login.  The org is named after the user's email
    username.
    """
    local = user_email.split("@")[0] if "@" in user_email else user_email
    name = f"{local}'s Workspace"
    slug = _slugify(name)

    # Check if the SQLiteBackend has create_org; for FileBackend, no-op
    if hasattr(backend, "create_org"):
        return backend.create_org(name, slug, user_id)

    # FileBackend — return a virtual org
    return {
        "id": "default",
        "name": name,
        "slug": "default",
        "created_at": "",
    }


def get_user_orgs(backend: Any, user_id: str) -> list[dict[str, Any]]:
    """Return all orgs the user belongs to."""
    if hasattr(backend, "get_user_orgs"):
        return backend.get_user_orgs(user_id)
    # FileBackend — single virtual org
    return [
        {
            "id": "default",
            "name": "Default Workspace",
            "slug": "default",
            "role": "owner",
            "created_at": "",
        }
    ]


def get_org_members(backend: Any, org_id: str) -> list[dict[str, Any]]:
    """Return all members of an org."""
    if hasattr(backend, "get_org_members"):
        return backend.get_org_members(org_id)
    return []

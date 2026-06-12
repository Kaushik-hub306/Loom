"""Loom REST API server — FastAPI application for cloud/SaaS deployments.

Provides OAuth 2.1 authentication, multi-org support, and a full
REST API wrapping the Loom engine.  This module is **optional** —
the MCP server over stdio is the primary interface.  Import the
``create_app`` or ``main`` entry points only after installing the
``server`` optional dependencies.

Usage::

    from loom.server.api import create_app
    from loom.storage import JSONFileBackend

    backend = JSONFileBackend(".loom")
    app = create_app(backend)
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════
# Guarded imports — all of these are optional.  The try/except block
# lets the MCP server import cleanly without fastapi/etc installed.
# ══════════════════════════════════════════════════════════════════════

_MISSING_DEPS: list[str] = []

try:
    import fastapi  # noqa: F401
except ImportError:
    _MISSING_DEPS.append("fastapi")

try:
    import uvicorn  # noqa: F401
except ImportError:
    _MISSING_DEPS.append("uvicorn")

try:
    import pydantic  # noqa: F401
except ImportError:
    _MISSING_DEPS.append("pydantic")

try:
    import jose  # noqa: F401
except ImportError:
    _MISSING_DEPS.append("python-jose")

try:
    import httpx  # noqa: F401
except ImportError:
    _MISSING_DEPS.append("httpx")

# Only export create_app and main when all deps are present
if not _MISSING_DEPS:
    from .api import create_app, main  # noqa: F401

__all__ = ["create_app", "main"]

"""Serve the React dashboard from FastAPI.

In development (``LOOM_DEV=true``), proxies to the Vite dev server at
``http://localhost:5173``.  In production, serves static files from the
``dashboard/dist/`` directory.

Usage in your app factory::

    from loom.server.static import mount_dashboard
    app = create_app(backend)
    mount_dashboard(app)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "dashboard"
_DIST_DIR = _DASHBOARD_DIR / "dist"
_INDEX_HTML = _DIST_DIR / "index.html"


def mount_dashboard(app: FastAPI) -> None:
    """Mount the dashboard on the FastAPI app.

    In dev mode the dashboard is served by Vite (``localhost:5173``), so
    this is a no-op — the Vite proxy in ``vite.config.ts`` handles it.
    """
    _mount_production(app)


def _mount_production(app: FastAPI) -> None:
    """Serve built dashboard files from ``dashboard/dist/``."""
    try:
        from fastapi.staticfiles import StaticFiles
    except ImportError:
        return  # fastapi not installed

    if not _INDEX_HTML.is_file():
        return  # dashboard not built

    static = StaticFiles(directory=str(_DIST_DIR), html=True)

    @app.get("/dashboard/{rest:path}")
    async def _dashboard_spa(rest: str = ""):
        """Serve the dashboard SPA — fallback to index.html for client-side routing."""
        from fastapi.responses import FileResponse

        file_path = _DIST_DIR / rest
        if rest and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_INDEX_HTML)

    @app.get("/dashboard")
    async def _dashboard_root():
        from fastapi.responses import FileResponse

        return FileResponse(_INDEX_HTML)

    # Also mount for direct asset access
    app.mount("/dashboard/assets", StaticFiles(directory=str(_DIST_DIR / "assets")), name="dashboard_assets")

    app.mount("/", static, name="dashboard")

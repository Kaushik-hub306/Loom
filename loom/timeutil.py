"""Shared timestamp helpers — tolerant parsing of stored ISO timestamps."""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = ["parse_iso_utc", "utc_now_iso"]


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string (timezone-aware)."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso_utc(ts: str) -> datetime | None:
    """Parse an ISO timestamp defensively; always return aware-UTC or None.

    Stored timestamps normally come from ``utc_now_iso`` and are aware,
    but hand-edited files, old schemas, or external imports can contain
    naive timestamps. Those are assumed to be UTC so comparisons against
    aware datetimes can never raise ``TypeError``.
    """
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

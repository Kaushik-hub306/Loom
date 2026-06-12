"""SQLiteBackend — SQLite-backed storage with multi-org isolation.

Uses Python's built-in ``sqlite3`` module (no SQLAlchemy dependency).
Each instance owns a single ``.db`` file.  All queries filter by
``org_id`` so multiple organisations can coexist in the same database.

Tables
------
observations
    id, org_id, observation_type, domain, category, content, context (JSON),
    confidence, times_confirmed, times_violated, source_urls (JSON),
    source_agent, source_session, tags (JSON), access_scope,
    created_at, updated_at

users
    id, email, oauth_provider, oauth_subject, created_at

orgs
    id, name, slug, created_at

memberships
    org_id, user_id, role

api_tokens
    token_hash, user_id, org_id, scope, created_at
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loom.engine.observation import Observation

from .backend import StorageBackend


class SQLiteBackend(StorageBackend):
    """SQLite-backed storage backend with full multi-org support.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  Created if it does not exist.
    """

    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        self._init_db()

    # ── connection management ────────────────────────────────────────────

    def get_connection(self) -> sqlite3.Connection:
        """Return a new ``sqlite3`` connection with ``sqlite3.Row`` row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        """Create tables and indexes if they do not already exist."""
        conn = self.get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS observations (
                    id              TEXT PRIMARY KEY,
                    org_id          TEXT NOT NULL DEFAULT 'default',
                    observation_type TEXT NOT NULL DEFAULT 'rule',
                    domain          TEXT NOT NULL DEFAULT 'general',
                    category        TEXT NOT NULL DEFAULT 'general',
                    content         TEXT NOT NULL DEFAULT '',
                    context         TEXT NOT NULL DEFAULT '{}',
                    confidence      INTEGER NOT NULL DEFAULT 5,
                    times_confirmed INTEGER NOT NULL DEFAULT 0,
                    times_violated  INTEGER NOT NULL DEFAULT 0,
                    source_urls     TEXT NOT NULL DEFAULT '[]',
                    source_agent    TEXT NOT NULL DEFAULT '',
                    source_session  TEXT NOT NULL DEFAULT '',
                    tags            TEXT NOT NULL DEFAULT '[]',
                    access_scope    TEXT NOT NULL DEFAULT 'team',
                    created_at      TEXT NOT NULL DEFAULT '',
                    updated_at      TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS users (
                    id              TEXT PRIMARY KEY,
                    email           TEXT NOT NULL,
                    oauth_provider  TEXT NOT NULL,
                    oauth_subject   TEXT NOT NULL,
                    created_at      TEXT NOT NULL DEFAULT '',
                    UNIQUE(oauth_provider, oauth_subject)
                );

                CREATE TABLE IF NOT EXISTS orgs (
                    id              TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    slug            TEXT NOT NULL UNIQUE,
                    created_at      TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS memberships (
                    org_id  TEXT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role    TEXT NOT NULL DEFAULT 'member',
                    PRIMARY KEY (org_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS api_tokens (
                    token_hash  TEXT PRIMARY KEY,
                    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    org_id      TEXT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
                    scope       TEXT NOT NULL DEFAULT 'read',
                    created_at  TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_obs_org_id
                    ON observations(org_id);
                CREATE INDEX IF NOT EXISTS idx_obs_domain
                    ON observations(org_id, domain);
                CREATE INDEX IF NOT EXISTS idx_obs_type
                    ON observations(org_id, observation_type);
                CREATE INDEX IF NOT EXISTS idx_obs_confidence
                    ON observations(org_id, confidence);
                CREATE INDEX IF NOT EXISTS idx_memberships_user
                    ON memberships(user_id);
                CREATE INDEX IF NOT EXISTS idx_memberships_org
                    ON memberships(org_id);
            """)
        finally:
            conn.close()

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_to_observation(row: sqlite3.Row) -> Observation:
        """Convert a ``sqlite3.Row`` into an ``Observation``."""
        return Observation(
            id=row["id"],
            observation_type=row["observation_type"],
            domain=row["domain"],
            category=row["category"],
            content=row["content"],
            context=_json_loads(row["context"]),
            confidence=row["confidence"],
            times_confirmed=row["times_confirmed"],
            times_violated=row["times_violated"],
            source_urls=_json_loads(row["source_urls"]),
            source_agent=row["source_agent"],
            source_session=row["source_session"],
            tags=_json_loads(row["tags"]),
            access_scope=row["access_scope"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ── CRUD ─────────────────────────────────────────────────────────────

    def add_observation(self, data: dict[str, Any], org_id: str = "default") -> Observation:
        """Insert a new observation, or bump an existing one on conflict."""
        obs_id = data.get("id") or _make_id(
            domain=data.get("domain", "general"),
            category=data.get("category", "general"),
            content=data.get("content", ""),
            obs_type=data.get("observation_type", "rule"),
        )
        now = self._now()

        conn = self.get_connection()
        try:
            # Try to load existing
            row = conn.execute(
                "SELECT * FROM observations WHERE id = ? AND org_id = ?",
                (obs_id, org_id),
            ).fetchone()

            if row:
                obs = self._row_to_observation(row)
                obs.confidence = min(10, obs.confidence + 1)
                obs.times_confirmed += 1
                obs.updated_at = now
                source_url = data.get("source_url", "")
                if source_url and source_url not in obs.source_urls:
                    obs.source_urls.append(source_url)
                source_agent = data.get("source_agent", "")
                if source_agent:
                    obs.source_agent = source_agent
                source_session = data.get("source_session", "")
                if source_session:
                    obs.source_session = source_session

                conn.execute(
                    """UPDATE observations
                       SET confidence = ?, times_confirmed = ?, updated_at = ?,
                           source_urls = ?, source_agent = ?, source_session = ?
                       WHERE id = ? AND org_id = ?""",
                    (
                        obs.confidence, obs.times_confirmed, obs.updated_at,
                        json.dumps(obs.source_urls), obs.source_agent,
                        obs.source_session, obs_id, org_id,
                    ),
                )
                conn.commit()
                return obs

            # Insert new
            new_obs = Observation(
                id=obs_id,
                observation_type=data.get("observation_type", "rule"),
                domain=data.get("domain", "general"),
                category=data.get("category", "general"),
                content=data.get("content", ""),
                context=data.get("context") or {},
                confidence=data.get("confidence", 5),
                times_confirmed=1,
                source_urls=[data["source_url"]] if data.get("source_url") else [],
                source_agent=data.get("source_agent", ""),
                source_session=data.get("source_session", ""),
                tags=data.get("tags") or [],
                access_scope=data.get("access_scope", "team"),
                created_at=now,
                updated_at=now,
            )

            conn.execute(
                """INSERT INTO observations
                   (id, org_id, observation_type, domain, category, content,
                    context, confidence, times_confirmed, times_violated,
                    source_urls, source_agent, source_session, tags,
                    access_scope, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_obs.id, org_id, new_obs.observation_type,
                    new_obs.domain, new_obs.category, new_obs.content,
                    json.dumps(new_obs.context), new_obs.confidence,
                    new_obs.times_confirmed, new_obs.times_violated,
                    json.dumps(new_obs.source_urls), new_obs.source_agent,
                    new_obs.source_session, json.dumps(new_obs.tags),
                    new_obs.access_scope, new_obs.created_at, new_obs.updated_at,
                ),
            )
            conn.commit()
            return new_obs
        finally:
            conn.close()

    def get_observations(
        self,
        filters: dict[str, Any] | None = None,
        org_id: str = "default",
    ) -> list[Observation]:
        """Return observations matching *filters*."""
        filters = filters or {}
        clauses: list[str] = ["org_id = ?"]
        params: list[Any] = [org_id]

        if "domain" in filters and filters["domain"]:
            clauses.append("domain = ?")
            params.append(filters["domain"])
        if "category" in filters and filters["category"]:
            clauses.append("category = ?")
            params.append(filters["category"])
        if "observation_type" in filters and filters["observation_type"]:
            clauses.append("observation_type = ?")
            params.append(filters["observation_type"])
        if "min_confidence" in filters:
            clauses.append("confidence >= ?")
            params.append(filters["min_confidence"])
        if "tags" in filters and filters["tags"]:
            # Filter rows whose tags JSON contains every requested tag
            for tag in filters["tags"]:
                clauses.append("tags LIKE ?")
                params.append(f'%"{tag}"%')
        if "access_scope" in filters and filters["access_scope"]:
            clauses.append("access_scope = ?")
            params.append(filters["access_scope"])

        where = " AND ".join(clauses)
        limit_clause = ""
        if "limit" in filters:
            limit_clause = " LIMIT ?"
            params.append(int(filters["limit"]))
        offset_clause = ""
        if filters.get("offset"):
            offset_clause = " OFFSET ?"
            params.append(int(filters["offset"]))

        conn = self.get_connection()
        try:
            rows = conn.execute(
                f"SELECT * FROM observations WHERE {where} "
                f"ORDER BY confidence DESC, times_confirmed DESC"
                f"{limit_clause}{offset_clause}",
                params,
            ).fetchall()
            return [self._row_to_observation(r) for r in rows]
        finally:
            conn.close()

    def update_observation(
        self,
        observation_id: str,
        data: dict[str, Any],
        org_id: str = "default",
    ) -> Observation | None:
        """Partially update an observation. Returns *None* if not found."""
        now = self._now()
        allowed = [
            "content", "category", "domain", "observation_type",
            "confidence", "context", "tags", "access_scope",
            "source_urls",
        ]
        set_clauses: list[str] = ["updated_at = ?"]
        params: list[Any] = [now]

        for key in allowed:
            if key in data:
                col = key
                val = data[key]
                if col in ("context", "tags", "source_urls"):
                    val = json.dumps(val) if isinstance(val, list | dict) else val
                set_clauses.append(f"{col} = ?")
                params.append(val)

        params.extend([observation_id, org_id])

        conn = self.get_connection()
        try:
            conn.execute(
                f"UPDATE observations SET {', '.join(set_clauses)} "
                f"WHERE id = ? AND org_id = ?",
                params,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM observations WHERE id = ? AND org_id = ?",
                (observation_id, org_id),
            ).fetchone()
            return self._row_to_observation(row) if row else None
        finally:
            conn.close()

    def delete_observation(
        self,
        observation_id: str,
        org_id: str = "default",
    ) -> bool:
        """Delete an observation. Returns *True* if it existed."""
        conn = self.get_connection()
        try:
            cur = conn.execute(
                "DELETE FROM observations WHERE id = ? AND org_id = ?",
                (observation_id, org_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def search(
        self,
        query: str,
        org_id: str = "default",
        **kwargs: Any,
    ) -> list[Observation]:
        """Keyword search with optional filters."""
        clauses: list[str] = ["org_id = ?"]
        params: list[Any] = [org_id]

        if query:
            clauses.append(
                "(content LIKE ? OR category LIKE ? OR domain LIKE ? OR id LIKE ?)"
            )
            like = f"%{query}%"
            params.extend([like, like, like, like])

        if kwargs.get("domain"):
            clauses.append("domain = ?")
            params.append(kwargs["domain"])
        if kwargs.get("observation_type"):
            clauses.append("observation_type = ?")
            params.append(kwargs["observation_type"])
        if kwargs.get("min_confidence"):
            clauses.append("confidence >= ?")
            params.append(kwargs["min_confidence"])
        if kwargs.get("tags"):
            for tag in kwargs["tags"]:
                clauses.append("tags LIKE ?")
                params.append(f'%"{tag}"%')

        where = " AND ".join(clauses)
        limit_clause = ""
        if kwargs.get("limit"):
            limit_clause = " LIMIT ?"
            params.append(int(kwargs["limit"]))

        conn = self.get_connection()
        try:
            rows = conn.execute(
                f"SELECT * FROM observations WHERE {where} "
                f"ORDER BY confidence DESC, times_confirmed DESC"
                f"{limit_clause}",
                params,
            ).fetchall()
            return [self._row_to_observation(r) for r in rows]
        finally:
            conn.close()

    def get_stats(
        self,
        org_id: str = "default",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return aggregate statistics."""
        conn = self.get_connection()
        try:
            params: list[Any] = [org_id]
            domain_clause = ""
            if kwargs.get("domain"):
                domain_clause = "AND domain = ?"
                params.append(kwargs["domain"])

            total_row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM observations "
                f"WHERE org_id = ? {domain_clause}",
                params,
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            if total == 0:
                return {
                    "total": 0,
                    "by_type": {},
                    "by_domain": {},
                    "by_category": {},
                    "avg_confidence": 0.0,
                }

            by_type_rows = conn.execute(
                f"SELECT observation_type, COUNT(*) as cnt FROM observations "
                f"WHERE org_id = ? {domain_clause} "
                f"GROUP BY observation_type",
                params,
            ).fetchall()

            by_domain_rows = conn.execute(
                f"SELECT domain, COUNT(*) as cnt FROM observations "
                f"WHERE org_id = ? {domain_clause} "
                f"GROUP BY domain",
                params,
            ).fetchall()

            by_cat_rows = conn.execute(
                f"SELECT category, COUNT(*) as cnt FROM observations "
                f"WHERE org_id = ? {domain_clause} "
                f"GROUP BY category",
                params,
            ).fetchall()

            avg_row = conn.execute(
                f"SELECT AVG(confidence) as avg_conf FROM observations "
                f"WHERE org_id = ? {domain_clause}",
                params,
            ).fetchone()
            avg_confidence = avg_row["avg_conf"] if avg_row else 0.0

            return {
                "total": total,
                "by_type": {r["observation_type"]: r["cnt"] for r in by_type_rows},
                "by_domain": {r["domain"]: r["cnt"] for r in by_domain_rows},
                "by_category": {r["category"]: r["cnt"] for r in by_cat_rows},
                "avg_confidence": avg_confidence,
            }
        finally:
            conn.close()

    # ── user / org / membership helpers ───────────────────────────────────

    def get_or_create_user(
        self,
        email: str,
        oauth_provider: str,
        oauth_subject: str,
    ) -> dict[str, Any]:
        """Find an existing user by OAuth provider+subject, or create one.

        Returns a dict with keys ``id``, ``email``, ``oauth_provider``,
        ``oauth_subject``, ``created_at``.
        """
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE oauth_provider = ? AND oauth_subject = ?",
                (oauth_provider, oauth_subject),
            ).fetchone()
            if row:
                return dict(row)

            import uuid

            user_id = str(uuid.uuid4())
            now = self._now()
            conn.execute(
                "INSERT INTO users (id, email, oauth_provider, oauth_subject, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, email, oauth_provider, oauth_subject, now),
            )
            conn.commit()
            return {
                "id": user_id,
                "email": email,
                "oauth_provider": oauth_provider,
                "oauth_subject": oauth_subject,
                "created_at": now,
            }
        finally:
            conn.close()

    def create_org(self, name: str, slug: str, owner_user_id: str) -> dict[str, Any]:
        """Create an org and add the creator as *owner*."""
        import uuid

        conn = self.get_connection()
        try:
            org_id = str(uuid.uuid4())
            now = self._now()
            conn.execute(
                "INSERT INTO orgs (id, name, slug, created_at) VALUES (?, ?, ?, ?)",
                (org_id, name, slug, now),
            )
            conn.execute(
                "INSERT INTO memberships (org_id, user_id, role) VALUES (?, ?, ?)",
                (org_id, owner_user_id, "owner"),
            )
            conn.commit()
            return {"id": org_id, "name": name, "slug": slug, "created_at": now}
        finally:
            conn.close()

    def get_user_orgs(self, user_id: str) -> list[dict[str, Any]]:
        """Return all orgs a user belongs to, with their role."""
        conn = self.get_connection()
        try:
            rows = conn.execute(
                "SELECT o.id, o.name, o.slug, o.created_at, m.role "
                "FROM orgs o JOIN memberships m ON o.id = m.org_id "
                "WHERE m.user_id = ? "
                "ORDER BY o.created_at",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_org_members(self, org_id: str) -> list[dict[str, Any]]:
        """Return all members of an org."""
        conn = self.get_connection()
        try:
            rows = conn.execute(
                "SELECT u.id, u.email, u.oauth_provider, m.role "
                "FROM users u JOIN memberships m ON u.id = m.user_id "
                "WHERE m.org_id = ?",
                (org_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def add_member(self, org_id: str, user_id: str, role: str = "member") -> bool:
        """Add a user to an org. Returns *True* on success, *False* if already a member."""
        conn = self.get_connection()
        try:
            conn.execute(
                "INSERT INTO memberships (org_id, user_id, role) VALUES (?, ?, ?)",
                (org_id, user_id, role),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Return a user dict by ID, or *None*."""
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_org(self, org_id: str) -> dict[str, Any] | None:
        """Return an org dict by ID, or *None*."""
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM orgs WHERE id = ?", (org_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_membership(self, org_id: str, user_id: str) -> dict[str, Any] | None:
        """Return a membership dict, or *None*."""
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM memberships WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


# ── helpers ────────────────────────────────────────────────────────────────


def _json_loads(text: str) -> Any:
    """Safely parse a JSON string, returning a default on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text if isinstance(text, str) else {}


def _make_id(
    domain: str,
    category: str,
    content: str,
    obs_type: str = "rule",
) -> str:
    """Build a deterministic observation ID."""
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", content.lower().strip())[:60].strip("-")
    return f"{domain}::{obs_type}::{category}::{slug}"

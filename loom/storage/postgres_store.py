"""PostgresStore — PostgreSQL storage backend for Loom Enterprise/Cloud."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from loom.storage.backend import StorageBackend


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: tuple, cursor) -> dict:
    """Convert a database row to a dict using column names."""
    cols = [desc[0] for desc in cursor.description]
    result = {}
    for col, val in zip(cols, row):
        if isinstance(val, str):
            result[col] = val
        elif isinstance(val, (int, float)):
            result[col] = val
        elif val is None:
            result[col] = None
        elif hasattr(val, "isoformat"):
            result[col] = val.isoformat()
        else:
            result[col] = val
    return result


class PostgresStore(StorageBackend):
    """PostgreSQL storage backend with connection pooling.

    Connects via ``LOOM_DATABASE_URL`` env var.  Auto-creates tables
    on first connect via migration files in ``loom/storage/migrations/``.
    """

    def __init__(self, config):
        self.config = config
        self._pool = None

    # ── Lifecycle ──────────────────────────────────────────────────

    def initialize(self):
        import psycopg2
        from psycopg2.pool import ThreadedConnectionPool

        dsn = self.config.database_url
        if not dsn:
            raise RuntimeError(
                "LOOM_DATABASE_URL is required for PostgresStore. "
                "Set it in your MCP config or environment."
            )

        self._pool = ThreadedConnectionPool(
            minconn=self.config.db_pool_min,
            maxconn=self.config.db_pool_max,
            dsn=dsn,
            sslmode="require",  # Required for Supabase / Neon
        )

        # Run migrations
        migrations_dir = Path(__file__).parent / "migrations"
        if migrations_dir.exists():
            with self._conn() as conn:
                with conn.cursor() as cur:
                    # Ensure migrations table exists
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS schema_migrations (
                            version TEXT PRIMARY KEY,
                            applied_at TIMESTAMPTZ DEFAULT NOW()
                        )
                    """)
                    # Run migration files in order
                    for sql_file in sorted(migrations_dir.glob("*.sql")):
                        version = sql_file.stem
                        cur.execute(
                            "SELECT 1 FROM schema_migrations WHERE version = %s",
                            (version,),
                        )
                        if cur.fetchone():
                            continue
                        cur.execute(sql_file.read_text())
                        cur.execute(
                            "INSERT INTO schema_migrations (version) VALUES (%s)",
                            (version,),
                        )
                    conn.commit()

    def health_check(self) -> bool:
        if not self._pool:
            return False
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    @contextmanager
    def _conn(self):
        """Get a connection from the pool. Auto-return on exit."""
        if not self._pool:
            raise RuntimeError("PostgresStore not initialized")
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    # ── Rules CRUD ─────────────────────────────────────────────────

    def get_rules(self, domain=None, min_confidence=1):
        with self._conn() as conn:
            with conn.cursor() as cur:
                if domain:
                    cur.execute(
                        "SELECT * FROM rules WHERE domain = %s AND confidence >= %s "
                        "ORDER BY confidence DESC",
                        (domain, min_confidence),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM rules WHERE confidence >= %s "
                        "ORDER BY confidence DESC",
                        (min_confidence,),
                    )
                return [_row_to_dict(r, cur) for r in cur.fetchall()]

    def get_rule(self, rule_id):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM rules WHERE id = %s", (rule_id,))
                row = cur.fetchone()
                return _row_to_dict(row, cur) if row else None

    def add_rule(self, rule):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM rules WHERE id = %s", (rule["id"],)
                )
                existing = cur.fetchone()
                now = _now()

                if existing:
                    cur.execute(
                        "UPDATE rules SET confidence = LEAST(10, confidence + 1), "
                        "times_confirmed = times_confirmed + 1, "
                        "updated_at = %s WHERE id = %s RETURNING *",
                        (now, rule["id"]),
                    )
                else:
                    cur.execute(
                        """INSERT INTO rules (id, domain, rule_type, rule, example,
                           confidence, times_confirmed, sources, source_type,
                           created_at, updated_at, project)
                           VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s)
                           RETURNING *""",
                        (
                            rule["id"],
                            rule.get("domain", "general"),
                            rule.get("rule_type", "convention"),
                            rule["rule"],
                            rule.get("example", ""),
                            rule.get("confidence", 5),
                            json.dumps(rule.get("sources", [])),
                            rule.get("source_type", ""),
                            rule.get("created_at", now),
                            now,
                            rule.get("project", ""),
                        ),
                    )
                conn.commit()
                return _row_to_dict(cur.fetchone(), cur)

    def delete_rule(self, rule_id):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rules WHERE id = %s", (rule_id,))
                conn.commit()
                return cur.rowcount > 0

    def promote_rule(self, rule_id):
        return self.add_rule({"id": rule_id})

    def demote_rule(self, rule_id):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE rules SET confidence = GREATEST(1, confidence - 1), "
                    "times_violated = times_violated + 1, updated_at = %s "
                    "WHERE id = %s RETURNING *",
                    (_now(), rule_id),
                )
                row = cur.fetchone()
                conn.commit()
                return _row_to_dict(row, cur) if row else None

    # ── Search ─────────────────────────────────────────────────────

    def search_rules(self, query, domain=None, min_confidence=1,
                     limit=None, rule_type=None):
        with self._conn() as conn:
            with conn.cursor() as cur:
                q = f"%{query}%"
                sql = """SELECT * FROM rules WHERE confidence >= %s
                         AND (rule ILIKE %s OR rule_type ILIKE %s
                              OR domain ILIKE %s OR id ILIKE %s)"""
                params = [min_confidence, q, q, q, q]

                if domain:
                    sql += " AND domain = %s"
                    params.append(domain)
                if rule_type:
                    sql += " AND rule_type = %s"
                    params.append(rule_type)

                sql += " ORDER BY confidence DESC, times_confirmed DESC"
                if limit:
                    sql += " LIMIT %s"
                    params.append(limit)

                cur.execute(sql, params)
                return [_row_to_dict(r, cur) for r in cur.fetchall()]

    def get_domain_stats(self, domain=None):
        with self._conn() as conn:
            with conn.cursor() as cur:
                if domain:
                    cur.execute(
                        "SELECT COUNT(*) as total, AVG(confidence) as avg_conf "
                        "FROM rules WHERE domain = %s",
                        (domain,),
                    )
                else:
                    cur.execute(
                        "SELECT COUNT(*) as total, AVG(confidence) as avg_conf "
                        "FROM rules"
                    )
                row = cur.fetchone()

                # By type
                cur.execute(
                    "SELECT rule_type, COUNT(*) FROM rules "
                    + ("WHERE domain = %s " % (f"'{domain}'") if domain else "")
                    + "GROUP BY rule_type"
                )
                by_type = {r[0]: r[1] for r in cur.fetchall()}

                return {
                    "total": row[0],
                    "by_type": by_type,
                    "avg_confidence": float(row[1]) if row[1] else 0.0,
                }

    def get_all_domain_stats(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT domain, COUNT(*), AVG(confidence) "
                    "FROM rules GROUP BY domain"
                )
                result = {}
                for row in cur.fetchall():
                    domain, count, avg = row
                    cur.execute(
                        "SELECT rule_type, COUNT(*) FROM rules "
                        "WHERE domain = %s GROUP BY rule_type",
                        (domain,),
                    )
                    by_type = {r[0]: r[1] for r in cur.fetchall()}
                    result[domain] = {
                        "total": count,
                        "by_type": by_type,
                        "avg_confidence": float(avg) if avg else 0.0,
                    }
                return result

    # ── Timeline ───────────────────────────────────────────────────

    def append_timeline(self, entry):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO timeline (timestamp, action, domain, rule_id,
                       rule_text, agent, project, decision_context, confidence, sources)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                    (
                        entry.get("timestamp", _now()),
                        entry.get("action", ""),
                        entry.get("domain", ""),
                        entry.get("rule_id", ""),
                        entry.get("rule_text", ""),
                        entry.get("agent", ""),
                        entry.get("project", ""),
                        entry.get("decision_context", ""),
                        entry.get("confidence", 5),
                        json.dumps(entry.get("sources", [])),
                    ),
                )
                conn.commit()
                return _row_to_dict(cur.fetchone(), cur)

    def query_timeline(self, domain=None, project=None, agent=None,
                       date_from=None, date_to=None, action=None, limit=None):
        with self._conn() as conn:
            with conn.cursor() as cur:
                sql = "SELECT * FROM timeline WHERE 1=1"
                params = []

                if domain:
                    sql += " AND domain = %s"
                    params.append(domain)
                if project:
                    sql += " AND project = %s"
                    params.append(project)
                if agent:
                    sql += " AND agent = %s"
                    params.append(agent)
                if action:
                    sql += " AND action = %s"
                    params.append(action)
                if date_from:
                    sql += " AND timestamp >= %s"
                    params.append(date_from)
                if date_to:
                    sql += " AND timestamp <= %s"
                    params.append(date_to)

                sql += " ORDER BY timestamp DESC"
                if limit:
                    sql += " LIMIT %s"
                    params.append(limit)

                cur.execute(sql, params)
                return [_row_to_dict(r, cur) for r in cur.fetchall()]

    def get_timeline_summary(self, period="weekly"):
        intervals = {"daily": "1 day", "weekly": "7 days", "monthly": "30 days"}
        interval = intervals.get(period, "7 days")

        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*), AVG(confidence) FROM timeline "
                    f"WHERE timestamp >= NOW() - INTERVAL '{interval}'"
                )
                row = cur.fetchone()
                return {
                    "period": period,
                    "total_entries": row[0],
                    "avg_confidence": float(row[1]) if row[1] else 0.0,
                }

    # ── Retention ──────────────────────────────────────────────────

    def set_retention(self, rule_id, policy, set_by="", reason=""):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO retention_policies (rule_id, policy, set_at, set_by, reason)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (rule_id) DO UPDATE SET
                       policy = EXCLUDED.policy, set_at = EXCLUDED.set_at,
                       set_by = EXCLUDED.set_by, reason = EXCLUDED.reason
                       RETURNING *""",
                    (rule_id, policy, _now(), set_by, reason),
                )
                conn.commit()
                return _row_to_dict(cur.fetchone(), cur)

    def get_retention(self, rule_id):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT policy FROM retention_policies WHERE rule_id = %s",
                    (rule_id,),
                )
                row = cur.fetchone()
                return row[0] if row else "standard"

    def get_permanent_rules(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT rule_id FROM retention_policies WHERE policy = 'permanent'"
                )
                return [r[0] for r in cur.fetchall()]

    # ── Archive ────────────────────────────────────────────────────

    def archive_rule(self, rule_id, reason="", archived_by=""):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM rules WHERE id = %s", (rule_id,))
                rule = cur.fetchone()
                if not rule:
                    return None
                r = _row_to_dict(rule, cur)
                cur.execute(
                    """INSERT INTO archived_rules (id, domain, rule, rule_type,
                       example, confidence, times_confirmed, times_violated,
                       sources, source_type, created_at, archived_at,
                       archived_by, archive_reason)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (
                        r["id"], r.get("domain", ""), r["rule"],
                        r.get("rule_type", ""), r.get("example", ""),
                        r.get("confidence", 5), r.get("times_confirmed", 0),
                        r.get("times_violated", 0),
                        json.dumps(r.get("sources", [])),
                        r.get("source_type", ""), r.get("created_at", _now()),
                        _now(), archived_by, reason,
                    ),
                )
                cur.execute("DELETE FROM rules WHERE id = %s", (rule_id,))
                conn.commit()
                return _row_to_dict(cur.fetchone(), cur)

    def get_archived_rules(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM archived_rules")
                return [_row_to_dict(r, cur) for r in cur.fetchall()]

    def restore_rule(self, rule_id):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM archived_rules WHERE id = %s", (rule_id,)
                )
                archived = cur.fetchone()
                if not archived:
                    return False
                a = _row_to_dict(archived, cur)
                cur.execute(
                    """INSERT INTO rules (id, domain, rule_type, rule, example,
                       confidence, times_confirmed, times_violated, sources,
                       source_type, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        a["id"], a.get("domain", ""), a.get("rule_type", ""),
                        a["rule"], a.get("example", ""), a.get("confidence", 5),
                        a.get("times_confirmed", 0), a.get("times_violated", 0),
                        json.dumps(a.get("sources", [])),
                        a.get("source_type", ""), a.get("created_at", _now()), _now(),
                    ),
                )
                cur.execute(
                    "DELETE FROM archived_rules WHERE id = %s", (rule_id,)
                )
                conn.commit()
                return True

    # ── Permissions / RBAC ─────────────────────────────────────────

    def set_permission(self, rule_id, clearance,
                       allowed_roles=None, allowed_teams=None):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO permissions (rule_id, clearance, allowed_roles,
                       allowed_teams)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (rule_id) DO UPDATE SET
                       clearance = EXCLUDED.clearance,
                       allowed_roles = EXCLUDED.allowed_roles,
                       allowed_teams = EXCLUDED.allowed_teams
                       RETURNING *""",
                    (
                        rule_id, clearance,
                        json.dumps(allowed_roles or []),
                        json.dumps(allowed_teams or []),
                    ),
                )
                conn.commit()
                return _row_to_dict(cur.fetchone(), cur)

    def get_permission(self, rule_id):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM permissions WHERE rule_id = %s", (rule_id,)
                )
                row = cur.fetchone()
                return _row_to_dict(row, cur) if row else None

    # ── Org Store ──────────────────────────────────────────────────

    def add_org_rule(self, rule):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM org_rules WHERE id = %s", (rule["id"],)
                )
                existing = cur.fetchone()
                now = _now()

                if existing:
                    cur.execute(
                        "UPDATE org_rules SET confidence = LEAST(10, confidence + 1), "
                        "times_confirmed = times_confirmed + 1, "
                        "updated_at = %s WHERE id = %s RETURNING *",
                        (now, rule["id"]),
                    )
                else:
                    cur.execute(
                        """INSERT INTO org_rules (id, domain, rule_type, rule, example,
                           confidence, times_confirmed, sources, source_type,
                           created_at, updated_at, project, tags, scope, retention,
                           author, decision_context)
                           VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           RETURNING *""",
                        (
                            rule["id"],
                            rule.get("domain", "general"),
                            rule.get("rule_type", "convention"),
                            rule["rule"],
                            rule.get("example", ""),
                            rule.get("confidence", 5),
                            json.dumps(rule.get("sources", [])),
                            rule.get("source_type", ""),
                            rule.get("created_at", now),
                            now,
                            rule.get("project", ""),
                            json.dumps(rule.get("tags", [])),
                            rule.get("scope", "org"),
                            rule.get("retention", "standard"),
                            rule.get("author", ""),
                            rule.get("decision_context", ""),
                        ),
                    )
                conn.commit()
                return _row_to_dict(cur.fetchone(), cur)

    def get_org_rules(self, min_confidence=1, project=None, tags=None, scope=None):
        with self._conn() as conn:
            with conn.cursor() as cur:
                sql = "SELECT * FROM org_rules WHERE confidence >= %s"
                params = [min_confidence]

                if project:
                    sql += " AND project = %s"
                    params.append(project)
                if scope:
                    sql += " AND scope = %s"
                    params.append(scope)

                sql += " ORDER BY confidence DESC, times_confirmed DESC"
                cur.execute(sql, params)
                rules = [_row_to_dict(r, cur) for r in cur.fetchall()]

                if tags:
                    rules = [
                        r for r in rules
                        if any(t in json.loads(r.get("tags", "[]")) for t in tags)
                    ]
                return rules

    def search_org(self, query, project=None, tags=None, role=None,
                   limit=None, min_confidence=1):
        with self._conn() as conn:
            with conn.cursor() as cur:
                q = f"%{query}%"
                sql = """SELECT * FROM org_rules WHERE confidence >= %s
                         AND (rule ILIKE %s OR rule_type ILIKE %s
                              OR domain ILIKE %s OR project ILIKE %s
                              OR decision_context ILIKE %s)"""
                params = [min_confidence, q, q, q, q, q]

                if project:
                    sql += " AND project = %s"
                    params.append(project)

                sql += " ORDER BY confidence DESC"
                if limit:
                    sql += " LIMIT %s"
                    params.append(limit)

                cur.execute(sql, params)
                rules = [_row_to_dict(r, cur) for r in cur.fetchall()]

                if tags:
                    rules = [
                        r for r in rules
                        if any(t in json.loads(r.get("tags", "[]")) for t in tags)
                    ]
                if role:
                    rules = [
                        r for r in rules
                        if role in json.loads(r.get("tags", "[]"))
                    ]
                return rules

    def get_cross_project_context(self, project, query, limit=10):
        with self._conn() as conn:
            with conn.cursor() as cur:
                q = f"%{query}%"
                cur.execute(
                    """SELECT * FROM org_rules
                       WHERE project != %s
                       AND (rule ILIKE %s OR rule_type ILIKE %s
                            OR domain ILIKE %s OR decision_context ILIKE %s)
                       ORDER BY confidence DESC
                       LIMIT %s""",
                    (project, q, q, q, q, limit),
                )
                return [_row_to_dict(r, cur) for r in cur.fetchall()]

    def get_org_stats(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM org_rules")
                total = cur.fetchone()[0]

                cur.execute("SELECT COUNT(DISTINCT project) FROM org_rules")
                projects = cur.fetchone()[0]

                cur.execute("SELECT AVG(confidence) FROM org_rules")
                avg = cur.fetchone()[0]

                cur.execute(
                    "SELECT project, COUNT(*) FROM org_rules GROUP BY project"
                )
                by_project = {
                    r[0]: {"count": r[1]} for r in cur.fetchall()
                }

                return {
                    "total_rules": total,
                    "total_projects": projects,
                    "by_project": by_project,
                    "avg_confidence": float(avg) if avg else 0.0,
                }

    # ── Observations ───────────────────────────────────────────────

    def write_observation(self, session_id, observation):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO observations (session_id, domain, context,
                       observation, source)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (
                        session_id,
                        observation.get("domain", ""),
                        observation.get("context", ""),
                        observation.get("observation", ""),
                        observation.get("source", ""),
                    ),
                )
                conn.commit()

    def get_observations(self, session_id, domain=None):
        with self._conn() as conn:
            with conn.cursor() as cur:
                if domain:
                    cur.execute(
                        "SELECT * FROM observations WHERE session_id = %s "
                        "AND domain = %s ORDER BY timestamp",
                        (session_id, domain),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM observations WHERE session_id = %s "
                        "ORDER BY timestamp",
                        (session_id,),
                    )
                return [_row_to_dict(r, cur) for r in cur.fetchall()]

    def count_observations(self, session_id):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM observations WHERE session_id = %s",
                    (session_id,),
                )
                return cur.fetchone()[0]

    def clear_observations(self, session_id, domain=None):
        with self._conn() as conn:
            with conn.cursor() as cur:
                if domain:
                    cur.execute(
                        "DELETE FROM observations WHERE session_id = %s "
                        "AND domain = %s",
                        (session_id, domain),
                    )
                else:
                    cur.execute(
                        "DELETE FROM observations WHERE session_id = %s",
                        (session_id,),
                    )
                conn.commit()

    # ── Blobs ──────────────────────────────────────────────────────

    def write_blob(self, namespace, key, data):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO blobs (namespace, key, data, updated_at)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (namespace, key) DO UPDATE SET
                       data = EXCLUDED.data, updated_at = EXCLUDED.updated_at""",
                    (namespace, key, json.dumps(data), _now()),
                )
                conn.commit()

    def read_blob(self, namespace, key):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM blobs WHERE namespace = %s AND key = %s",
                    (namespace, key),
                )
                row = cur.fetchone()
                return _row_to_dict(row, cur) if row else None

    def list_blobs(self, namespace):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT key FROM blobs WHERE namespace = %s", (namespace,)
                )
                return [r[0] for r in cur.fetchall()]

    def delete_blob(self, namespace, key):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM blobs WHERE namespace = %s AND key = %s",
                    (namespace, key),
                )
                conn.commit()
                return cur.rowcount > 0

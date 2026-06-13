-- Loom: Initial PostgreSQL schema

CREATE TABLE IF NOT EXISTS rules (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL DEFAULT 'general',
    rule_type TEXT NOT NULL DEFAULT 'convention',
    rule TEXT NOT NULL,
    example TEXT DEFAULT '',
    confidence INTEGER DEFAULT 5,
    times_confirmed INTEGER DEFAULT 0,
    times_violated INTEGER DEFAULT 0,
    sources JSONB DEFAULT '[]',
    source_type TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    project TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS timeline (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    action TEXT NOT NULL,
    domain TEXT DEFAULT '',
    rule_id TEXT DEFAULT '',
    rule_text TEXT DEFAULT '',
    agent TEXT DEFAULT '',
    project TEXT DEFAULT '',
    decision_context TEXT DEFAULT '',
    confidence INTEGER DEFAULT 5,
    sources JSONB DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS retention_policies (
    rule_id TEXT PRIMARY KEY REFERENCES rules(id) ON DELETE CASCADE,
    policy TEXT NOT NULL DEFAULT 'standard',
    set_at TIMESTAMPTZ DEFAULT NOW(),
    set_by TEXT DEFAULT '',
    reason TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS archived_rules (
    id TEXT PRIMARY KEY,
    domain TEXT DEFAULT '',
    rule TEXT DEFAULT '',
    rule_type TEXT DEFAULT '',
    example TEXT DEFAULT '',
    confidence INTEGER DEFAULT 5,
    times_confirmed INTEGER DEFAULT 0,
    times_violated INTEGER DEFAULT 0,
    sources JSONB DEFAULT '[]',
    source_type TEXT DEFAULT '',
    created_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ DEFAULT NOW(),
    archived_by TEXT DEFAULT '',
    archive_reason TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS permissions (
    rule_id TEXT PRIMARY KEY REFERENCES rules(id) ON DELETE CASCADE,
    clearance TEXT NOT NULL DEFAULT 'internal',
    allowed_roles JSONB DEFAULT '[]',
    allowed_teams JSONB DEFAULT '[]',
    allowed_agents JSONB DEFAULT '[]',
    owner TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS observations (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    domain TEXT DEFAULT '',
    context TEXT DEFAULT '',
    observation TEXT NOT NULL,
    source TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_observations_session ON observations(session_id);

CREATE TABLE IF NOT EXISTS blobs (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (namespace, key)
);

CREATE TABLE IF NOT EXISTS org_rules (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL DEFAULT 'general',
    rule_type TEXT NOT NULL DEFAULT 'convention',
    rule TEXT NOT NULL,
    example TEXT DEFAULT '',
    confidence INTEGER DEFAULT 5,
    times_confirmed INTEGER DEFAULT 0,
    times_violated INTEGER DEFAULT 0,
    sources JSONB DEFAULT '[]',
    source_type TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    project TEXT DEFAULT '',
    tags JSONB DEFAULT '[]',
    scope TEXT DEFAULT 'org',
    retention TEXT DEFAULT 'standard',
    author TEXT DEFAULT '',
    decision_context TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    key_hash TEXT UNIQUE NOT NULL,
    key_prefix TEXT DEFAULT '',
    project_id TEXT NOT NULL,
    role TEXT DEFAULT 'agent',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO schema_migrations (version) VALUES ('001_initial')
ON CONFLICT (version) DO NOTHING;

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_rules_domain_conf ON rules(domain, confidence DESC);
CREATE INDEX IF NOT EXISTS idx_rules_project ON rules(project);
CREATE INDEX IF NOT EXISTS idx_timeline_project_date ON timeline(project, timestamp);
CREATE INDEX IF NOT EXISTS idx_org_rules_project ON org_rules(project);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);

# Changelog

All notable changes to the Loom project are documented here.

## [1.0.0] - Unreleased

### Major Transformation

- **Observation model**: Generalized knowledge model replacing the old Rule concept. New `Observation` dataclass supports five types: `rule`, `fact`, `decision`, `context`, and `technique` -- each with rich provenance (source URLs, agent, session), tags, and access scoping (public, team, org, private).
- **Semantic search**: Optional `sentence-transformers` integration for embedding-based semantic search with keyword fallback via `HybridSearch`.
- **Security pipeline**: Five security modules integrated throughout the write path -- `Redactor` (PII/secret stripping), `PrivateMode` (no-persistence toggle), `IntegrityGuard` (SHA-256 checksum verification), `AuditLog` (append-only JSONL mutation log with invariant checks), and `AccessControl` (token-based domain read/write/admin scopes).
- **MCP v2 with 7 tools**: Expanded MCP server with `recall_memory`, `store_outcome`, `get_stats`, `record_observation`, `set_private_mode`, `verify_integrity`, and `get_audit_log`. All tools use the new `Observation` model with backward compatibility for old `Rule`-based parameters.
- **FastAPI cloud server**: Optional web server with OAuth 2.1 (GitHub + Google), multi-org management via slugs, REST API for observations CRUD, search, stats, and knowledge graph endpoints.
- **Web dashboard**: React + TypeScript dashboard for viewing, searching, and managing observations with analytics.
- **Integrations framework**: GitHub webhook handler, Slack connector, Linear connector, and Jira connector with configurable ingest routing.
- **Multi-org support**: Organizations with slug-based namespacing, permission management, and user membership.
- **Knowledge Graph**: Explicit relationship tracking between observations (`related_to`, `supersedes`, `contradicts`, `supports`) with bidirectional link traversal.
- **LLM extraction**: Optional AI-powered structured observation extraction from unstructured text using Anthropic or OpenAI APIs.
- **SQLite backend**: Optional SQLite storage backend alongside the default JSON file backend.
- **Category registry**: YAML-driven domain/category configuration with keyword-based detection and classification.
- **Source tracker**: Per-observation provenance recording with unique session IDs.

### Changed

- `RuleStore` and `Rule` are deprecated. All new code should use `ObservationStore` and `Observation`.
- Domain configuration format changed from old-style `rule_types` list to richer `categories` with labels and prompts.
- Store file renamed from `rules.json` to `store.json` with auto-migration on first load.
- `Rule.from_dict()` and `RuleStore` construction now emit `FutureWarning`.

### Removed

- `loom` CLI entry point removed. Use `python -m loom.mcp` instead.
- `loom-server` CLI entry point removed. Use `loom-server` script from `loom.server.api:main` instead.

## [0.2.0] - Initial MCP Server

### Added

- MCP server with 3 tools: `recall_memory`, `store_outcome`, `get_stats`.
- Rule extraction from feedback text via `DomainExtractor` with 8 keyword-based rule types.
- Confidence decay over time via `DecayManager`.
- Five security modules: `Redactor`, `PrivateMode`, `IntegrityGuard`, `AuditLog`, `AccessControl`.
- Engine module with `RuleStore` for JSON-backed persistence.
- Integration test suite with 169 passing tests.
- Domain configuration via YAML files in `.loom/domains/`.
- Auto-bootstrapping of `.loom/` directory on first run.

## [0.1.0] - Initial Release

### Added

- Core project structure and package layout.
- Basic rule store with JSON persistence.
- CLI entry point.
- MIT license.

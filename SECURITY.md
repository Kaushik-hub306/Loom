# Security Policy

Loom stores what your AI agents learn. That makes its security posture part
of *your* security posture — we take reports seriously.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.4.x   | ✅ |
| < 0.4   | ❌ — upgrade; 0.4.0 fixed redaction and access-control gaps |

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Use GitHub's private vulnerability reporting: go to the repository's
**Security** tab → **Report a vulnerability**. You'll get a response as soon
as possible, typically within a few days.

Include: affected version, a minimal reproduction, and impact assessment
(what data could be exposed / modified).

## What Loom does to protect stored memory

- **Secret redaction on every write path** — API keys (Anthropic, OpenAI,
  Stripe, AWS, GitHub, GitLab, Slack, Google, SendGrid, npm, PyPI,
  Hugging Face), JWTs, bearer tokens, PEM blocks, connection-string
  passwords, credential assignments, emails, and IPs are stripped before
  storage. Redaction favors over-matching: a false positive redacts harmless
  text; a false negative leaks a secret.
- **RBAC enforced at read time** — five clearance levels checked against
  the agent identity on every recall/export/timeline read.
- **Private mode** — `LOOM_PRIVATE_MODE=1` blocks all memory writes.
- **Generated `.loom/.gitignore`** — tokens, audit logs, permissions, and
  lock/quarantine files never reach git.
- **Crash-safe storage** — atomic writes with quarantine-on-corruption, so
  partial writes can't silently destroy or mangle stored knowledge.

## Known limitations (honest edges)

- Redaction is pattern-based. Novel or exotic secret formats may pass
  through — treat the memory store with the same care as a log aggregator.
- Local JSON mode trusts the filesystem: anyone with read access to
  `.loom/` can read stored rules. Use file permissions accordingly.
- In cloud mode, your Supabase `service_role` key grants full database
  access — keep the generated config file out of git and restrict its file
  permissions (`chmod 600`).

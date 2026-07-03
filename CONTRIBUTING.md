# Contributing to Loom

Thanks for helping make AI agents remember better. Bug reports, feature
ideas, and PRs are all welcome.

## Development setup

```bash
git clone https://github.com/Kaushik-hub306/Loom.git
cd Loom
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Before you open a PR

All three gates must pass — CI enforces them:

```bash
python -m pytest                        # 159 tests, hermetic (no API keys needed)
ruff check loom/ tests/ conftest.py     # lint
mypy loom/                              # types
```

## Project conventions

The full contributor guide (architecture map + hard rules) lives in
[AGENTS.md](AGENTS.md). The short version:

1. **No stdout prints in library code** — stdout is the MCP JSON-RPC stream;
   diagnostics go to stderr.
2. **All JSON persistence via `loom/storage/jsonio.py`** — atomic writes,
   locks, corruption quarantine.
3. **Every write path redacts secrets** before storage.
4. **Tests are hermetic** — `tmp_path` fixtures, no ambient env dependence.
5. **New MCP tools dispatch through `call_tool()`** so the hook layer
   (auto-context, auto-observe, redaction, private mode) applies.

## Reporting bugs

Open an issue with: what you ran, what you expected, what happened, plus
`loom doctor` output and your Python version. If the bug involves stored
data, include the stderr output — Loom logs storage warnings there.

## Reporting security issues

Please do NOT open a public issue — see [SECURITY.md](SECURITY.md).

## Releasing (maintainers)

1. Bump the version in **both** `loom/__init__.py` and `pyproject.toml`.
2. Add a `CHANGELOG.md` entry.
3. Commit, then tag: `git tag v0.x.y && git push origin v0.x.y`.
4. The publish workflow runs the test matrix and uploads to PyPI via
   Trusted Publishing.

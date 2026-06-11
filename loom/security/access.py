"""Scoped MCP tokens — read, write, admin — stored in tokens.json."""

import enum
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path


TOKENS_FILE = "tokens.json"
_TOKEN_PREFIX = "loom"


class TokenScope(enum.Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


# Ordered: later scopes include earlier ones.
_SCOPE_HIERARCHY = {TokenScope.READ: 0, TokenScope.WRITE: 1, TokenScope.ADMIN: 2}


def _tokens_path(tokens_path: str | Path | None = None) -> Path:
    if tokens_path:
        return Path(tokens_path)
    store_dir = Path(os.environ.get("LOOM_STORE_DIR", Path.cwd() / ".loom"))
    return store_dir / TOKENS_FILE


def _read_tokens(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_tokens(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    path.chmod(0o600)


def generate_token(scope: str, tokens_path: str | Path | None = None) -> str:
    """Create a new scoped token, persist it, and return the bearer string.

    Token format: loom_<scope>_<32-char-random-hex>
    """
    if scope not in (s.value for s in TokenScope):
        raise ValueError(f"Unknown scope '{scope}'. Use one of: read, write, admin.")

    random_part = secrets.token_hex(16)  # 32 hex chars
    token_str = f"{_TOKEN_PREFIX}_{scope}_{random_part}"

    sha = hashlib.sha256(token_str.encode()).hexdigest()

    tpath = _tokens_path(tokens_path)
    tokens = _read_tokens(tpath)
    tokens[sha] = {
        "scope": scope,
        "created": datetime.now(timezone.utc).isoformat(),
        "prefix": f"{_TOKEN_PREFIX}_{scope}_",
    }

    _write_tokens(tpath, tokens)
    return token_str


def verify_token(token: str, tokens_path: str | Path | None = None) -> tuple[bool, TokenScope | None]:
    """Check whether a bearer token is valid and return its scope.

    Returns (valid: bool, scope: TokenScope | None).
    """
    sha = hashlib.sha256(token.encode()).hexdigest()
    tpath = _tokens_path(tokens_path)
    tokens = _read_tokens(tpath)

    entry = tokens.get(sha)
    if not entry:
        return False, None

    try:
        scope = TokenScope(entry["scope"])
    except ValueError:
        return False, None

    return True, scope


def check_access(scope: TokenScope, required: TokenScope) -> bool:
    """Return True when *scope* has sufficient privilege for *required*."""
    return _SCOPE_HIERARCHY.get(scope, -1) >= _SCOPE_HIERARCHY.get(required, 0)

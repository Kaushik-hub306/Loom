"""AccessControl — domain-level access control for multi-agent setups."""

import json
import os
import secrets
from enum import Enum
from pathlib import Path


class TokenScope(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


SCOPE_HIERARCHY = {
    TokenScope.ADMIN: {TokenScope.ADMIN, TokenScope.WRITE, TokenScope.READ},
    TokenScope.WRITE: {TokenScope.WRITE, TokenScope.READ},
    TokenScope.READ: {TokenScope.READ},
}


def check_access(scope: TokenScope, required: TokenScope) -> bool:
    return required in SCOPE_HIERARCHY.get(scope, set())


def generate_token(scope: str, tokens_path: Path) -> str:
    token = f"loom_{scope}_{secrets.token_hex(16)}"
    tokens_path = Path(tokens_path)
    if tokens_path.exists():
        tokens = json.loads(tokens_path.read_text())
    else:
        tokens = {}
    tokens[token] = scope
    tokens_path.parent.mkdir(parents=True, exist_ok=True)
    tokens_path.write_text(json.dumps(tokens, indent=2))
    return token


def verify_token(token: str, tokens_path: Path) -> tuple[bool, TokenScope | None]:
    tokens_path = Path(tokens_path)
    if not tokens_path.exists():
        return False, None
    tokens = json.loads(tokens_path.read_text())
    scope_str = tokens.get(token)
    if scope_str is None:
        return False, None
    try:
        return True, TokenScope(scope_str)
    except ValueError:
        return False, None


class AccessControl:
    """Controls which domains each agent can access."""

    def __init__(self, allowed_domains: list[str] | None = None):
        if allowed_domains is None:
            env_val = os.getenv("LOOM_ALLOWED_DOMAINS", "")
            allowed_domains = [d.strip() for d in env_val.split(",") if d.strip()] if env_val else []
        self.allowed_domains = allowed_domains

    def can_access_domain(self, domain: str) -> bool:
        if not self.allowed_domains:
            return True
        return domain in self.allowed_domains

    def can_access_all(self) -> bool:
        return len(self.allowed_domains) == 0

    def filter_domains(self, domains: list[str]) -> list[str]:
        if not self.allowed_domains:
            return domains
        return [d for d in domains if d in self.allowed_domains]

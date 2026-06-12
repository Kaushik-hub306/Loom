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


class ObservationScope(str, Enum):
    PUBLIC = "public"
    TEAM = "team"
    ORG = "org"
    PRIVATE = "private"


# Scope visibility: which scopes can READ a given scope
OBSERVATION_SCOPE_HIERARCHY: dict[ObservationScope, set[ObservationScope]] = {
    ObservationScope.PUBLIC: {
        ObservationScope.PUBLIC,
        ObservationScope.TEAM,
        ObservationScope.ORG,
        ObservationScope.PRIVATE,
    },
    ObservationScope.TEAM: {ObservationScope.TEAM, ObservationScope.ORG, ObservationScope.PRIVATE},
    ObservationScope.ORG: {ObservationScope.ORG, ObservationScope.PRIVATE},
    ObservationScope.PRIVATE: {ObservationScope.PRIVATE},
}


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


def check_observation_access(
    observation_scope: ObservationScope, token_scope: TokenScope | None
) -> bool:
    """Check whether a token scope can access an observation at the given scope.

    If *token_scope* is None, it defaults to full access (unauthenticated).
    """
    if token_scope is None:
        return True
    # ADMIN can see everything
    if token_scope == TokenScope.ADMIN:
        return True
    # READ and WRITE can only see PUBLIC and TEAM
    return observation_scope in (ObservationScope.PUBLIC, ObservationScope.TEAM)


class AccessControl:
    """Controls which domains each agent can access."""

    def __init__(
        self,
        allowed_domains: list[str] | None = None,
        tokens_path: Path | None = None,
        token: str | None = None,
    ):
        if allowed_domains is None:
            env_val = os.getenv("LOOM_ALLOWED_DOMAINS", "")
            allowed_domains = [d.strip() for d in env_val.split(",") if d.strip()] if env_val else []
        self.allowed_domains = allowed_domains
        self.tokens_path = tokens_path
        self.token = token or os.getenv("LOOM_MCP_TOKEN", "")
        self.token_scope: TokenScope | None = None
        if self.token and self.tokens_path:
            ok, scope = verify_token(self.token, self.tokens_path)
            if ok and scope is not None:
                self.token_scope = scope

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

    def can_read_observation(self, obs_scope: ObservationScope) -> bool:
        """Check whether the current token scope can read an observation."""
        return check_observation_access(obs_scope, self.token_scope)

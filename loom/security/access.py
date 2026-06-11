"""AccessControl — domain-level access control for multi-agent setups."""

import os


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

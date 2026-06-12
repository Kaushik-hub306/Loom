"""SecurityMiddleware — composes all five security modules into a single pipeline.

Provides a unified interface for the MCP server and engine to apply
redaction, private-mode filtering, access control, integrity checks,
and audit logging with a single import.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .redactor import Redactor
from .private_mode import PrivateMode
from .integrity import IntegrityGuard, compute_and_store, verify_store_integrity
from .audit import AuditLog, AuditAction
from .access import AccessControl, ObservationScope, check_observation_access


class SecurityMiddleware:
    """Composes Redactor, PrivateMode, IntegrityGuard, AuditLog, and AccessControl.

    Hooks into the MCP server lifecycle:
    - ``pre_write`` — sanitise input before persisting.
    - ``post_write`` — update integrity checksums and log to the audit trail.
    - ``pre_read`` — enforce domain-level access control.
    """

    def __init__(
        self,
        store_dir: Path,
        audit_log_path: Path | None = None,
        integrity_path: Path | None = None,
        tokens_path: Path | None = None,
        token: str | None = None,
    ):
        store_dir = Path(store_dir)
        store_dir.mkdir(parents=True, exist_ok=True)

        self.store_dir = store_dir

        # ── Component instances ──────────────────────────────────────
        self._redactor = Redactor()
        self._private_mode = PrivateMode()
        self._access = AccessControl(
            tokens_path=tokens_path or (store_dir / "tokens.json"),
            token=token,
        )

        # IntegrityGuard and AuditLog need explicit paths
        self._integrity_path = integrity_path or store_dir
        self._guard = IntegrityGuard()

        self._audit_log_path = audit_log_path or (store_dir / "audit.jsonl")
        self._audit = AuditLog(self._audit_log_path)

    # ── Write pipeline ───────────────────────────────────────────────

    def pre_write(self, observation_data: dict[str, Any]) -> dict[str, Any] | None:
        """Run security checks before an observation is persisted.

        1. Redact secrets from the ``content`` field.
        2. Sanitise feedback for private-mode users.
        3. Check access-control (domain-level).

        Returns the cleaned data dict, or **None** if the write should be
        skipped entirely (private mode active).
        """
        # Private-mode skip check — must come first
        if self._private_mode.should_skip_write():
            return None

        # Redact secrets from content
        if "content" in observation_data and observation_data["content"]:
            observation_data["content"] = self._redactor.redact(
                str(observation_data["content"])
            )

        # Sanitise feedback for private mode
        if "feedback" in observation_data and observation_data["feedback"]:
            observation_data["feedback"] = self._private_mode.sanitize_feedback(
                str(observation_data["feedback"])
            )

        # Also sanitise the primary content field (URLs, paths) in private mode
        if "content" in observation_data and observation_data["content"]:
            observation_data["content"] = self._private_mode.sanitize_feedback(
                str(observation_data["content"])
            )

        # Domain access check
        domain = observation_data.get("domain", "")
        if domain and not self._access.can_access_domain(domain):
            return None

        return observation_data

    def post_write(
        self,
        observation: Any,
        action: str | None = None,
        agent: str = "mcp-server",
    ) -> None:
        """Run post-write security tasks.

        - Update integrity checksums on the store.
        - Log to the audit trail with the appropriate action type.
        """
        # Determine action type based on context
        resolved_action = action or "observation_created"

        # Update integrity checksums
        try:
            compute_and_store(self._integrity_path)
        except Exception:
            pass  # integrity updates are best-effort

        # Audit logging
        try:
            obs_id = getattr(observation, "id", str(observation))
            domain = getattr(observation, "domain", "")
            obs_type = getattr(observation, "observation_type", "")
        except Exception:
            obs_id = str(observation)
            domain = ""
            obs_type = ""

        self._audit.record(
            action=resolved_action,
            details={
                "observation_id": obs_id,
                "domain": domain,
                "observation_type": obs_type,
                "agent": agent,
            },
        )

    # ── Read pipeline ────────────────────────────────────────────────

    def pre_read(self, domain: str) -> bool:
        """Check whether the caller is allowed to read from *domain*.

        Returns *True* if access is permitted, *False* otherwise.
        """
        return self._access.can_access_domain(domain)

    # ── Integrity ────────────────────────────────────────────────────

    def verify_integrity(self) -> tuple[bool, str]:
        """Verify the integrity of the observation store.

        Returns a ``(passed, message)`` tuple.
        """
        try:
            return verify_store_integrity(self._integrity_path)
        except Exception as e:
            return False, f"Integrity verification failed: {e}"

    # ── Audit ────────────────────────────────────────────────────────

    def get_audit_entries(self, limit: int = 100) -> list[dict]:
        """Return the most recent audit trail entries."""
        try:
            return self._audit.read(limit=limit)
        except Exception:
            return []

    # ── Private mode ─────────────────────────────────────────────────

    def set_private_mode(self, enabled: bool) -> None:
        """Toggle private mode for the current session."""
        self._private_mode.set_mode(enabled)

    @property
    def is_private(self) -> bool:
        """Return True if private mode is currently active."""
        return self._private_mode.is_active

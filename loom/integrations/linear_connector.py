"""Linear connector — parses Linear webhook payloads into observations.

No Linear SDK required.  Payload verification uses HMAC-SHA256 as configured
in the Linear webhook settings.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any


@dataclass
class LinearWebhookHandler:
    """Parses Linear webhook payloads into observations.

    Parameters
    ----------
    webhook_secret:
        The signing secret configured in Linear webhook settings.  If ``None``,
        verification is skipped.
    """

    webhook_secret: str | None = None

    # ── signature verification ────────────────────────────────────────────

    def verify_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """Verify a Linear webhook signature.

        Parameters
        ----------
        payload_body:
            Raw request body bytes.
        signature_header:
            The ``Linear-Signature`` header value.

        Returns
        -------
        bool
            ``True`` if the signature matches.
        """
        if not self.webhook_secret:
            return True
        if not signature_header:
            return False
        expected = hmac.new(
            self.webhook_secret.encode(), payload_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    # ── event parsing ─────────────────────────────────────────────────────

    def parse_event(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse a Linear webhook payload into observation dicts.

        Parameters
        ----------
        payload:
            Parsed JSON payload from the Linear webhook.

        Returns
        -------
        list[dict]
            Observation dicts extracted from the payload.
        """
        action = payload.get("action", "")
        data = payload.get("data", {})
        results: list[dict[str, Any]] = []

        if action in ("create", "update"):
            item_type = payload.get("type", "")
            title = data.get("title", "")
            description = data.get("description", "")
            text = title
            if description:
                text = f"{title}\n{description}"
            if text.strip():
                team_name = (data.get("team") or {}).get("name", "")
                results.append(
                    {
                        "source": "linear",
                        "event": action,
                        "domain": "coding",  # Default; IngestRouter re-routes
                        "observation_type": "context",
                        "raw_text": text,
                        "metadata": {
                            "team": team_name,
                            "type": item_type,
                            "url": data.get("url", ""),
                            "creator": (data.get("creator") or {}).get("name", ""),
                        },
                    }
                )

        return results

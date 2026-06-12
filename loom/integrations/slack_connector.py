"""Slack connector — parses Slack events and messages into observations.

No Slack SDK required.  Event payload verification uses the signing secret
as documented in the Slack Events API.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class SlackConnector:
    """Parses Slack events and channel messages into observations.

    Parameters
    ----------
    signing_secret:
        The Slack signing secret for request verification.  If ``None``,
        verification is skipped (useful for local dev).
    """

    signing_secret: str | None = None

    # ── signature verification ────────────────────────────────────────────

    def verify_request(
        self, body: bytes, timestamp: str, signature_header: str
    ) -> bool:
        """Verify a Slack signed request.

        Parameters
        ----------
        body:
            Raw request body bytes.
        timestamp:
            The ``X-Slack-Request-Timestamp`` header value.
        signature_header:
            The ``X-Slack-Signature`` header value (e.g. ``"v0=abc123..."``).

        Returns
        -------
        bool
            ``True`` if the signature is valid.
        """
        if not self.signing_secret:
            return True
        if not timestamp or not signature_header:
            return False
        # Prevent replay attacks — reject stale timestamps
        try:
            ts = int(timestamp)
            if abs(time.time() - ts) > 60 * 5:
                return False
        except (ValueError, TypeError):
            return False
        sig_basestring = f"v0:{timestamp}:{body.decode()}"
        expected = (
            "v0="
            + hmac.new(
                self.signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )
        return hmac.compare_digest(expected, signature_header)

    # ── message parsing ───────────────────────────────────────────────────

    def parse_message(
        self, channel: str, text: str, user: str = ""
    ) -> dict[str, Any] | None:
        """Parse a Slack message into an observation dict.

        Parameters
        ----------
        channel:
            The channel name (e.g. ``"#sales"``, ``"#eng"``).
        text:
            The message text.
        user:
            The Slack user ID or display name.

        Returns
        -------
        dict or None
            An observation dict, or ``None`` if the message has no text.
        """
        clean_text = text.strip()
        if not clean_text:
            return None
        # Strip the channel '#' prefix if present
        channel_name = channel.lstrip("#")

        return {
            "source": "slack",
            "event": "message",
            "domain": "coding",  # Default; IngestRouter will re-route
            "observation_type": "context",
            "raw_text": clean_text,
            "metadata": {
                "channel": channel_name,
                "user": user,
            },
        }

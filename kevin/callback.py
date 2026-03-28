"""HTTP callback client for Executor-as-a-Service mode.

Kevin calls back to the Edge Function to report run status changes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)


class CallbackClient:
    """Sends HMAC-signed status updates to the Edge Function callback endpoint."""

    def __init__(self, *, callback_url: str, callback_secret: str) -> None:
        self._url = callback_url
        self._secret = callback_secret

    def report_status(
        self,
        *,
        run_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Send a status update to the callback URL. No-op if URL is empty."""
        if not self._url:
            return

        payload: dict[str, Any] = {"run_id": run_id, "status": status}
        if result is not None:
            payload["result"] = result
        if error_code:
            payload["error_code"] = error_code
        if error_message:
            payload["error_message"] = error_message

        body = json.dumps(payload)
        signature = self._sign(body)

        req = urllib.request.Request(
            self._url,
            data=body.encode(),
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                log.info("Callback %s → %s (HTTP %d)", run_id, status, resp.status)
        except (urllib.error.URLError, OSError) as exc:
            log.warning("Callback failed for %s: %s", run_id, exc)

    def _sign(self, body: str) -> str:
        return hmac.new(
            self._secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()

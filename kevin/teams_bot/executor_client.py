"""Lightweight client for Kevin Executor Edge Function.

Used by the Teams Bot to dispatch blueprints and check status
without going through GitHub Issues.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


def _base_url() -> str:
    return os.environ.get("EXECUTOR_BASE_URL", "")


def _api_key() -> str:
    return os.environ.get("EXECUTOR_API_KEY", "")


def _request(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    """Make an authenticated request to the executor API."""
    url = f"{_base_url()}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def is_configured() -> bool:
    """Return True if executor env vars are set."""
    return bool(_base_url()) and bool(_api_key())


def execute(blueprint_id: str, instruction: str, *, repo: str = "", ref: str = "main") -> dict[str, Any]:
    """Submit a task to the executor. Returns {run_id, status}."""
    body: dict[str, Any] = {
        "blueprint_id": blueprint_id,
        "instruction": instruction,
    }
    if repo:
        body["context"] = {"repo": repo, "ref": ref}
    return _request("POST", "/execute", body)


def get_status(run_id: str) -> dict[str, Any]:
    """Get the status of a run."""
    return _request("GET", f"/status/{run_id}")


def list_runs(limit: int = 10) -> list[dict[str, Any]]:
    """List recent runs."""
    data = _request("GET", f"/status?limit={limit}")
    return data.get("runs", [])


def cancel_run(run_id: str) -> dict[str, Any]:
    """Cancel a running or pending run."""
    return _request("POST", "/cancel", {"run_id": run_id})

"""Dashboard page: Remote Runs — fetches run status from Edge Function API."""

from __future__ import annotations

import os
from typing import Any

import streamlit as st


def _fetch_runs(base_url: str, api_key: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch recent runs from the executor status API."""
    import urllib.request
    import json

    req = urllib.request.Request(
        f"{base_url}/status?limit={limit}",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("runs", [])
    except Exception as exc:
        st.error(f"Failed to fetch remote runs: {exc}")
        return []


def _fetch_run_detail(base_url: str, api_key: str, run_id: str) -> dict[str, Any] | None:
    """Fetch a single run's detail."""
    import urllib.request
    import json

    req = urllib.request.Request(
        f"{base_url}/status/{run_id}",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def render() -> None:
    """Render the Remote Runs dashboard page."""
    from kevin.dashboard.components.status_badge import render_status_badge

    st.header("Remote Runs (Executor API)")

    base_url = os.environ.get("EXECUTOR_BASE_URL", "")
    api_key = os.environ.get("EXECUTOR_API_KEY", "")

    if not base_url or not api_key:
        st.warning(
            "Set `EXECUTOR_BASE_URL` and `EXECUTOR_API_KEY` environment variables "
            "to connect to the remote executor."
        )
        return

    runs = _fetch_runs(base_url, api_key)
    if not runs:
        st.info("No remote runs found.")
        return

    # Summary metrics
    statuses = [r["status"] for r in runs]
    cols = st.columns(4)
    cols[0].metric("Total", len(runs))
    cols[1].metric("Completed", statuses.count("completed"))
    cols[2].metric("Failed", statuses.count("failed"))
    cols[3].metric("Running", statuses.count("running") + statuses.count("dispatched"))

    # Run table
    st.subheader("Recent Runs")
    for run in runs:
        badge = render_status_badge(run["status"])
        col1, col2, col3 = st.columns([3, 5, 2])
        col1.markdown(badge, unsafe_allow_html=True)
        col2.text(f"{run['blueprint_id']}  —  {run['instruction'][:60]}")
        col3.text(run["created_at"][:19])

        # Expandable detail
        with st.expander(f"Details: {run['run_id'][:8]}..."):
            detail = _fetch_run_detail(base_url, api_key, run["run_id"])
            if detail:
                st.json(detail)

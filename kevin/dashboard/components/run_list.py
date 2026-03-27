"""Page 1: Run list with summary metrics and clickable table."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from kevin.dashboard.data_loader import list_runs


STATUS_ICONS = {
    "completed": ":white_check_mark:",
    "failed": ":x:",
    "running": ":arrows_counterclockwise:",
    "pending": ":hourglass_flowing_sand:",
}


def render(state_dir: Path) -> None:
    st.header("Kevin Runs")

    runs = list_runs(state_dir)
    if not runs:
        st.info("No runs found. Run `python -m kevin.dashboard.seed` to generate demo data.")
        return

    # Metric cards
    total = len(runs)
    passed = sum(1 for r in runs if r.status == "completed")
    failed = sum(1 for r in runs if r.status == "failed")
    running = sum(1 for r in runs if r.status == "running")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Runs", total)
    col2.metric("Completed", passed)
    col3.metric("Failed", failed)
    col4.metric("Running", running)

    st.divider()

    # Run table
    for run in runs:
        status_icon = STATUS_ICONS.get(run.status, ":question:")
        elapsed = f"{run.elapsed_seconds:.0f}s" if run.elapsed_seconds is not None else "—"
        progress = f"{run.blocks_passed}/{run.blocks_total}"

        col_id, col_bp, col_issue, col_status, col_progress, col_time, col_elapsed = st.columns(
            [2, 3, 1, 1, 1, 2, 1]
        )
        col_id.code(run.run_id, language=None)
        col_bp.write(run.blueprint_id)
        col_issue.write(f"#{run.issue_number}")
        col_status.write(status_icon)
        col_progress.write(progress)
        col_time.write(run.started_at[:19] if run.started_at else "—")
        col_elapsed.write(elapsed)

        if col_id.button("View", key=f"view_{run.run_id}"):
            st.session_state["selected_run_id"] = run.run_id
            st.session_state["_page"] = "Run Detail"
            st.rerun()

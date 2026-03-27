"""Page 2: Run detail with Mermaid pipeline, Gantt chart, and logs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import plotly.figure_factory as ff
import streamlit as st
from streamlit_mermaid import st_mermaid

from kevin.dashboard.data_loader import BlockInfo, load_block_log, load_run, list_runs


STATUS_COLORS = {
    "passed": "#28a745",
    "failed": "#dc3545",
    "running": "#007bff",
    "pending": "#6c757d",
}

STATUS_MERMAID_CLASS = {
    "passed": "passed",
    "failed": "failed",
    "running": "running",
    "pending": "pending",
}


def render(state_dir: Path) -> None:
    st.header("Run Detail")

    runs = list_runs(state_dir)
    if not runs:
        st.info("No runs found.")
        return

    run_ids = [r.run_id for r in runs]
    default_idx = 0
    if "selected_run_id" in st.session_state and st.session_state["selected_run_id"] in run_ids:
        default_idx = run_ids.index(st.session_state["selected_run_id"])

    selected_id = st.selectbox("Select Run", run_ids, index=default_idx)
    if not selected_id:
        return

    detail = load_run(state_dir, selected_id)

    # Metadata
    meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
    meta_col1.metric("Blueprint", detail.blueprint_id)
    meta_col2.metric("Issue", f"#{detail.issue_number}")
    meta_col3.metric("Repo", detail.repo)
    meta_col4.metric("Status", detail.status)

    st.divider()

    # Mermaid pipeline
    st.subheader("Block Pipeline")
    mermaid_code = _build_mermaid(detail.blocks)
    st_mermaid(mermaid_code, height=200)

    # Gantt chart
    gantt_data = _build_gantt_data(detail.blocks)
    if gantt_data:
        st.subheader("Execution Timeline")
        fig = ff.create_gantt(
            gantt_data,
            colors={s: c for s, c in STATUS_COLORS.items()},
            index_col="Status",
            show_colorbar=True,
            showgrid_x=True,
            showgrid_y=True,
        )
        fig.update_layout(height=250, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

    # Block details
    st.subheader("Block Details")
    for block in detail.blocks:
        status_emoji = {"passed": "✅", "failed": "❌", "running": "🔄", "pending": "⏳"}.get(
            block.status, "❓"
        )
        with st.expander(f"{status_emoji} {block.block_id}: {block.name} — {block.status}"):
            info_col1, info_col2, info_col3, info_col4 = st.columns(4)
            info_col1.write(f"**Runner:** `{block.runner}`")
            info_col2.write(f"**Exit Code:** `{block.exit_code}`")
            info_col3.write(f"**Retries:** {block.retries}")
            info_col4.write(f"**Error:** {block.error or '—'}")

            if block.validator_results:
                st.write("**Validators:**")
                for v in block.validator_results:
                    v_icon = "✅" if v.get("passed") else "❌"
                    st.write(f"  {v_icon} `{v.get('type', 'unknown')}`")

            log_content = load_block_log(state_dir, selected_id, block.block_id)
            if log_content:
                st.code(log_content, language="text")


def _build_mermaid(blocks: list[BlockInfo]) -> str:
    """Build a Mermaid flowchart from blocks."""
    lines = ["graph LR"]
    for block in blocks:
        cls = STATUS_MERMAID_CLASS.get(block.status, "pending")
        label = f"{block.block_id}: {block.name}"
        lines.append(f'    {block.block_id}["{label}"]:::{cls}')

    for i in range(len(blocks) - 1):
        lines.append(f"    {blocks[i].block_id} --> {blocks[i + 1].block_id}")

    lines.append("    classDef passed fill:#28a745,stroke:#1e7e34,color:white")
    lines.append("    classDef failed fill:#dc3545,stroke:#bd2130,color:white")
    lines.append("    classDef running fill:#007bff,stroke:#0069d9,color:white")
    lines.append("    classDef pending fill:#6c757d,stroke:#5a6268,color:white")
    return "\n".join(lines)


def _build_gantt_data(blocks: list[BlockInfo]) -> list[dict]:
    """Build Plotly Gantt chart data from blocks."""
    data = []
    for block in blocks:
        if not block.started_at:
            continue
        start = block.started_at
        finish = block.completed_at if block.completed_at else datetime.now().isoformat()
        data.append({
            "Task": f"{block.block_id}: {block.name}",
            "Start": start,
            "Finish": finish,
            "Status": block.status,
        })
    return data

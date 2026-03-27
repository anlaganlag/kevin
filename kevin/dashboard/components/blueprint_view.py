"""Page 3: Blueprint viewer with dependency graph and block table."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit_mermaid import st_mermaid

from kevin.dashboard.data_loader import BlueprintInfo, list_blueprints


def render(blueprints_dir: Path) -> None:
    st.header("Blueprints")

    blueprints = list_blueprints(blueprints_dir)
    if not blueprints:
        st.info(f"No blueprints found in `{blueprints_dir}`.")
        return

    bp_names = [f"{bp.blueprint_id} ({bp.blueprint_name})" for bp in blueprints]
    selected_idx = st.selectbox(
        "Select Blueprint",
        range(len(bp_names)),
        format_func=lambda i: bp_names[i],
    )

    bp = blueprints[selected_idx]

    # Metadata
    meta_col1, meta_col2, meta_col3 = st.columns(3)
    meta_col1.metric("Version", bp.version)
    meta_col2.metric("Blocks", bp.block_count)
    meta_col3.write(f"**Tags:** {', '.join(bp.tags)}")

    st.divider()

    # Dependency graph
    st.subheader("Block Dependency Graph")
    mermaid_code = _build_dependency_graph(bp)
    st_mermaid(mermaid_code, height=250)

    # Block table
    st.subheader("Block Definitions")
    table_data = []
    for block in bp.blocks:
        table_data.append({
            "Block ID": block.block_id,
            "Name": block.name,
            "Runner": block.runner,
            "Dependencies": ", ".join(block.dependencies) if block.dependencies else "—",
            "Timeout": f"{block.timeout}s",
            "Max Retries": block.max_retries,
            "Validators": ", ".join(block.validators) if block.validators else "—",
        })

    st.dataframe(table_data, use_container_width=True, hide_index=True)


def _build_dependency_graph(bp: BlueprintInfo) -> str:
    """Build a Mermaid flowchart from blueprint block dependencies."""
    lines = ["graph LR"]
    for block in bp.blocks:
        label = f"{block.block_id}: {block.name}"
        lines.append(f'    {block.block_id}["{label}"]')

    # Add edges based on explicit dependencies
    for block in bp.blocks:
        for dep in block.dependencies:
            lines.append(f"    {dep} --> {block.block_id}")

    # If no explicit dependencies exist, chain sequentially
    has_deps = any(len(b.dependencies) > 0 for b in bp.blocks)
    if not has_deps and len(bp.blocks) > 1:
        for i in range(len(bp.blocks) - 1):
            lines.append(f"    {bp.blocks[i].block_id} --> {bp.blocks[i + 1].block_id}")

    lines.append("    classDef default fill:#4a90d9,stroke:#357abd,color:white")
    return "\n".join(lines)

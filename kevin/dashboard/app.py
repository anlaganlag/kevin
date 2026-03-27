"""Kevin Dashboard — Streamlit entry point.

Usage:
    streamlit run kevin/dashboard/app.py -- --kevin-root . --blueprints-dir blueprints
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import streamlit as st


def parse_args() -> argparse.Namespace:
    """Parse CLI args passed after `--`."""
    parser = argparse.ArgumentParser(description="Kevin Dashboard")
    parser.add_argument("--kevin-root", default=".", help="Project root with .kevin/runs/")
    parser.add_argument("--blueprints-dir", default="blueprints", help="Blueprints directory")
    args, _ = parser.parse_known_args(sys.argv[1:])
    return args


def main() -> None:
    args = parse_args()
    kevin_root = Path(args.kevin_root).resolve()
    blueprints_dir = Path(args.blueprints_dir).resolve()
    state_dir = kevin_root / ".kevin" / "runs"

    st.set_page_config(
        page_title="Kevin Dashboard",
        page_icon=":robot_face:",
        layout="wide",
    )

    st.session_state["state_dir"] = state_dir
    st.session_state["blueprints_dir"] = blueprints_dir

    st.sidebar.title("Kevin Dashboard")
    page = st.sidebar.radio(
        "Navigation",
        ["Run List", "Run Detail", "Blueprints"],
        label_visibility="collapsed",
    )

    if not state_dir.exists():
        st.sidebar.warning(
            f"No runs found at `{state_dir}`.\n\n"
            "Run `python -m kevin.dashboard.seed` to generate demo data."
        )

    if page == "Run List":
        from kevin.dashboard.components.run_list import render
        render(state_dir)
    elif page == "Run Detail":
        from kevin.dashboard.components.run_detail import render
        render(state_dir)
    elif page == "Blueprints":
        from kevin.dashboard.components.blueprint_view import render
        render(blueprints_dir)


main()

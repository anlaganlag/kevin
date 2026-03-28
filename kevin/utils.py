"""Shared utilities used by scheduler and agent_runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kevin.prompt_template import render


def resolve_cwd(runner_config: dict[str, Any], variables: dict[str, str]) -> Path:
    """Resolve the working directory from runner_config or default to cwd.

    Shared between scheduler (cwd conflict detection) and agent_runner (execution).
    """
    cwd_raw = runner_config.get("cwd", "")
    if cwd_raw:
        return Path(render(cwd_raw, variables)).resolve()
    return Path.cwd().resolve()

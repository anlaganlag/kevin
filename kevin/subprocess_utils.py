"""Subprocess execution for Kevin — run to completion (no in-process timeout or silence watchdog)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SubprocessResult:
    """Outcome of ``run_with_heartbeat`` (name kept for call-site compatibility)."""

    success: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""


def run_with_heartbeat(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> SubprocessResult:
    """Run *cmd* until the process exits. *timeout* is ignored (blueprints still pass it)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=None,
        )
    except FileNotFoundError as exc:
        return SubprocessResult(
            success=False,
            stderr=f"Command not found: {exc}",
        )
    return SubprocessResult(
        success=proc.returncode == 0,
        exit_code=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )

"""Subprocess execution for Kevin — streaming output with optional progress callback."""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


ProgressCallback = Callable[[str], None]
"""Called with each stdout line as the subprocess produces it."""


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
    on_progress: ProgressCallback | None = None,
) -> SubprocessResult:
    """Run *cmd* streaming stdout line-by-line.

    When *on_progress* is provided, each stdout line is forwarded to the
    callback in real time (for Teams/Dashboard progress updates).
    Falls back to batch mode when no callback is given.
    """
    if on_progress is None:
        return _run_batch(cmd, cwd=cwd)
    return _run_streaming(cmd, cwd=cwd, on_progress=on_progress)


def _run_batch(cmd: list[str], *, cwd: Path) -> SubprocessResult:
    """Original batch execution — collect all output at once."""
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


def _run_streaming(
    cmd: list[str],
    *,
    cwd: Path,
    on_progress: ProgressCallback,
) -> SubprocessResult:
    """Stream stdout line-by-line, forwarding each to *on_progress*."""
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        return SubprocessResult(
            success=False,
            stderr=f"Command not found: {exc}",
        )

    if proc.stdout is None:
        proc.wait()
        return SubprocessResult(success=False, stderr="stdout pipe not available")

    # Drain stderr in a background thread to avoid deadlock when the
    # stderr pipe buffer fills up while we're blocked reading stdout.
    stderr_chunks: list[str] = []
    stderr_thread = threading.Thread(
        target=lambda: stderr_chunks.append(proc.stderr.read() if proc.stderr else ""),
        daemon=True,
    )
    stderr_thread.start()

    stdout_lines: list[str] = []
    for line in proc.stdout:
        stdout_lines.append(line)
        try:
            on_progress(line.rstrip("\n"))
        except Exception:
            pass  # callback failure never kills execution

    stderr_thread.join(timeout=5)
    proc.wait()

    return SubprocessResult(
        success=proc.returncode == 0,
        exit_code=proc.returncode,
        stdout="".join(stdout_lines),
        stderr=stderr_chunks[0] if stderr_chunks else "",
    )

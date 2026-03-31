"""Subprocess execution with heartbeat watchdog (avoids silent hangs in CI)."""

from __future__ import annotations

import os
import selectors
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Claude CLI can go quiet during extended thinking; keep generous.
HEARTBEAT_TIMEOUT_SECONDS = 600

# Progress lines (parent stderr) so CI logs show the subprocess is still alive.
_DEFAULT_PROGRESS_INTERVAL = 60


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _heartbeat_cap_seconds() -> int:
    """Max silence (no child stdout/stderr) before kill. Override via KEVIN_SUBPROCESS_HEARTBEAT_SECONDS."""
    return _int_env("KEVIN_SUBPROCESS_HEARTBEAT_SECONDS", HEARTBEAT_TIMEOUT_SECONDS) or HEARTBEAT_TIMEOUT_SECONDS


def _progress_log_interval_seconds() -> int:
    """Emit [kevin] still waiting... every N seconds to stderr; 0 disables."""
    return _int_env("KEVIN_SUBPROCESS_PROGRESS_INTERVAL", _DEFAULT_PROGRESS_INTERVAL)


@dataclass
class SubprocessResult:
    """Outcome of ``run_with_heartbeat``."""

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
    """Run *cmd* with non-blocking I/O; kill if silent for too long or *timeout* exceeded."""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(cwd),
        )
    except FileNotFoundError as exc:
        return SubprocessResult(
            success=False,
            stderr=f"Command not found: {exc}",
        )

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    start_time = time.monotonic()
    last_output_time = start_time
    heartbeat_cap = _heartbeat_cap_seconds()
    heartbeat_limit = min(heartbeat_cap, timeout)
    progress_interval = _progress_log_interval_seconds()
    last_progress_log = start_time

    sel = selectors.DefaultSelector()
    try:
        if proc.stdout:
            sel.register(proc.stdout, selectors.EVENT_READ, "stdout")
        if proc.stderr:
            sel.register(proc.stderr, selectors.EVENT_READ, "stderr")

        while sel.get_map():
            now = time.monotonic()
            elapsed = now - start_time
            if progress_interval > 0 and (now - last_progress_log) >= progress_interval:
                silence_s = now - last_output_time
                print(
                    f"[kevin] subprocess still running: elapsed={elapsed:.0f}s, "
                    f"no child output for {silence_s:.0f}s (silence limit {heartbeat_limit}s, "
                    f"hard timeout {timeout}s)",
                    file=sys.stderr,
                    flush=True,
                )
                last_progress_log = now

            if elapsed > timeout:
                proc.kill()
                proc.wait()
                return SubprocessResult(
                    success=False,
                    exit_code=proc.returncode,
                    stdout="".join(stdout_chunks),
                    stderr=f"Timeout after {timeout}s\n{''.join(stderr_chunks)}",
                )

            silence = now - last_output_time
            if silence > heartbeat_limit:
                proc.kill()
                proc.wait()
                return SubprocessResult(
                    success=False,
                    exit_code=proc.returncode,
                    stdout="".join(stdout_chunks),
                    stderr=(
                        f"Heartbeat timeout: no output for {heartbeat_limit}s\n"
                        f"{''.join(stderr_chunks)}"
                    ),
                )

            ready = sel.select(timeout=1.0)
            for key, _ in ready:
                chunk = (
                    key.fileobj.read1(8192)
                    if hasattr(key.fileobj, "read1")
                    else key.fileobj.readline()
                )
                if chunk:
                    if key.data == "stdout":
                        stdout_chunks.append(chunk)
                    else:
                        stderr_chunks.append(chunk)
                    last_output_time = time.monotonic()
                else:
                    sel.unregister(key.fileobj)

        proc.wait()
        return SubprocessResult(
            success=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout="".join(stdout_chunks),
            stderr="".join(stderr_chunks),
        )

    except Exception as exc:
        proc.kill()
        proc.wait()
        return SubprocessResult(
            success=False,
            exit_code=proc.returncode,
            stdout="".join(stdout_chunks),
            stderr=f"Unexpected error: {exc}",
        )
    finally:
        sel.close()

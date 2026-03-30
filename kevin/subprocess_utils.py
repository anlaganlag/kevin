"""Heartbeat-monitored subprocess execution.

Extracted from agent_runner for reuse by both block runner and agentic executor.
"""

from __future__ import annotations

import selectors
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

# Seconds of silence before the heartbeat watchdog kills a subprocess.
# Claude CLI can think for a while (extended thinking), so this needs to be generous.
DEFAULT_HEARTBEAT_TIMEOUT = 600


@dataclass
class SubprocessResult:
    """Generic result from a heartbeat-monitored subprocess."""

    success: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""


def run_with_heartbeat(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
    heartbeat_timeout: int = DEFAULT_HEARTBEAT_TIMEOUT,
) -> SubprocessResult:
    """Run a subprocess with non-blocking I/O and heartbeat watchdog.

    Uses selectors to monitor both stdout and stderr without blocking.
    If no output on either stream for *heartbeat_timeout* seconds, the
    process is killed (prevents "fake death" in CI environments like GHA).
    """
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
    heartbeat_limit = min(heartbeat_timeout, timeout)

    sel = selectors.DefaultSelector()
    try:
        if proc.stdout:
            sel.register(proc.stdout, selectors.EVENT_READ, "stdout")
        if proc.stderr:
            sel.register(proc.stderr, selectors.EVENT_READ, "stderr")

        while sel.get_map():
            elapsed = time.monotonic() - start_time
            if elapsed > timeout:
                proc.kill()
                proc.wait()
                return SubprocessResult(
                    success=False,
                    stdout="".join(stdout_chunks),
                    stderr=f"Timeout after {timeout}s\n{''.join(stderr_chunks)}",
                )

            silence = time.monotonic() - last_output_time
            if silence > heartbeat_limit:
                proc.kill()
                proc.wait()
                return SubprocessResult(
                    success=False,
                    stdout="".join(stdout_chunks),
                    stderr=f"Heartbeat timeout: no output for {heartbeat_limit}s\n{''.join(stderr_chunks)}",
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
            stderr=f"Unexpected error: {exc}",
        )
    finally:
        sel.close()

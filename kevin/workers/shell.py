"""ShellWorker — executes bash commands behind the WorkerInterface."""

from __future__ import annotations

import time

from kevin.subprocess_utils import run_with_heartbeat
from kevin.workers.interface import FailureType, WorkerHealth, WorkerResult, WorkerTask


class ShellWorker:
    """Worker adapter that runs shell commands via ``bash -c``."""

    @property
    def worker_id(self) -> str:
        return "shell"

    def execute(self, task: WorkerTask) -> WorkerResult:
        """Run *task.instruction* as a bash command and return a WorkerResult."""
        start = time.monotonic()
        sub = run_with_heartbeat(
            ["bash", "-c", task.instruction],
            cwd=task.workspace.cwd,
            timeout=task.timeout,
        )
        duration = time.monotonic() - start

        if sub.success:
            return WorkerResult(
                success=True,
                exit_code=sub.exit_code,
                stdout=sub.stdout,
                stderr=sub.stderr,
                duration_seconds=duration,
            )

        failure_type = _classify_failure(sub.stderr)
        return WorkerResult(
            success=False,
            exit_code=sub.exit_code,
            failure_type=failure_type,
            failure_detail=sub.stderr.strip()[:500],
            stdout=sub.stdout,
            stderr=sub.stderr,
            duration_seconds=duration,
        )

    def health_check(self) -> WorkerHealth:
        """Shell is always available."""
        return WorkerHealth(
            available=True,
            worker_id="shell",
            version="builtin",
            capabilities=["shell_execute"],
        )


def _classify_failure(stderr: str) -> FailureType:
    """Map stderr patterns to a FailureType."""
    lower = stderr.lower()
    if "timeout" in lower:
        return FailureType.TIMEOUT
    if "heartbeat" in lower:
        return FailureType.HEARTBEAT_TIMEOUT
    if "command not found" in lower:
        return FailureType.COMMAND_NOT_FOUND
    return FailureType.EXIT_CODE_NON_ZERO

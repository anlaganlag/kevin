"""ClaudeCodeWorker — Claude CLI adapter behind WorkerInterface."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from kevin.subprocess_utils import run_with_heartbeat
from kevin.workers.interface import (
    ArtifactType,
    FailureType,
    WorkerArtifact,
    WorkerHealth,
    WorkerPermissions,
    WorkerResult,
    WorkerTask,
)

_EXECUTOR_PREFIX = (
    "You are Kevin Executor, an autonomous software development agent.\n"
    "Complete the following task end-to-end.\n"
    "You MUST create files and execute commands. "
    "Do NOT ask questions or wait for confirmation. Just execute.\n\n"
)

_PR_URL_PATTERN = re.compile(r"github\.com/[^/]+/[^/]+/pull/(\d+)")


class ClaudeCodeWorker:
    """Wraps the Claude CLI behind the WorkerInterface contract."""

    @property
    def worker_id(self) -> str:
        return "claude-code"

    def execute(self, task: WorkerTask) -> WorkerResult:
        prompt = self._translate_instruction(task)
        tools = self._translate_permissions(task.permissions)

        cmd: list[str] = ["claude", "-p", prompt, "--verbose", "--allowedTools", tools]
        if task.model:
            cmd.extend(["--model", task.model])

        claudeignore_path = self._write_claudeignore(task)

        start = time.monotonic()
        try:
            sub_result = run_with_heartbeat(
                cmd,
                cwd=task.workspace.cwd,
                timeout=task.timeout,
            )
        finally:
            self._cleanup_claudeignore(claudeignore_path)

        duration = time.monotonic() - start

        if sub_result.success:
            return WorkerResult(
                success=True,
                exit_code=sub_result.exit_code,
                stdout=sub_result.stdout,
                stderr=sub_result.stderr,
                duration_seconds=duration,
                artifacts=self._extract_artifacts(sub_result.stdout),
            )

        failure_type = self._classify_failure(sub_result.stderr)
        return WorkerResult(
            success=False,
            exit_code=sub_result.exit_code,
            failure_type=failure_type,
            failure_detail=sub_result.stderr,
            stdout=sub_result.stdout,
            stderr=sub_result.stderr,
            duration_seconds=duration,
            artifacts=self._extract_artifacts(sub_result.stdout),
        )

    def health_check(self) -> WorkerHealth:
        try:
            proc = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            version = proc.stdout.strip()
            return WorkerHealth(
                available=proc.returncode == 0,
                worker_id=self.worker_id,
                version=version,
            )
        except FileNotFoundError as exc:
            return WorkerHealth(
                available=False,
                worker_id=self.worker_id,
                error=f"Claude CLI not found: {exc}",
            )

    def _translate_instruction(self, task: WorkerTask) -> str:
        return f"{_EXECUTOR_PREFIX}{task.instruction}"

    def _translate_permissions(self, perms: WorkerPermissions) -> str:
        tools: list[str] = []
        if perms.file_read:
            tools.extend(["Read", "Glob", "Grep"])
        if perms.file_write:
            tools.extend(["Write", "Edit"])
        if perms.shell_execute:
            tools.append("Bash")
        return ",".join(tools)

    def _classify_failure(self, stderr: str) -> FailureType:
        lower = stderr.lower()
        if "heartbeat timeout" in lower:
            return FailureType.HEARTBEAT_TIMEOUT
        if "timeout after" in lower:
            return FailureType.TIMEOUT
        if "command not found" in lower:
            return FailureType.COMMAND_NOT_FOUND
        if "permission denied" in lower:
            return FailureType.PERMISSION_DENIED
        return FailureType.EXIT_CODE_NON_ZERO

    def _extract_artifacts(self, stdout: str) -> list[WorkerArtifact]:
        artifacts: list[WorkerArtifact] = []
        for match in _PR_URL_PATTERN.finditer(stdout):
            pr_number = match.group(1)
            pr_url = match.group(0)
            artifacts.append(
                WorkerArtifact(
                    artifact_type=ArtifactType.PR_URL,
                    name=f"PR #{pr_number}",
                    location=pr_url,
                )
            )
        return artifacts

    def _write_claudeignore(self, task: WorkerTask) -> Path | None:
        if not task.workspace.context_filter:
            return None
        path = task.workspace.cwd / ".claudeignore"
        path.write_text("\n".join(task.workspace.context_filter) + "\n")
        return path

    def _cleanup_claudeignore(self, path: Path | None) -> None:
        if path is not None and path.exists():
            path.unlink()

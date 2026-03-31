"""Tests for kevin.workers.shell — ShellWorker adapter."""

from pathlib import Path

import pytest

from kevin.workers.interface import (
    FailureType,
    WorkerPermissions,
    WorkerTask,
    WorkspacePolicy,
)
from kevin.workers.shell import ShellWorker


def _make_task(
    tmp_path: Path,
    instruction: str = "echo ok",
    timeout: int = 10,
) -> WorkerTask:
    return WorkerTask(
        task_id="shell-001",
        instruction=instruction,
        workspace=WorkspacePolicy(cwd=tmp_path),
        permissions=WorkerPermissions(),
        timeout=timeout,
    )


class TestShellWorkerExecute:
    def test_should_succeed_on_zero_exit(self, tmp_path: Path) -> None:
        worker = ShellWorker()
        task = _make_task(tmp_path, instruction="echo hello")

        result = worker.execute(task)

        assert result.success is True
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.failure_type is None
        assert result.duration_seconds > 0

    def test_should_fail_on_non_zero_exit(self, tmp_path: Path) -> None:
        worker = ShellWorker()
        task = _make_task(tmp_path, instruction="exit 42")

        result = worker.execute(task)

        assert result.success is False
        assert result.exit_code == 42
        assert result.failure_type == FailureType.EXIT_CODE_NON_ZERO

    def test_should_capture_stderr(self, tmp_path: Path) -> None:
        worker = ShellWorker()
        task = _make_task(tmp_path, instruction="echo err >&2; exit 1")

        result = worker.execute(task)

        assert result.success is False
        assert "err" in result.stderr
        assert result.exit_code == 1

    def test_task_timeout_not_enforced_by_subprocess(self, tmp_path: Path) -> None:
        """Blueprint timeout is ignored by subprocess_utils; short sleep still succeeds."""
        worker = ShellWorker()
        task = _make_task(tmp_path, instruction="sleep 1; echo ok", timeout=1)

        result = worker.execute(task)

        assert result.success is True
        assert "ok" in result.stdout


class TestShellWorkerHealthCheck:
    def test_should_always_be_available(self) -> None:
        worker = ShellWorker()

        health = worker.health_check()

        assert health.available is True
        assert health.worker_id == "shell"
        assert health.version == "builtin"
        assert "shell_execute" in health.capabilities


class TestShellWorkerIdentity:
    def test_should_return_shell_as_worker_id(self) -> None:
        worker = ShellWorker()
        assert worker.worker_id == "shell"

"""Tests for kevin.workers.claude_code — ClaudeCodeWorker adapter."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kevin.subprocess_utils import SubprocessResult
from kevin.workers.claude_code import ClaudeCodeWorker
from kevin.workers.interface import (
    ArtifactType,
    FailureType,
    WorkerPermissions,
    WorkerTask,
    WorkspacePolicy,
)


def _make_task(
    *,
    instruction: str = "Implement feature X",
    model: str = "",
    timeout: int = 300,
    file_read: bool = True,
    file_write: bool = True,
    shell_execute: bool = True,
    context_filter: list[str] | None = None,
) -> WorkerTask:
    """Factory for WorkerTask with sensible defaults."""
    return WorkerTask(
        task_id="task-001",
        instruction=instruction,
        workspace=WorkspacePolicy(
            cwd=Path("/tmp/work"),
            context_filter=context_filter or [],
        ),
        permissions=WorkerPermissions(
            file_read=file_read,
            file_write=file_write,
            shell_execute=shell_execute,
        ),
        timeout=timeout,
        model=model,
    )


class TestClaudeCodeWorkerExecute:
    def test_should_return_success_on_zero_exit(self) -> None:
        worker = ClaudeCodeWorker()
        task = _make_task()
        mock_result = SubprocessResult(
            success=True,
            exit_code=0,
            stdout="Done.\n",
            stderr="",
        )
        with patch("kevin.workers.claude_code.run_with_heartbeat", return_value=mock_result):
            result = worker.execute(task)

        assert result.success is True
        assert result.exit_code == 0
        assert result.failure_type is None
        assert result.stdout == "Done.\n"

    def test_should_map_timeout_to_failure_type(self) -> None:
        worker = ClaudeCodeWorker()
        task = _make_task()
        mock_result = SubprocessResult(
            success=False,
            exit_code=None,
            stdout="",
            stderr="Timeout after 300s\nsome context",
        )
        with patch("kevin.workers.claude_code.run_with_heartbeat", return_value=mock_result):
            result = worker.execute(task)

        assert result.success is False
        assert result.failure_type == FailureType.TIMEOUT

    def test_should_map_heartbeat_to_failure_type(self) -> None:
        worker = ClaudeCodeWorker()
        task = _make_task()
        mock_result = SubprocessResult(
            success=False,
            exit_code=None,
            stdout="",
            stderr="Heartbeat timeout: no output for 600s\n",
        )
        with patch("kevin.workers.claude_code.run_with_heartbeat", return_value=mock_result):
            result = worker.execute(task)

        assert result.success is False
        assert result.failure_type == FailureType.HEARTBEAT_TIMEOUT

    def test_should_extract_pr_artifact_from_stdout(self) -> None:
        worker = ClaudeCodeWorker()
        task = _make_task()
        stdout = "Created PR: https://github.com/acme/repo/pull/42\nDone."
        mock_result = SubprocessResult(
            success=True,
            exit_code=0,
            stdout=stdout,
            stderr="",
        )
        with patch("kevin.workers.claude_code.run_with_heartbeat", return_value=mock_result):
            result = worker.execute(task)

        assert len(result.artifacts) == 1
        assert result.artifacts[0].artifact_type == ArtifactType.PR_URL
        assert "42" in result.artifacts[0].location

    def test_should_include_model_flag_when_specified(self) -> None:
        worker = ClaudeCodeWorker()
        task = _make_task(model="claude-sonnet-4-20250514")
        mock_result = SubprocessResult(success=True, exit_code=0, stdout="", stderr="")

        with patch("kevin.workers.claude_code.run_with_heartbeat", return_value=mock_result) as mock_run:
            worker.execute(task)

        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        assert "claude-sonnet-4-20250514" in cmd


class TestTranslatePermissions:
    def test_should_translate_permissions_to_allowed_tools(self) -> None:
        worker = ClaudeCodeWorker()
        read_only_perms = WorkerPermissions(
            file_read=True,
            file_write=False,
            shell_execute=False,
        )
        tools_str = worker._translate_permissions(read_only_perms)

        assert "Read" in tools_str
        assert "Glob" in tools_str
        assert "Grep" in tools_str
        assert "Write" not in tools_str
        assert "Edit" not in tools_str
        assert "Bash" not in tools_str

    def test_should_include_write_tools_when_permitted(self) -> None:
        worker = ClaudeCodeWorker()
        perms = WorkerPermissions(file_read=True, file_write=True, shell_execute=False)
        tools_str = worker._translate_permissions(perms)

        assert "Write" in tools_str
        assert "Edit" in tools_str
        assert "Bash" not in tools_str

    def test_should_include_bash_when_shell_permitted(self) -> None:
        worker = ClaudeCodeWorker()
        perms = WorkerPermissions(file_read=True, file_write=True, shell_execute=True)
        tools_str = worker._translate_permissions(perms)

        assert "Bash" in tools_str


class TestClaudeignoreLifecycle:
    def test_should_manage_claudeignore_lifecycle(self, tmp_path: Path) -> None:
        worker = ClaudeCodeWorker()
        task = WorkerTask(
            task_id="task-002",
            instruction="Do stuff",
            workspace=WorkspacePolicy(
                cwd=tmp_path,
                context_filter=["node_modules", "*.pyc", "dist"],
            ),
            permissions=WorkerPermissions(),
            timeout=60,
        )
        mock_result = SubprocessResult(success=True, exit_code=0, stdout="", stderr="")

        with patch("kevin.workers.claude_code.run_with_heartbeat", return_value=mock_result):
            worker.execute(task)

        # .claudeignore should be cleaned up after execution
        claudeignore = tmp_path / ".claudeignore"
        assert not claudeignore.exists()

    def test_should_write_claudeignore_during_execution(self, tmp_path: Path) -> None:
        worker = ClaudeCodeWorker()
        written_content: str | None = None

        def capture_claudeignore(cmd: list[str], *, cwd: Path, timeout: int, heartbeat_timeout: int = 600) -> SubprocessResult:
            nonlocal written_content
            claudeignore = cwd / ".claudeignore"
            if claudeignore.exists():
                written_content = claudeignore.read_text()
            return SubprocessResult(success=True, exit_code=0, stdout="", stderr="")

        task = WorkerTask(
            task_id="task-003",
            instruction="Do stuff",
            workspace=WorkspacePolicy(
                cwd=tmp_path,
                context_filter=["node_modules", "*.pyc"],
            ),
            permissions=WorkerPermissions(),
            timeout=60,
        )

        with patch("kevin.workers.claude_code.run_with_heartbeat", side_effect=capture_claudeignore):
            worker.execute(task)

        assert written_content is not None
        assert "node_modules" in written_content
        assert "*.pyc" in written_content

    def test_should_not_create_claudeignore_when_filter_empty(self, tmp_path: Path) -> None:
        worker = ClaudeCodeWorker()
        task = WorkerTask(
            task_id="task-004",
            instruction="Do stuff",
            workspace=WorkspacePolicy(cwd=tmp_path, context_filter=[]),
            permissions=WorkerPermissions(),
            timeout=60,
        )
        mock_result = SubprocessResult(success=True, exit_code=0, stdout="", stderr="")

        created_during: bool = False

        def check_no_claudeignore(cmd: list[str], *, cwd: Path, timeout: int, heartbeat_timeout: int = 600) -> SubprocessResult:
            nonlocal created_during
            created_during = (cwd / ".claudeignore").exists()
            return mock_result

        with patch("kevin.workers.claude_code.run_with_heartbeat", side_effect=check_no_claudeignore):
            worker.execute(task)

        assert not created_during


class TestHealthCheck:
    def test_should_report_healthy_when_cli_available(self) -> None:
        worker = ClaudeCodeWorker()
        mock_proc = MagicMock()
        mock_proc.stdout = "1.0.5\n"
        mock_proc.returncode = 0

        with patch("subprocess.run", return_value=mock_proc):
            health = worker.health_check()

        assert health.available is True
        assert health.worker_id == "claude-code"
        assert health.version == "1.0.5"

    def test_should_report_unhealthy_when_cli_missing(self) -> None:
        worker = ClaudeCodeWorker()

        with patch("subprocess.run", side_effect=FileNotFoundError("claude not found")):
            health = worker.health_check()

        assert health.available is False
        assert health.worker_id == "claude-code"
        assert "not found" in health.error.lower() or "claude" in health.error.lower()


class TestWorkerIdProperty:
    def test_should_return_claude_code(self) -> None:
        worker = ClaudeCodeWorker()
        assert worker.worker_id == "claude-code"


class TestClassifyFailure:
    def test_should_classify_command_not_found(self) -> None:
        worker = ClaudeCodeWorker()
        assert worker._classify_failure("Command not found: claude") == FailureType.COMMAND_NOT_FOUND

    def test_should_classify_permission_denied(self) -> None:
        worker = ClaudeCodeWorker()
        assert worker._classify_failure("permission denied: /tmp/x") == FailureType.PERMISSION_DENIED

    def test_should_default_to_exit_code_non_zero(self) -> None:
        worker = ClaudeCodeWorker()
        assert worker._classify_failure("some random error") == FailureType.EXIT_CODE_NON_ZERO


class TestTranslateInstruction:
    def test_should_prefix_executor_framing(self) -> None:
        worker = ClaudeCodeWorker()
        task = _make_task(instruction="Build the login page")
        prompt = worker._translate_instruction(task)

        assert prompt.startswith("You are Kevin Executor")
        assert "Build the login page" in prompt
        assert "Do NOT ask questions" in prompt

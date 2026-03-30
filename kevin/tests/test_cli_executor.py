# kevin/tests/test_cli_executor.py
"""Tests for kevin CLI executor mode (--run-id + --instruction)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from kevin.cli import main


class TestExecutorMode:
    """Test the executor CLI entry point."""

    @patch("kevin.cli._execute_agentic")
    @patch("kevin.cli.load")
    @patch("kevin.cli.find_blueprint")
    @patch("kevin.cli.StateManager")
    def test_executor_mode_loads_blueprint_and_executes(
        self,
        mock_state_mgr_cls: MagicMock,
        mock_find: MagicMock,
        mock_load: MagicMock,
        mock_exec: MagicMock,
        tmp_path,
    ) -> None:
        """should complete successfully when all required executor args are provided."""
        bp_file = tmp_path / "bp.yaml"
        bp_file.write_text("blueprint: {metadata: {blueprint_id: bp_test}}")
        mock_find.return_value = bp_file

        mock_bp = MagicMock()
        mock_bp.blueprint_id = "bp_coding_task.1.0.0"
        mock_bp.blueprint_name = "Test"
        mock_bp.blocks = []
        mock_load.return_value = mock_bp

        mock_exec.return_value = 0

        mock_run = MagicMock()
        mock_run.run_id = "local-run-abc"
        mock_run.blocks = {}
        mock_state_mgr = MagicMock()
        mock_state_mgr.create_run.return_value = mock_run
        mock_state_mgr.load_run.return_value = mock_run
        mock_state_mgr_cls.return_value = mock_state_mgr

        ctx = json.dumps({"repo": "owner/app", "ref": "main"})

        with patch("kevin.callback.CallbackClient.report_status"):
            result = main([
                "run",
                "--run-id", "test-uuid-123",
                "--blueprint", "bp_coding_task.1.0.0",
                "--instruction", "Add health check",
                "--context", ctx,
                "--callback-url", "https://example.com/callback",
                "--callback-secret", "secret123",
            ])

        assert result == 0
        mock_find.assert_called_once()
        mock_exec.assert_called_once()

    @patch("kevin.cli._execute_agentic")
    @patch("kevin.cli.load")
    @patch("kevin.cli.find_blueprint")
    @patch("kevin.cli.StateManager")
    def test_executor_mode_reports_running_then_completed(
        self,
        mock_state_mgr_cls: MagicMock,
        mock_find: MagicMock,
        mock_load: MagicMock,
        mock_exec: MagicMock,
        tmp_path,
    ) -> None:
        """should call report_status with 'running' then 'completed' on success."""
        bp_file = tmp_path / "bp.yaml"
        bp_file.write_text("blueprint: {metadata: {blueprint_id: bp_test}}")
        mock_find.return_value = bp_file

        mock_bp = MagicMock()
        mock_bp.blueprint_id = "bp_test"
        mock_bp.blocks = []
        mock_load.return_value = mock_bp

        mock_exec.return_value = 0

        mock_run = MagicMock()
        mock_run.run_id = "local-run-xyz"
        mock_run.blocks = {}
        mock_state_mgr = MagicMock()
        mock_state_mgr.create_run.return_value = mock_run
        mock_state_mgr.load_run.return_value = mock_run
        mock_state_mgr_cls.return_value = mock_state_mgr

        status_calls: list[str] = []

        def capture_status(**kwargs) -> None:
            status_calls.append(kwargs["status"])

        with patch("kevin.callback.CallbackClient.report_status", side_effect=capture_status):
            result = main([
                "run",
                "--run-id", "exec-run-001",
                "--blueprint", "bp_test",
                "--instruction", "Do something",
                "--callback-url", "https://example.com/cb",
                "--callback-secret", "s3cr3t",
            ])

        assert result == 0
        assert status_calls[0] == "running"
        assert status_calls[-1] == "completed"

    @patch("kevin.cli._execute_agentic")
    @patch("kevin.cli.load")
    @patch("kevin.cli.find_blueprint")
    @patch("kevin.cli.StateManager")
    def test_executor_mode_reports_failed_on_execution_failure(
        self,
        mock_state_mgr_cls: MagicMock,
        mock_find: MagicMock,
        mock_load: MagicMock,
        mock_exec: MagicMock,
        tmp_path,
    ) -> None:
        """should call report_status with 'failed' when _execute_agentic returns non-zero."""
        bp_file = tmp_path / "bp.yaml"
        bp_file.write_text("blueprint: {metadata: {blueprint_id: bp_test}}")
        mock_find.return_value = bp_file

        mock_bp = MagicMock()
        mock_bp.blueprint_id = "bp_test"
        mock_bp.blocks = []
        mock_load.return_value = mock_bp

        mock_exec.return_value = 1  # Failure

        mock_run = MagicMock()
        mock_run.run_id = "local-run-fail"
        mock_run.blocks = {}
        mock_state_mgr = MagicMock()
        mock_state_mgr.create_run.return_value = mock_run
        mock_state_mgr.load_run.return_value = mock_run
        mock_state_mgr_cls.return_value = mock_state_mgr

        with patch("kevin.callback.CallbackClient.report_status") as mock_report:
            result = main([
                "run",
                "--run-id", "exec-run-002",
                "--blueprint", "bp_test",
                "--instruction", "Do something",
                "--callback-url", "https://example.com/cb",
                "--callback-secret", "s3cr3t",
            ])

        assert result == 1
        calls = [c.kwargs["status"] for c in mock_report.call_args_list]
        assert "failed" in calls

    @patch("kevin.cli._execute_blocks")
    @patch("kevin.cli.load")
    @patch("kevin.cli.find_blueprint")
    @patch("kevin.cli.StateManager")
    def test_legacy_mode_uses_block_execution(
        self,
        mock_state_mgr_cls: MagicMock,
        mock_find: MagicMock,
        mock_load: MagicMock,
        mock_exec: MagicMock,
        tmp_path,
    ) -> None:
        """should use _execute_blocks when --legacy flag is set."""
        mock_find.return_value = tmp_path / "bp.yaml"

        mock_bp = MagicMock()
        mock_bp.blueprint_id = "bp_test"
        mock_bp.blocks = []
        mock_load.return_value = mock_bp

        mock_exec.return_value = 0

        mock_run = MagicMock()
        mock_run.run_id = "local-run-legacy"
        mock_run.blocks = {}
        mock_state_mgr = MagicMock()
        mock_state_mgr.create_run.return_value = mock_run
        mock_state_mgr.load_run.return_value = mock_run
        mock_state_mgr_cls.return_value = mock_state_mgr

        with patch("kevin.callback.CallbackClient.report_status"):
            result = main([
                "run",
                "--run-id", "test-legacy",
                "--blueprint", "bp_test",
                "--instruction", "Do something",
                "--callback-url", "https://example.com/cb",
                "--callback-secret", "s3cr3t",
                "--legacy",
            ])

        assert result == 0
        mock_exec.assert_called_once()

    def test_executor_mode_requires_run_id_with_instruction(self) -> None:
        """should fail when --instruction is given without --run-id."""
        result = main([
            "run",
            "--instruction", "Add health check",
            "--blueprint", "bp_coding_task.1.0.0",
        ])
        assert result != 0

    def test_issue_mode_still_requires_issue_and_repo(self) -> None:
        """should fail when neither executor args nor issue/repo are provided."""
        result = main(["run"])
        assert result != 0

    @patch("kevin.cli.find_blueprint", side_effect=FileNotFoundError)
    def test_executor_mode_fails_when_blueprint_not_found(
        self, mock_find: MagicMock
    ) -> None:
        """should report failed with BLUEPRINT_NOT_FOUND when blueprint file missing."""
        with patch("kevin.callback.CallbackClient.report_status") as mock_report:
            result = main([
                "run",
                "--run-id", "exec-run-003",
                "--blueprint", "bp_nonexistent",
                "--instruction", "Do something",
                "--callback-url", "https://example.com/cb",
                "--callback-secret", "s3cr3t",
            ])

        assert result == 1
        calls = {c.kwargs.get("error_code") for c in mock_report.call_args_list}
        assert "BLUEPRINT_NOT_FOUND" in calls

    def test_executor_mode_fails_without_blueprint(self) -> None:
        """should report failed when --blueprint is omitted in executor mode."""
        with patch("kevin.callback.CallbackClient.report_status") as mock_report:
            result = main([
                "run",
                "--run-id", "exec-run-004",
                "--instruction", "Do something",
                "--callback-url", "https://example.com/cb",
                "--callback-secret", "s3cr3t",
            ])

        assert result == 1
        calls = {c.kwargs.get("error_code") for c in mock_report.call_args_list}
        assert "BLUEPRINT_NOT_FOUND" in calls


class TestAgenticWorkerIntegration:
    """Test that _execute_agentic uses WorkerRegistry internally."""

    @patch("kevin.workers.registry.WorkerRegistry", autospec=True)
    @patch("kevin.blueprint_compiler.compile_task")
    @patch("kevin.blueprint_compiler.load_semantic")
    def test_agentic_uses_worker_registry(
        self, mock_load_semantic, mock_compile_task, mock_registry_cls,
    ) -> None:
        """should resolve a worker from WorkerRegistry and call execute()."""
        from kevin.cli import _execute_agentic
        from kevin.workers.interface import WorkerResult, WorkerTask

        # Arrange: semantic blueprint
        mock_semantic = MagicMock()
        mock_semantic.blueprint_name = "Test BP"
        mock_semantic.acceptance_criteria = ["c1"]
        mock_semantic.constraints = ["k1"]
        mock_semantic.task_timeout = 300
        mock_load_semantic.return_value = mock_semantic

        # Arrange: compiled task
        mock_task = MagicMock(spec=WorkerTask)
        mock_task.instruction = "do stuff"
        mock_compile_task.return_value = mock_task

        # Arrange: worker
        mock_worker = MagicMock()
        mock_worker.worker_id = "claude-code"
        mock_worker.execute.return_value = WorkerResult(
            success=True, exit_code=0, stdout="PR #42 opened", stderr="",
            duration_seconds=10.0,
        )
        mock_registry_cls.return_value.resolve.return_value = mock_worker

        # Arrange: config / state
        config = MagicMock()
        config.dry_run = False
        config.target_repo = "/tmp/repo"
        state_mgr = MagicMock()
        run = MagicMock()
        run.run_id = "worker-test-001"
        run.repo = "owner/repo"
        run.issue_number = 42
        bp_path = MagicMock()

        # Act
        with patch("kevin.executor.run_post_validators", return_value=[]):
            with patch("kevin.cli._notify_teams"):
                with patch("kevin.cli._post_completion_comment_agentic"):
                    with patch("kevin.cli.remove_labels"):
                        with patch("kevin.cli.add_labels"):
                            exit_code = _execute_agentic(
                                config, state_mgr, run, bp_path, {}, issue=None,
                            )

        # Assert
        assert exit_code == 0
        mock_registry_cls.assert_called_once()
        mock_registry_cls.return_value.resolve.assert_called_once()
        mock_worker.execute.assert_called_once_with(mock_task)

    @patch("kevin.workers.registry.WorkerRegistry", autospec=True)
    @patch("kevin.blueprint_compiler.compile_task")
    @patch("kevin.blueprint_compiler.load_semantic")
    def test_agentic_dry_run_skips_worker_execute(
        self, mock_load_semantic, mock_compile_task, mock_registry_cls,
    ) -> None:
        """should return a dry-run WorkerResult instead of calling worker.execute()."""
        from kevin.cli import _execute_agentic

        mock_semantic = MagicMock()
        mock_semantic.blueprint_name = "Dry BP"
        mock_semantic.acceptance_criteria = []
        mock_semantic.constraints = []
        mock_semantic.task_timeout = 60
        mock_load_semantic.return_value = mock_semantic

        mock_task = MagicMock()
        mock_task.instruction = "dry instruction"
        mock_compile_task.return_value = mock_task

        mock_worker = MagicMock()
        mock_worker.worker_id = "claude-code"
        mock_registry_cls.return_value.resolve.return_value = mock_worker

        config = MagicMock()
        config.dry_run = True
        config.target_repo = "/tmp/repo"
        state_mgr = MagicMock()
        run = MagicMock()
        run.run_id = "dry-run-001"

        exit_code = _execute_agentic(config, state_mgr, run, MagicMock(), {})

        assert exit_code == 0
        mock_worker.execute.assert_not_called()
        # Verify logs saved with instruction as prompt
        state_mgr.save_executor_logs.assert_called_once()
        call_kwargs = state_mgr.save_executor_logs.call_args
        assert call_kwargs[1]["prompt"] == "dry instruction" or call_kwargs[0][1] == "dry instruction"


class TestExecutorModeAgenticIntegration:
    """Test agentic vs legacy mode dispatch."""

    @patch("kevin.cli._execute_agentic")
    @patch("kevin.cli.load")
    @patch("kevin.cli.find_blueprint")
    @patch("kevin.cli.StateManager")
    def test_agentic_mode_is_default(
        self,
        mock_state_mgr_cls: MagicMock,
        mock_find: MagicMock,
        mock_load: MagicMock,
        mock_exec_agentic: MagicMock,
        tmp_path,
    ) -> None:
        """should call _execute_agentic when no --legacy flag is passed."""
        mock_find.return_value = tmp_path / "bp.yaml"

        mock_bp = MagicMock()
        mock_bp.blueprint_id = "bp_test"
        mock_bp.blocks = []
        mock_load.return_value = mock_bp

        mock_exec_agentic.return_value = 0

        mock_run = MagicMock()
        mock_run.run_id = "local-run-agentic"
        mock_run.blocks = {}
        mock_state_mgr = MagicMock()
        mock_state_mgr.create_run.return_value = mock_run
        mock_state_mgr.load_run.return_value = mock_run
        mock_state_mgr_cls.return_value = mock_state_mgr

        with patch("kevin.callback.CallbackClient.report_status"):
            result = main([
                "run",
                "--run-id", "test-agentic-default",
                "--blueprint", "bp_test",
                "--instruction", "Do something",
                "--callback-url", "https://example.com/cb",
                "--callback-secret", "s3cr3t",
            ])

        assert result == 0
        mock_exec_agentic.assert_called_once()

    @patch("kevin.cli._execute_blocks")
    @patch("kevin.cli._execute_agentic")
    @patch("kevin.cli.load")
    @patch("kevin.cli.find_blueprint")
    @patch("kevin.cli.StateManager")
    def test_legacy_flag_uses_blocks(
        self,
        mock_state_mgr_cls: MagicMock,
        mock_find: MagicMock,
        mock_load: MagicMock,
        mock_exec_agentic: MagicMock,
        mock_exec_blocks: MagicMock,
        tmp_path,
    ) -> None:
        """should call _execute_blocks (not _execute_agentic) when --legacy is set."""
        mock_find.return_value = tmp_path / "bp.yaml"

        mock_bp = MagicMock()
        mock_bp.blueprint_id = "bp_test"
        mock_bp.blocks = []
        mock_load.return_value = mock_bp

        mock_exec_blocks.return_value = 0

        mock_run = MagicMock()
        mock_run.run_id = "local-run-legacy2"
        mock_run.blocks = {}
        mock_state_mgr = MagicMock()
        mock_state_mgr.create_run.return_value = mock_run
        mock_state_mgr.load_run.return_value = mock_run
        mock_state_mgr_cls.return_value = mock_state_mgr

        with patch("kevin.callback.CallbackClient.report_status"):
            result = main([
                "run",
                "--run-id", "test-legacy2",
                "--blueprint", "bp_test",
                "--instruction", "Do something",
                "--callback-url", "https://example.com/cb",
                "--callback-secret", "s3cr3t",
                "--legacy",
            ])

        assert result == 0
        mock_exec_blocks.assert_called_once()
        mock_exec_agentic.assert_not_called()

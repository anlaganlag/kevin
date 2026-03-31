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
        mock_find.return_value = tmp_path / "bp.yaml"

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
        mock_load.assert_called_once()
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
        mock_find.return_value = tmp_path / "bp.yaml"

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

    @patch("kevin.cli._execute_blocks")
    @patch("kevin.cli.load")
    @patch("kevin.cli.find_blueprint")
    @patch("kevin.cli.StateManager")
    def test_executor_mode_reports_failed_on_block_failure(
        self,
        mock_state_mgr_cls: MagicMock,
        mock_find: MagicMock,
        mock_load: MagicMock,
        mock_exec: MagicMock,
        tmp_path,
    ) -> None:
        """should call report_status with 'failed' when _execute_blocks returns non-zero."""
        mock_find.return_value = tmp_path / "bp.yaml"

        mock_bp = MagicMock()
        mock_bp.blueprint_id = "bp_test"
        mock_bp.blocks = []
        mock_load.return_value = mock_bp

        mock_exec.return_value = 1  # Failure

        mock_run = MagicMock()
        mock_run.run_id = "local-run-fail"
        mock_run.blocks = {
            "B1": MagicMock(status="failed", error="Something went wrong"),
        }
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
        # Last call should be 'failed'
        calls = [c.kwargs["status"] for c in mock_report.call_args_list]
        assert "failed" in calls

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

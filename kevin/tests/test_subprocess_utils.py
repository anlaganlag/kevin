"""Tests for kevin.subprocess_utils — heartbeat subprocess."""

from pathlib import Path

from kevin.subprocess_utils import SubprocessResult, run_with_heartbeat


class TestRunWithHeartbeat:
    def test_should_succeed_on_simple_command(self, tmp_path: Path) -> None:
        result = run_with_heartbeat(
            ["echo", "hello"], cwd=tmp_path, timeout=10,
        )
        assert result.success is True
        assert result.exit_code == 0
        assert "hello" in result.stdout

    def test_should_fail_on_bad_exit_code(self, tmp_path: Path) -> None:
        result = run_with_heartbeat(
            ["bash", "-c", "exit 42"], cwd=tmp_path, timeout=10,
        )
        assert result.success is False
        assert result.exit_code == 42

    def test_should_capture_stderr(self, tmp_path: Path) -> None:
        result = run_with_heartbeat(
            ["bash", "-c", "echo err >&2; exit 1"], cwd=tmp_path, timeout=10,
        )
        assert result.success is False
        assert "err" in result.stderr

    def test_should_timeout_on_long_command(self, tmp_path: Path) -> None:
        result = run_with_heartbeat(
            ["sleep", "30"], cwd=tmp_path, timeout=1, heartbeat_timeout=1,
        )
        assert result.success is False
        assert "timeout" in result.stderr.lower() or "Timeout" in result.stderr

    def test_should_fail_on_command_not_found(self, tmp_path: Path) -> None:
        result = run_with_heartbeat(
            ["__nonexistent_command__"], cwd=tmp_path, timeout=10,
        )
        assert result.success is False
        assert "not found" in result.stderr.lower() or "Command not found" in result.stderr


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------


class TestRunWithHeartbeatEdgeCases:
    """Edge-case scenarios for heartbeat subprocess."""

    def test_should_handle_large_stdout(self, tmp_path: Path) -> None:
        """100KB of stdout data should be captured completely."""
        # Generate 100KB via printf (faster and more portable than Python echo)
        result = run_with_heartbeat(
            ["bash", "-c", "python3 -c \"print('A' * 100000)\""],
            cwd=tmp_path,
            timeout=10,
        )

        assert result.success is True
        assert len(result.stdout.strip()) == 100_000

    def test_should_handle_interleaved_stdout_stderr(self, tmp_path: Path) -> None:
        """Both stdout and stderr should be captured when interleaved."""
        script = (
            "echo out1; echo err1 >&2; echo out2; echo err2 >&2"
        )
        result = run_with_heartbeat(
            ["bash", "-c", script],
            cwd=tmp_path,
            timeout=10,
        )

        assert result.success is True
        assert "out1" in result.stdout
        assert "out2" in result.stdout
        assert "err1" in result.stderr
        assert "err2" in result.stderr

    def test_should_handle_process_that_writes_then_hangs(self, tmp_path: Path) -> None:
        """Process that outputs then goes silent should be killed by heartbeat timeout."""
        script = "echo alive; sleep 30"
        result = run_with_heartbeat(
            ["bash", "-c", script],
            cwd=tmp_path,
            timeout=10,
            heartbeat_timeout=2,
        )

        assert result.success is False
        assert "alive" in result.stdout
        # Killed by heartbeat or overall timeout
        assert "timeout" in result.stderr.lower() or "Timeout" in result.stderr

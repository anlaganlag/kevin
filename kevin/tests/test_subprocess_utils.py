"""Tests for kevin.subprocess_utils — subprocess wrapper."""

from pathlib import Path

from kevin.subprocess_utils import run_with_heartbeat


# ---------------------------------------------------------------------------
# Batch mode (no callback — original behaviour)
# ---------------------------------------------------------------------------


def test_capture_stdout() -> None:
    r = run_with_heartbeat(["echo", "hello"], cwd=Path("."), timeout=5)
    assert r.success
    assert "hello" in r.stdout


def test_capture_stderr() -> None:
    r = run_with_heartbeat(["bash", "-c", "echo err >&2"], cwd=Path("."), timeout=5)
    assert r.success
    assert "err" in r.stderr


def test_exit_code() -> None:
    r = run_with_heartbeat(["bash", "-c", "exit 7"], cwd=Path("."), timeout=5)
    assert not r.success
    assert r.exit_code == 7


def test_command_not_found() -> None:
    r = run_with_heartbeat(["nonexistent_xyz_cmd"], cwd=Path("."), timeout=5)
    assert not r.success
    assert "not found" in r.stderr.lower() or "Command not found" in r.stderr


def test_timeout_param_ignored_long_sleep_completes() -> None:
    """timeout= is legacy API; subprocess is not killed early."""
    r = run_with_heartbeat(["sleep", "1"], cwd=Path("."), timeout=1)
    assert r.success


# ---------------------------------------------------------------------------
# Streaming mode (with on_progress callback)
# ---------------------------------------------------------------------------


class TestStreamingMode:
    """Tests for _run_streaming via the on_progress parameter."""

    def test_should_forward_each_line_to_callback(self) -> None:
        lines: list[str] = []
        r = run_with_heartbeat(
            ["bash", "-c", "echo AAA; echo BBB; echo CCC"],
            cwd=Path("."), timeout=5,
            on_progress=lines.append,
        )
        assert r.success
        assert lines == ["AAA", "BBB", "CCC"]

    def test_should_still_capture_full_stdout(self) -> None:
        r = run_with_heartbeat(
            ["bash", "-c", "echo one; echo two"],
            cwd=Path("."), timeout=5,
            on_progress=lambda _: None,
        )
        assert r.success
        assert "one" in r.stdout
        assert "two" in r.stdout

    def test_should_capture_stderr_concurrently(self) -> None:
        r = run_with_heartbeat(
            ["bash", "-c", "echo out; echo err >&2"],
            cwd=Path("."), timeout=5,
            on_progress=lambda _: None,
        )
        assert r.success
        assert "out" in r.stdout
        assert "err" in r.stderr

    def test_should_not_deadlock_on_large_stderr(self) -> None:
        """Regression: stderr > pipe buffer must not deadlock."""
        r = run_with_heartbeat(
            ["bash", "-c", "python3 -c \"import sys; sys.stderr.write('X' * 100000); print('done')\""],
            cwd=Path("."), timeout=10,
            on_progress=lambda _: None,
        )
        assert r.success
        assert "done" in r.stdout
        assert len(r.stderr) == 100000

    def test_should_survive_callback_exception(self) -> None:
        def bad_callback(line: str) -> None:
            raise ValueError("boom")

        r = run_with_heartbeat(
            ["bash", "-c", "echo safe"],
            cwd=Path("."), timeout=5,
            on_progress=bad_callback,
        )
        assert r.success
        assert "safe" in r.stdout

    def test_should_report_failure_exit_code(self) -> None:
        lines: list[str] = []
        r = run_with_heartbeat(
            ["bash", "-c", "echo before_fail; exit 42"],
            cwd=Path("."), timeout=5,
            on_progress=lines.append,
        )
        assert not r.success
        assert r.exit_code == 42
        assert "before_fail" in lines

    def test_should_handle_command_not_found(self) -> None:
        r = run_with_heartbeat(
            ["nonexistent_xyz_cmd"],
            cwd=Path("."), timeout=5,
            on_progress=lambda _: None,
        )
        assert not r.success
        assert "not found" in r.stderr.lower() or "Command not found" in r.stderr

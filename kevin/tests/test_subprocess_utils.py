"""Tests for kevin.subprocess_utils — subprocess wrapper."""

from pathlib import Path

from kevin.subprocess_utils import run_with_heartbeat


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

"""Tests for kevin.agent_runner — runners, validators, pre_check, heartbeat."""

import pytest
from pathlib import Path
from kevin.agent_runner import (
    _subprocess_run,
    _run_pre_check,
    run_block,
    HEARTBEAT_TIMEOUT_SECONDS,
)
from kevin.blueprint_loader import Block, Validator
import time


def _make_block(**overrides) -> Block:
    """Factory for Block with sensible defaults."""
    defaults = dict(
        block_id="B1", name="test", assigned_to="", dependencies=[],
        runner="shell", runner_config={"cwd": ".", "command": "echo ok"},
        timeout=10, max_retries=0, prompt_template="", output="",
        validators=[], acceptance_criteria=[], pre_check="", raw={},
    )
    defaults.update(overrides)
    return Block(**defaults)


class TestSubprocessRun:
    """Non-blocking subprocess with heartbeat."""

    def test_should_capture_stdout(self) -> None:
        r = _subprocess_run("t", ["echo", "hello"], cwd=Path("."), timeout=5)
        assert r.success
        assert "hello" in r.stdout

    def test_should_capture_stderr(self) -> None:
        r = _subprocess_run("t", ["bash", "-c", "echo err >&2"], cwd=Path("."), timeout=5)
        assert "err" in r.stderr

    def test_should_report_exit_code(self) -> None:
        r = _subprocess_run("t", ["bash", "-c", "exit 42"], cwd=Path("."), timeout=5)
        assert not r.success
        assert r.exit_code == 42

    def test_should_kill_on_timeout(self) -> None:
        start = time.monotonic()
        r = _subprocess_run("t", ["sleep", "30"], cwd=Path("."), timeout=2)
        elapsed = time.monotonic() - start
        assert not r.success
        assert elapsed < 5
        assert "imeout" in r.stderr  # "Timeout" or "timeout"

    def test_should_count_stderr_as_heartbeat(self) -> None:
        """stderr output should reset the heartbeat timer."""
        r = _subprocess_run(
            "t",
            ["bash", "-c", "for i in 1 2 3; do echo alive >&2; sleep 1; done; echo done"],
            cwd=Path("."), timeout=10,
        )
        assert r.success
        assert "done" in r.stdout
        assert "alive" in r.stderr

    def test_should_handle_command_not_found(self) -> None:
        r = _subprocess_run("t", ["nonexistent_xyz_cmd"], cwd=Path("."), timeout=5)
        assert not r.success
        assert "not found" in r.stderr.lower() or "Command not found" in r.stderr


class TestPreCheck:
    """Idempotency reset before block execution."""

    def test_should_skip_when_empty(self) -> None:
        block = _make_block(pre_check="")
        assert _run_pre_check(block, {}) is None

    def test_should_return_none_on_success(self) -> None:
        block = _make_block(pre_check="echo ok")
        assert _run_pre_check(block, {}) is None

    def test_should_return_failure_on_nonzero_exit(self) -> None:
        block = _make_block(pre_check="exit 1")
        result = _run_pre_check(block, {})
        assert result is not None
        assert not result.success
        assert "pre_check failed" in result.stderr


class TestRunBlock:
    """End-to-end block execution with validators."""

    def test_should_run_shell_block(self) -> None:
        block = _make_block(runner_config={"command": "echo 42"})
        r = run_block(block, {})
        assert r.success
        assert "42" in r.stdout

    def test_should_fail_on_unknown_runner(self) -> None:
        block = _make_block(runner="unknown_runner")
        r = run_block(block, {})
        assert not r.success
        assert "Unknown runner" in r.stderr

    def test_should_run_validators_on_success(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        block = _make_block(
            runner_config={"cwd": str(tmp_path), "command": f"echo x > {target}"},
            validators=[Validator(type="file_exists", params={"path": "out.txt"})],
        )
        r = run_block(block, {})
        assert r.success
        assert r.validator_results is not None
        assert r.validator_results[0]["passed"]

    def test_should_fail_when_validator_fails(self) -> None:
        block = _make_block(
            validators=[Validator(type="file_exists", params={"path": "nonexistent_xyz.txt"})],
        )
        r = run_block(block, {})
        assert not r.success

    def test_should_run_pre_check_on_retry(self, tmp_path: Path) -> None:
        marker = tmp_path / "marker.txt"
        marker.write_text("old")
        block = _make_block(
            pre_check=f"rm {marker}",
            runner_config={"command": f"test ! -f {marker} && echo cleaned"},
        )
        r = run_block(block, {}, is_retry=True)
        assert r.success
        assert "cleaned" in r.stdout

    def test_should_skip_pre_check_on_first_attempt(self, tmp_path: Path) -> None:
        block = _make_block(
            pre_check="exit 1",
            runner_config={"command": "echo ok"},
        )
        r = run_block(block, {}, is_retry=False)
        assert r.success
        assert "ok" in r.stdout

    def test_should_skip_block_when_pre_check_fails_on_retry(self) -> None:
        block = _make_block(pre_check="exit 1")
        r = run_block(block, {}, is_retry=True)
        assert not r.success
        assert "pre_check failed" in r.stderr

    def test_dry_run_should_not_execute(self) -> None:
        block = _make_block(runner_config={"command": "exit 1"})
        r = run_block(block, {}, dry_run=True)
        assert r.success
        assert "dry-run" in r.stdout

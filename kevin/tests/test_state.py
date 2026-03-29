"""Tests for kevin.state — run state persistence, snapshots, logs."""

import pytest
from pathlib import Path
from kevin.state import StateManager, RunState, BlockState


@pytest.fixture
def state_env(tmp_path: Path) -> tuple[StateManager, Path]:
    """Create a StateManager with a temp state dir + fake blueprint."""
    state_dir = tmp_path / "runs"
    mgr = StateManager(state_dir)

    bp_file = tmp_path / "test_bp.yaml"
    bp_file.write_text("blueprint:\n  metadata:\n    blueprint_id: test\n")

    return mgr, bp_file


class TestCreateRun:
    """Run creation and snapshot."""

    def test_should_create_run_directory(self, state_env: tuple) -> None:
        mgr, bp_file = state_env
        run = mgr.create_run("test_bp", 42, "owner/repo", blueprint_path=bp_file)
        run_dir = mgr._state_dir / run.run_id
        assert run_dir.exists()
        assert (run_dir / "run.yaml").exists()

    def test_should_save_blueprint_snapshot(self, state_env: tuple) -> None:
        mgr, bp_file = state_env
        run = mgr.create_run("test_bp", 42, "owner/repo", blueprint_path=bp_file)
        snapshot = mgr._state_dir / run.run_id / "blueprint_snapshot.yaml"
        assert snapshot.exists()
        assert "blueprint_id: test" in snapshot.read_text()

    def test_should_skip_snapshot_when_no_path(self, state_env: tuple) -> None:
        mgr, _ = state_env
        run = mgr.create_run("test_bp", 42, "owner/repo")
        snapshot = mgr._state_dir / run.run_id / "blueprint_snapshot.yaml"
        assert not snapshot.exists()

    def test_should_set_status_to_running(self, state_env: tuple) -> None:
        mgr, bp_file = state_env
        run = mgr.create_run("test_bp", 42, "owner/repo")
        assert run.status == "running"


class TestBlockLogs:
    """Full execution log persistence."""

    def test_should_save_prompt_stdout_stderr(self, state_env: tuple) -> None:
        mgr, bp_file = state_env
        run = mgr.create_run("test_bp", 1, "o/r")
        path = mgr.save_block_logs(run.run_id, "B1", prompt="p", stdout="out", stderr="err")
        content = path.read_text()
        assert "=== PROMPT ===" in content
        assert "=== STDOUT ===" in content
        assert "=== STDERR ===" in content

    def test_should_preserve_retry_logs(self, state_env: tuple) -> None:
        mgr, _ = state_env
        run = mgr.create_run("test_bp", 1, "o/r")
        p0 = mgr.save_block_logs(run.run_id, "B2", prompt="first", stdout="a", stderr="")
        p1 = mgr.save_block_logs(run.run_id, "B2.attempt-1", prompt="second", stdout="b", stderr="")
        assert p0.exists()
        assert p1.exists()
        assert "first" in p0.read_text()
        assert "second" in p1.read_text()


class TestLoadAndComplete:
    """Round-trip persistence."""

    def test_should_load_saved_run(self, state_env: tuple) -> None:
        mgr, _ = state_env
        run = mgr.create_run("bp_x", 99, "a/b", variables={"k": "v"})
        loaded = mgr.load_run(run.run_id)
        assert loaded.blueprint_id == "bp_x"
        assert loaded.issue_number == 99
        assert loaded.variables["k"] == "v"

    def test_should_update_block_state(self, state_env: tuple) -> None:
        mgr, _ = state_env
        run = mgr.create_run("bp_x", 1, "a/b")
        bs = BlockState(block_id="B1", status="passed", runner="claude_cli")
        mgr.update_block(run, bs)
        loaded = mgr.load_run(run.run_id)
        assert loaded.blocks["B1"].status == "passed"

    def test_should_complete_run(self, state_env: tuple) -> None:
        mgr, _ = state_env
        run = mgr.create_run("bp_x", 1, "a/b")
        mgr.complete_run(run, "completed")
        loaded = mgr.load_run(run.run_id)
        assert loaded.status == "completed"
        assert loaded.completed_at != ""

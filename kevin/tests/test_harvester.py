"""Tests for kevin.learning.harvester — run extraction, log parsing, batch harvest."""

import json
from pathlib import Path

import pytest
import yaml

from kevin.learning.db import connect, ensure_schema
from kevin.learning.harvester import harvest_run, harvest_all, _find_final_log, _parse_attempt_number


@pytest.fixture
def knowledge_db(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    conn = connect(db_path)
    ensure_schema(conn)
    conn.close()
    return db_path


def _seed_run(state_dir: Path, run_id: str, status: str = "completed",
              blocks: dict | None = None, variables: dict | None = None) -> Path:
    """Create a minimal .kevin/runs/{run_id}/ structure."""
    run_dir = state_dir / run_id
    run_dir.mkdir(parents=True)
    logs_dir = run_dir / "logs"
    logs_dir.mkdir()

    run_data = {
        "run_id": run_id,
        "blueprint_id": "bp_coding_task.1.0.0",
        "issue_number": 42,
        "repo": "owner/repo",
        "status": status,
        "created_at": "2026-03-28T10:00:00+00:00",
        "completed_at": "2026-03-28T10:05:00+00:00",
        "variables": variables or {"issue_number": "42", "issue_title": "Add feature"},
        "blocks": blocks or {
            "B1": {"block_id": "B1", "status": "passed", "runner": "claude_cli",
                   "exit_code": 0, "retries": 0, "error": "",
                   "started_at": "2026-03-28T10:00:05+00:00",
                   "completed_at": "2026-03-28T10:02:00+00:00",
                   "output_summary": "analysis done", "validator_results": []},
        },
    }
    with (run_dir / "run.yaml").open("w") as f:
        yaml.safe_dump(run_data, f)

    (logs_dir / "B1.log").write_text(
        "=== PROMPT ===\nAnalyze the repo\n\n=== STDOUT ===\nanalysis done\n"
    )
    return run_dir


class TestFindFinalLog:
    def test_should_select_highest_attempt(self, tmp_path: Path) -> None:
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "B2.log").touch()
        (logs / "B2.attempt-1.log").touch()
        (logs / "B2.attempt-10.log").touch()
        result = _find_final_log(logs, "B2")
        assert result is not None
        assert result.name == "B2.attempt-10.log"

    def test_should_select_base_log_when_no_retries(self, tmp_path: Path) -> None:
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "B1.log").touch()
        result = _find_final_log(logs, "B1")
        assert result is not None
        assert result.name == "B1.log"

    def test_should_return_none_when_no_logs(self, tmp_path: Path) -> None:
        logs = tmp_path / "logs"
        logs.mkdir()
        assert _find_final_log(logs, "B99") is None


class TestParseAttemptNumber:
    def test_base_log_is_attempt_0(self) -> None:
        assert _parse_attempt_number("B2.log", "B2") == 0

    def test_attempt_1(self) -> None:
        assert _parse_attempt_number("B2.attempt-1.log", "B2") == 1

    def test_attempt_10(self) -> None:
        assert _parse_attempt_number("B2.attempt-10.log", "B2") == 10


class TestHarvestRun:
    def test_should_insert_records(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1")
        harvest_run(knowledge_db, state_dir, "r1")

        conn = connect(knowledge_db)
        row = conn.execute("SELECT * FROM run_history WHERE run_id='r1'").fetchone()
        assert row is not None
        blocks = conn.execute("SELECT * FROM block_history WHERE run_id='r1'").fetchall()
        assert len(blocks) == 1
        conn.close()

    def test_should_be_idempotent(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1")
        harvest_run(knowledge_db, state_dir, "r1")
        harvest_run(knowledge_db, state_dir, "r1")

        conn = connect(knowledge_db)
        count = conn.execute("SELECT COUNT(*) FROM run_history").fetchone()[0]
        assert count == 1
        fts_count = conn.execute(
            "SELECT COUNT(*) FROM block_logs_fts WHERE run_id='r1' AND block_id='B1'"
        ).fetchone()[0]
        assert fts_count == 1
        conn.close()

    def test_should_skip_running_status(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1", status="running")
        harvest_run(knowledge_db, state_dir, "r1")

        conn = connect(knowledge_db)
        count = conn.execute("SELECT COUNT(*) FROM run_history").fetchone()[0]
        assert count == 0
        conn.close()

    def test_should_compute_elapsed_seconds(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1")
        harvest_run(knowledge_db, state_dir, "r1")

        conn = connect(knowledge_db)
        elapsed = conn.execute(
            "SELECT elapsed_seconds FROM run_history WHERE run_id='r1'"
        ).fetchone()[0]
        assert elapsed is not None
        assert elapsed == pytest.approx(300.0, abs=1.0)
        conn.close()


class TestHarvestAll:
    def test_should_harvest_multiple_runs(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1")
        _seed_run(state_dir, "r2")
        result = harvest_all(knowledge_db, state_dir)
        assert result.harvested == 2
        assert result.failed_parse == 0

    def test_should_skip_broken_runs(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1")
        broken = state_dir / "r_broken"
        broken.mkdir(parents=True)
        (broken / "run.yaml").write_text("{{invalid yaml")
        result = harvest_all(knowledge_db, state_dir)
        assert result.harvested == 1
        assert result.failed_parse == 1

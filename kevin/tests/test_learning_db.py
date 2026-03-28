"""Tests for kevin.learning.db — SQLite schema creation and operations."""

import json
import sqlite3
from pathlib import Path

import pytest

from kevin.learning.db import connect, ensure_schema, upsert_run, upsert_block, upsert_fts, delete_fts, safe_variables_json


@pytest.fixture
def db(tmp_path: Path):
    db_path = tmp_path / "test_knowledge.db"
    conn = connect(db_path)
    ensure_schema(conn)
    yield conn
    conn.close()


class TestSchema:
    def test_should_create_tables_on_first_connect(self, db: sqlite3.Connection) -> None:
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {t[0] for t in tables}
        assert "run_history" in names
        assert "block_history" in names
        fts_check = db.execute(
            "SELECT * FROM block_logs_fts LIMIT 0"
        ).fetchall()
        assert fts_check == []


class TestUpsertRun:
    def test_should_insert_run(self, db: sqlite3.Connection) -> None:
        upsert_run(db, run_id="r1", blueprint_id="bp_test.1.0.0",
                    issue_number=42, issue_title="Add feature",
                    repo="owner/repo", status="completed",
                    total_blocks=3, passed_blocks=3,
                    failed_block_id=None, failure_reason=None,
                    elapsed_seconds=120.5, created_at="2026-03-28T10:00:00Z",
                    variables_json='{"issue_number": "42"}')
        row = db.execute("SELECT * FROM run_history WHERE run_id='r1'").fetchone()
        assert row is not None

    def test_should_upsert_same_run_id(self, db: sqlite3.Connection) -> None:
        for status in ("running", "completed"):
            upsert_run(db, run_id="r1", blueprint_id="bp_test.1.0.0",
                        issue_number=42, issue_title="Add feature",
                        repo="o/r", status=status,
                        total_blocks=3, passed_blocks=3,
                        failed_block_id=None, failure_reason=None,
                        elapsed_seconds=100.0, created_at="2026-03-28T10:00:00Z",
                        variables_json="{}")
        count = db.execute("SELECT COUNT(*) FROM run_history WHERE run_id='r1'").fetchone()[0]
        assert count == 1


class TestUpsertBlock:
    def test_should_insert_block(self, db: sqlite3.Connection) -> None:
        upsert_block(db, run_id="r1", block_id="B1", blueprint_id="bp_test.1.0.0",
                      block_name="analyze", runner="claude_cli",
                      status="passed", exit_code=0, retries=0,
                      elapsed_seconds=30.0, error=None, validator_json="[]")
        row = db.execute("SELECT * FROM block_history WHERE run_id='r1' AND block_id='B1'").fetchone()
        assert row is not None


class TestFtsIdempotency:
    def test_should_have_exactly_one_row_after_double_insert(self, db: sqlite3.Connection) -> None:
        for _ in range(2):
            delete_fts(db, run_id="r1", block_id="B1")
            upsert_fts(db, run_id="r1", block_id="B1", blueprint_id="bp_test.1.0.0",
                        status="passed", issue_title="Add feature",
                        issue_body="body text", prompt="do something",
                        output_summary="done")
        count = db.execute(
            "SELECT COUNT(*) FROM block_logs_fts WHERE run_id='r1' AND block_id='B1'"
        ).fetchone()[0]
        assert count == 1


class TestVariablesWhitelist:
    def test_should_only_serialize_safe_fields(self) -> None:
        variables = {
            "issue_number": "42",
            "issue_title": "Add feature",
            "target_repo": "/home/secret/path",
            "issue_body": "long body text...",
        }
        result = json.loads(safe_variables_json(variables))
        assert "issue_number" in result
        assert "issue_title" in result
        assert "target_repo" not in result
        assert "issue_body" not in result

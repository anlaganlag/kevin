"""Tests for kevin.learning.advisor — context query, rendering, silent degradation."""

from pathlib import Path

import pytest

from kevin.learning.advisor import (
    FailurePattern,
    LearningContext,
    SimilarSnippet,
    advise,
    format_learning_context,
)
from kevin.learning.db import connect, ensure_schema, upsert_run, upsert_block, upsert_fts, delete_fts


@pytest.fixture
def knowledge_db(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    conn = connect(db_path)
    ensure_schema(conn)
    conn.close()
    return db_path


def _seed_completed_run(db_path: Path, run_id: str, blueprint_id: str = "bp_coding_task.1.0.0",
                         status: str = "completed", failed_block: str | None = None,
                         failure_reason: str | None = None,
                         issue_title: str = "Add feature") -> None:
    conn = connect(db_path)
    ensure_schema(conn)
    upsert_run(conn, run_id=run_id, blueprint_id=blueprint_id,
               issue_number=42, issue_title=issue_title,
               repo="o/r", status=status, total_blocks=3,
               passed_blocks=2 if failed_block else 3,
               failed_block_id=failed_block, failure_reason=failure_reason,
               elapsed_seconds=120.0, created_at="2026-03-28T10:00:00Z",
               variables_json='{}')
    for bid in ["B1", "B2", "B3"]:
        s = "failed" if bid == failed_block else "passed"
        err = failure_reason if bid == failed_block else None
        upsert_block(conn, run_id=run_id, block_id=bid, blueprint_id=blueprint_id,
                      block_name=f"test_{bid}", runner="shell", status=s,
                      exit_code=0 if s == "passed" else 1, retries=0,
                      elapsed_seconds=30.0, error=err, validator_json="[]")
        if s == "passed":
            delete_fts(conn, run_id=run_id, block_id=bid)
            upsert_fts(conn, run_id=run_id, block_id=bid, blueprint_id=blueprint_id,
                        status="passed", issue_title=issue_title,
                        issue_body="some body", prompt="do stuff",
                        output_summary=f"completed {bid}")
    conn.close()


class TestAdvise:
    def test_should_return_empty_context_when_no_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "nonexistent" / "knowledge.db"
        ctx = advise(db_path, "bp_test.1.0.0", "title", "body")
        assert ctx.success_rate is None
        assert ctx.total_runs == 0
        assert ctx.common_failures == []
        assert ctx.similar_snippets == []

    def test_should_return_empty_context_when_empty_db(self, knowledge_db: Path) -> None:
        ctx = advise(knowledge_db, "bp_test.1.0.0", "title", "body")
        assert ctx.success_rate is None
        assert ctx.total_runs == 0

    def test_should_compute_blueprint_stats(self, knowledge_db: Path) -> None:
        _seed_completed_run(knowledge_db, "r1", status="completed")
        _seed_completed_run(knowledge_db, "r2", status="completed")
        _seed_completed_run(knowledge_db, "r3", status="failed", failed_block="B2",
                             failure_reason="tests failed")
        ctx = advise(knowledge_db, "bp_coding_task.1.0.0", "title", "body")
        assert ctx.total_runs == 3
        assert ctx.success_rate == pytest.approx(2 / 3, abs=0.01)

    def test_should_aggregate_common_failures(self, knowledge_db: Path) -> None:
        _seed_completed_run(knowledge_db, "r1", status="failed", failed_block="B2",
                             failure_reason="tests failed")
        _seed_completed_run(knowledge_db, "r2", status="failed", failed_block="B2",
                             failure_reason="tests failed")
        _seed_completed_run(knowledge_db, "r3", status="failed", failed_block="B3",
                             failure_reason="lint error")
        ctx = advise(knowledge_db, "bp_coding_task.1.0.0", "title", "body")
        assert len(ctx.common_failures) >= 1
        top = ctx.common_failures[0]
        assert top.block_id == "B2"
        assert top.count == 2

    def test_should_find_similar_by_issue_title(self, knowledge_db: Path) -> None:
        _seed_completed_run(knowledge_db, "r1", issue_title="Add user avatar upload")
        ctx = advise(knowledge_db, "bp_coding_task.1.0.0", "Add avatar feature", "body")
        assert len(ctx.similar_snippets) >= 1


class TestFormatLearningContext:
    def test_should_return_empty_string_for_empty_context(self) -> None:
        ctx = LearningContext(success_rate=None, total_runs=0,
                               common_failures=[], similar_snippets=[], risk_warnings=[])
        assert format_learning_context(ctx) == ""

    def test_should_contain_no_emoji_or_unicode(self) -> None:
        ctx = LearningContext(
            success_rate=0.75, total_runs=4,
            common_failures=[FailurePattern("B2", "tests failed", 3)],
            similar_snippets=[SimilarSnippet("r1", "Add feature", "done")],
            risk_warnings=["B2 failed last time"],
        )
        result = format_learning_context(ctx)
        assert all(ord(c) < 128 for c in result), f"Non-ASCII found: {result}"

    def test_should_respect_max_chars(self) -> None:
        ctx = LearningContext(
            success_rate=0.5, total_runs=100,
            common_failures=[FailurePattern("B2", "x" * 500, 10)],
            similar_snippets=[SimilarSnippet("r1", "y" * 200, "z" * 500)],
            risk_warnings=["warning " * 50],
        )
        result = format_learning_context(ctx, max_chars=200)
        assert len(result) <= 200

    def test_should_include_stats_line(self) -> None:
        ctx = LearningContext(success_rate=0.85, total_runs=20,
                               common_failures=[], similar_snippets=[], risk_warnings=[])
        result = format_learning_context(ctx)
        assert "[History]" in result
        assert "85%" in result
        assert "20 runs" in result

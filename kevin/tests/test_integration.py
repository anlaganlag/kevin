"""End-to-end integration tests for wave scheduler and learning agent."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo for use by shell-runner blocks."""
    repo = tmp_path / "target_repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        check=True, capture_output=True, cwd=str(repo),
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        check=True, capture_output=True, cwd=str(repo),
    )
    return repo


# ---------------------------------------------------------------------------
# TestWaveSchedulerIntegration
# ---------------------------------------------------------------------------


class TestWaveSchedulerIntegration:
    """Verify wave scheduler works end-to-end with real blocks."""

    def test_should_execute_parallel_shell_blocks(self, target_repo: Path) -> None:
        """Two independent shell blocks with different cwds should be scheduled in parallel."""
        from kevin.scheduler import compute_waves
        from kevin.blueprint_loader import Block

        dir_a = target_repo / "mod_a"
        dir_b = target_repo / "mod_b"
        dir_a.mkdir(exist_ok=True)
        dir_b.mkdir(exist_ok=True)

        blocks = [
            Block(
                block_id="B1", name="task_a", assigned_to="", dependencies=[],
                runner="shell", runner_config={"cwd": str(dir_a), "command": "echo a > result.txt"},
                timeout=10, max_retries=0, prompt_template="", output="",
                validators=[], acceptance_criteria=[], pre_check="", raw={},
            ),
            Block(
                block_id="B2", name="task_b", assigned_to="", dependencies=[],
                runner="shell", runner_config={"cwd": str(dir_b), "command": "echo b > result.txt"},
                timeout=10, max_retries=0, prompt_template="", output="",
                validators=[], acceptance_criteria=[], pre_check="", raw={},
            ),
        ]

        waves = compute_waves(blocks, {})
        assert len(waves) == 1
        assert len(waves[0].blocks) == 2

        from kevin.agent_runner import run_block
        for block in blocks:
            result = run_block(block, {})
            assert result.success

        assert (dir_a / "result.txt").exists()
        assert (dir_b / "result.txt").exists()


# ---------------------------------------------------------------------------
# TestLearningIntegration
# ---------------------------------------------------------------------------


class TestLearningIntegration:
    """Verify harvest + advise cycle works end-to-end."""

    def test_should_harvest_then_advise(self, tmp_path: Path) -> None:
        from kevin.learning.harvester import harvest_run
        from kevin.learning.advisor import advise

        # Setup: create a fake run state
        state_dir = tmp_path / "runs"
        run_dir = state_dir / "test-run-001"
        run_dir.mkdir(parents=True)
        logs_dir = run_dir / "logs"
        logs_dir.mkdir()

        run_data = {
            "run_id": "test-run-001",
            "blueprint_id": "bp_coding_task.1.0.0",
            "issue_number": 1,
            "repo": "test/repo",
            "status": "completed",
            "created_at": "2026-03-28T10:00:00+00:00",
            "completed_at": "2026-03-28T10:05:00+00:00",
            "variables": {"issue_number": "1", "issue_title": "Add login page"},
            "blocks": {
                "B1": {"block_id": "B1", "status": "passed", "runner": "shell",
                       "exit_code": 0, "retries": 0, "error": "",
                       "started_at": "2026-03-28T10:00:05+00:00",
                       "completed_at": "2026-03-28T10:02:00+00:00",
                       "output_summary": "login page analysis complete",
                       "validator_results": []},
            },
        }
        with (run_dir / "run.yaml").open("w") as f:
            yaml.safe_dump(run_data, f)
        (logs_dir / "B1.log").write_text(
            "=== PROMPT ===\nAnalyze login\n\n=== STDOUT ===\nlogin page analysis complete\n"
        )

        # Harvest
        db_path = tmp_path / "knowledge.db"
        harvest_run(db_path, state_dir, "test-run-001")

        # Advise — should find the harvested run
        ctx = advise(db_path, "bp_coding_task.1.0.0", "Add login feature", "body")
        assert ctx.total_runs == 1
        assert ctx.success_rate == 1.0

    def test_should_advise_empty_when_no_db(self, tmp_path: Path) -> None:
        """Advisor must silently degrade when knowledge.db doesn't exist."""
        from kevin.learning.advisor import advise
        db_path = tmp_path / "nonexistent" / "knowledge.db"
        ctx = advise(db_path, "bp_test.1.0.0", "title", "body")
        assert ctx.success_rate is None
        assert ctx.total_runs == 0
        assert ctx.common_failures == []

    def test_should_format_context_as_plain_ascii(self, tmp_path: Path) -> None:
        """Verify format_learning_context outputs only ASCII (constraint C5)."""
        from kevin.learning.advisor import format_learning_context, LearningContext, FailurePattern
        ctx = LearningContext(
            success_rate=0.8, total_runs=5,
            common_failures=[FailurePattern("B2", "test coverage below threshold", 2)],
            similar_snippets=[], risk_warnings=["Last run failed at B2"],
        )
        result = format_learning_context(ctx)
        assert result  # non-empty
        assert all(ord(c) < 128 for c in result), f"Non-ASCII in output: {result}"
        assert "[History]" in result
        assert "[Warning]" in result
        assert "[Risk]" in result

"""Seed script — generate 3 sample runs in .kevin/runs/ for dashboard demos.

Usage:
    python -m kevin.dashboard.seed --target-repo .
"""

from __future__ import annotations

import argparse
from pathlib import Path

from kevin.state import BlockState, RunState, StateManager

# ---------------------------------------------------------------------------
# Timestamps (fixed so the data looks consistent every run)
# ---------------------------------------------------------------------------

_T = {
    "r1_created":    "2026-03-27T10:00:00+00:00",
    "r1_completed":  "2026-03-27T10:08:42+00:00",
    "r1_b1_start":   "2026-03-27T10:00:05+00:00",
    "r1_b1_end":     "2026-03-27T10:02:11+00:00",
    "r1_b2_start":   "2026-03-27T10:02:15+00:00",
    "r1_b2_end":     "2026-03-27T10:05:30+00:00",
    "r1_b3_start":   "2026-03-27T10:05:35+00:00",
    "r1_b3_end":     "2026-03-27T10:08:40+00:00",

    "r2_created":    "2026-03-27T11:00:00+00:00",
    "r2_completed":  "2026-03-27T11:06:17+00:00",
    "r2_b1_start":   "2026-03-27T11:00:04+00:00",
    "r2_b1_end":     "2026-03-27T11:02:00+00:00",
    "r2_b2_start":   "2026-03-27T11:02:05+00:00",
    "r2_b2_end":     "2026-03-27T11:06:15+00:00",

    "r3_created":    "2026-03-27T12:00:00+00:00",
    "r3_b1_start":   "2026-03-27T12:00:03+00:00",
    "r3_b1_end":     "2026-03-27T12:01:55+00:00",
    "r3_b2_start":   "2026-03-27T12:02:00+00:00",
}

# ---------------------------------------------------------------------------
# Sample log content
# ---------------------------------------------------------------------------

_LOGS: dict[str, dict[str, str]] = {
    "r1_B1": {
        "prompt": "Analyze the repository structure and produce a summary of the codebase.",
        "stdout": (
            "Repository: centific-cn/demo-app\n"
            "Languages: Python 72%, TypeScript 18%, YAML 10%\n"
            "Key modules: api/, core/, tests/\n"
            "Open issues: 3 critical, 7 medium\n"
            "Analysis complete."
        ),
        "stderr": "",
    },
    "r1_B2": {
        "prompt": "Implement the feature described in issue #42 with full test coverage.",
        "stdout": (
            "Generating implementation plan...\n"
            "Writing src/features/user_export.py\n"
            "Writing tests/test_user_export.py\n"
            "Running pytest...\n"
            ".......... 10 passed in 1.23s\n"
            "Implementation complete."
        ),
        "stderr": "",
    },
    "r1_B3": {
        "prompt": "Run the full test suite and lint checks.",
        "stdout": (
            "$ pytest --tb=short -q\n"
            "............... 15 passed in 2.41s\n"
            "$ ruff check .\n"
            "All checks passed.\n"
            "Done."
        ),
        "stderr": "",
    },
    "r2_B1": {
        "prompt": "Analyze the repository structure for issue #55.",
        "stdout": (
            "Repository: centific-cn/demo-app\n"
            "Target module: src/auth/\n"
            "Existing tests: 8\n"
            "Analysis complete."
        ),
        "stderr": "",
    },
    "r2_B2": {
        "prompt": "Implement TDD-based backend feature for issue #55.",
        "stdout": (
            "Writing failing tests first...\n"
            "Writing tests/test_auth_refresh.py  [RED]\n"
            "Attempt 1/3: implementing src/auth/refresh.py\n"
            "$ pytest tests/test_auth_refresh.py\n"
            "FAILED tests/test_auth_refresh.py::test_expired_token - AssertionError\n"
            "Attempt 2/3: revising implementation\n"
            "$ pytest tests/test_auth_refresh.py\n"
            "FAILED tests/test_auth_refresh.py::test_concurrent_refresh - AssertionError\n"
            "Attempt 3/3: revising implementation\n"
            "$ pytest tests/test_auth_refresh.py\n"
            "FAILED tests/test_auth_refresh.py::test_concurrent_refresh - AssertionError\n"
            "Max retries exceeded. Block failed."
        ),
        "stderr": "AssertionError: expected 409 Conflict, got 200 OK on concurrent token refresh",
    },
    "r3_B1": {
        "prompt": "Analyze the repository structure for issue #63.",
        "stdout": (
            "Repository: centific-cn/demo-app\n"
            "Target module: src/reporting/\n"
            "Analysis complete."
        ),
        "stderr": "",
    },
    "r3_B2": {
        "prompt": "Implement the feature described in issue #63.",
        "stdout": "Generating implementation plan...\n",
        "stderr": "",
    },
}


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_run1(sm: StateManager) -> None:
    """Run 1 — completed successfully, all 3 blocks passed."""
    run = RunState(
        run_id="20260327-100000-demo01",
        blueprint_id="bp_coding_task.1.0.0",
        issue_number=42,
        repo="centific-cn/demo-app",
        status="completed",
        created_at=_T["r1_created"],
        completed_at=_T["r1_completed"],
        variables={"ISSUE_TITLE": "Export user data as CSV", "BRANCH": "feat/user-export-42"},
    )
    sm._save_run(run)

    blocks = [
        BlockState(
            block_id="B1",
            status="passed",
            runner="claude_cli",
            started_at=_T["r1_b1_start"],
            completed_at=_T["r1_b1_end"],
            exit_code=0,
            output_summary="Codebase analysis complete. 3 critical issues identified.",
            validator_results=[{"validator": "output_not_empty", "passed": True}],
        ),
        BlockState(
            block_id="B2",
            status="passed",
            runner="claude_cli",
            started_at=_T["r1_b2_start"],
            completed_at=_T["r1_b2_end"],
            exit_code=0,
            output_summary="Feature implemented. 10 tests passing.",
            validator_results=[
                {"validator": "tests_pass", "passed": True},
                {"validator": "output_not_empty", "passed": True},
            ],
        ),
        BlockState(
            block_id="B3",
            status="passed",
            runner="shell",
            started_at=_T["r1_b3_start"],
            completed_at=_T["r1_b3_end"],
            exit_code=0,
            output_summary="15 tests passed. Lint clean.",
            validator_results=[{"validator": "exit_code_zero", "passed": True}],
        ),
    ]
    for block in blocks:
        run.blocks[block.block_id] = block
        sm._save_block(run.run_id, block)

    log_key_map = {"B1": "r1_B1", "B2": "r1_B2", "B3": "r1_B3"}
    for block in blocks:
        logs = _LOGS[log_key_map[block.block_id]]
        sm.save_block_logs(run.run_id, block.block_id, **logs)

    sm._save_run(run)


def _seed_run2(sm: StateManager) -> None:
    """Run 2 — failed at B2, B1 passed, B2 failed after retries."""
    run = RunState(
        run_id="20260327-110000-demo02",
        blueprint_id="bp_backend_coding_tdd_automation.1.0.0",
        issue_number=55,
        repo="centific-cn/demo-app",
        status="failed",
        created_at=_T["r2_created"],
        completed_at=_T["r2_completed"],
        variables={"ISSUE_TITLE": "Token refresh race condition", "BRANCH": "feat/auth-refresh-55"},
    )
    sm._save_run(run)

    blocks = [
        BlockState(
            block_id="B1",
            status="passed",
            runner="claude_cli",
            started_at=_T["r2_b1_start"],
            completed_at=_T["r2_b1_end"],
            exit_code=0,
            output_summary="Codebase analysis complete.",
            validator_results=[{"validator": "output_not_empty", "passed": True}],
        ),
        BlockState(
            block_id="B2",
            status="failed",
            runner="claude_cli",
            started_at=_T["r2_b2_start"],
            completed_at=_T["r2_b2_end"],
            exit_code=1,
            output_summary="Tests failed after 3 attempts.",
            validator_results=[{"validator": "tests_pass", "passed": False}],
            retries=2,
            error=(
                "test_concurrent_refresh FAILED — expected 409 Conflict, got 200 OK. "
                "Race condition in token invalidation logic not resolved within max retries."
            ),
        ),
    ]
    for block in blocks:
        run.blocks[block.block_id] = block
        sm._save_block(run.run_id, block)

    log_key_map = {"B1": "r2_B1", "B2": "r2_B2"}
    for block in blocks:
        logs = _LOGS[log_key_map[block.block_id]]
        sm.save_block_logs(run.run_id, block.block_id, **logs)

    sm._save_run(run)


def _seed_run3(sm: StateManager) -> None:
    """Run 3 — currently running: B1 passed, B2 running, B3 pending."""
    run = RunState(
        run_id="20260327-120000-demo03",
        blueprint_id="bp_coding_task.1.0.0",
        issue_number=63,
        repo="centific-cn/demo-app",
        status="running",
        created_at=_T["r3_created"],
        completed_at="",
        variables={"ISSUE_TITLE": "Add PDF export to reports", "BRANCH": "feat/pdf-export-63"},
    )
    sm._save_run(run)

    blocks = [
        BlockState(
            block_id="B1",
            status="passed",
            runner="claude_cli",
            started_at=_T["r3_b1_start"],
            completed_at=_T["r3_b1_end"],
            exit_code=0,
            output_summary="Codebase analysis complete.",
            validator_results=[{"validator": "output_not_empty", "passed": True}],
        ),
        BlockState(
            block_id="B2",
            status="running",
            runner="claude_cli",
            started_at=_T["r3_b2_start"],
            completed_at="",
            exit_code=None,
            output_summary="",
            validator_results=[],
        ),
        BlockState(
            block_id="B3",
            status="pending",
            runner="shell",
            started_at="",
            completed_at="",
            exit_code=None,
            output_summary="",
            validator_results=[],
        ),
    ]
    for block in blocks:
        run.blocks[block.block_id] = block
        sm._save_block(run.run_id, block)

    sm.save_block_logs(run.run_id, "B1", **_LOGS["r3_B1"])
    sm.save_block_logs(run.run_id, "B2", **_LOGS["r3_B2"])

    sm._save_run(run)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo run data for the Kevin dashboard.")
    parser.add_argument(
        "--target-repo",
        default=".",
        help="Root of the repo (default: current directory)",
    )
    args = parser.parse_args()

    state_dir = Path(args.target_repo) / ".kevin" / "runs"
    state_dir.mkdir(parents=True, exist_ok=True)

    sm = StateManager(state_dir)

    _seed_run1(sm)
    _seed_run2(sm)
    _seed_run3(sm)

    print(f"Seeded 3 demo runs in {state_dir}")


if __name__ == "__main__":
    main()

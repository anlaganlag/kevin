"""Tests for _execute_agentic() — core agentic execution path in kevin/cli.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kevin.config import KevinConfig
from kevin.state import StateManager
from kevin.workers.interface import ArtifactType, WorkerArtifact, WorkerResult

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent.parent / "blueprints"
BP_CODING_TASK = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"
BP_PLANNING_AGENT = BLUEPRINTS_DIR / "bp_planning_agent.1.0.0.yaml"


def _make_config(tmp_path: Path, *, dry_run: bool = False) -> KevinConfig:
    return KevinConfig(
        kevin_root=Path(__file__).resolve().parent.parent.parent,
        blueprints_dir=BLUEPRINTS_DIR,
        target_repo=tmp_path,
        state_dir=tmp_path / ".kevin" / "runs",
        repo_owner="acme",
        repo_name="app",
        dry_run=dry_run,
    )


SAMPLE_VARS = {
    "issue_number": "99",
    "issue_title": "Test",
    "issue_body": "",
    "issue_labels": "",
    "target_repo": "/tmp/test",
    "owner": "acme",
    "repo": "app",
    "repo_full": "acme/app",
    "learning_context": "",
    "pr_number": "",
}


def _make_run(state_mgr: StateManager, bp_id: str = "bp_coding_task.1.0.0") -> "RunState":
    return state_mgr.create_run(
        blueprint_id=bp_id,
        issue_number=99,
        repo="acme/app",
        variables=SAMPLE_VARS,
    )


def _success_result(*, stdout: str = "Done", pr_url: str | None = None) -> WorkerResult:
    artifacts = []
    if pr_url:
        artifacts.append(WorkerArtifact(
            artifact_type=ArtifactType.PR_URL,
            name="pr",
            location=pr_url,
        ))
    return WorkerResult(
        success=True,
        exit_code=0,
        stdout=stdout,
        stderr="",
        duration_seconds=12.0,
        artifacts=artifacts,
    )


def _failure_result() -> WorkerResult:
    return WorkerResult(
        success=False,
        exit_code=1,
        failure_detail="worker crashed",
        stdout="",
        stderr="boom",
        duration_seconds=5.0,
    )


# Shared patch targets
_PATCHES = {
    "registry": "kevin.workers.registry.WorkerRegistry",
    "notify": "kevin.cli._notify_teams",
    "comment": "kevin.cli._post_completion_comment_agentic",
    "remove_labels": "kevin.cli.remove_labels",
    "add_labels": "kevin.cli.add_labels",
    "close_issue": "kevin.cli.close_issue",
    "validators": "kevin.executor.run_post_validators",
    "harvest": "kevin.learning.harvest_run",
}


def _patch_all(**overrides):
    """Return a dict of patch context managers for all external deps."""
    targets = {**_PATCHES, **overrides}
    return {name: patch(target) for name, target in targets.items()}


# ---------------------------------------------------------------------------
# Helpers to invoke _execute_agentic with standard mocking
# ---------------------------------------------------------------------------

def _run_agentic(
    tmp_path: Path,
    *,
    bp_path: Path = BP_CODING_TASK,
    dry_run: bool = False,
    worker_result: WorkerResult | None = None,
    validator_results: list[dict] | None = None,
    validator_exception: Exception | None = None,
):
    """Convenience: set up config, state, mocks and call _execute_agentic."""
    from kevin.cli import _execute_agentic

    config = _make_config(tmp_path, dry_run=dry_run)
    state_mgr = StateManager(config.state_dir)
    run = _make_run(state_mgr)

    if worker_result is None:
        worker_result = _success_result(pr_url="https://github.com/acme/app/pull/42")

    if validator_results is None:
        validator_results = [{"name": "lint", "passed": True}]

    mock_worker = MagicMock()
    mock_worker.worker_id = "claude-code"
    mock_worker.execute.return_value = worker_result

    mock_registry_cls = MagicMock()
    mock_registry_cls.return_value.resolve.return_value = mock_worker

    with (
        patch(_PATCHES["registry"], mock_registry_cls),
        patch(_PATCHES["notify"]),
        patch(_PATCHES["comment"]),
        patch(_PATCHES["remove_labels"]),
        patch(_PATCHES["add_labels"]),
        patch(_PATCHES["close_issue"]),
        patch(_PATCHES["harvest"]),
        patch(_PATCHES["validators"]) as mock_validators,
    ):
        if validator_exception:
            mock_validators.side_effect = validator_exception
        else:
            mock_validators.return_value = validator_results

        rc = _execute_agentic(config, state_mgr, run, bp_path, SAMPLE_VARS)

    return rc, run, state_mgr, mock_worker


# ===========================================================================
# TestExecuteAgenticHappyPath
# ===========================================================================


class TestExecuteAgenticHappyPath:
    def test_should_return_zero_on_full_success(self, tmp_path: Path):
        rc, _run, _sm, mock_worker = _run_agentic(
            tmp_path,
            worker_result=_success_result(
                stdout="Created PR",
                pr_url="https://github.com/acme/app/pull/42",
            ),
            validator_results=[{"name": "lint", "passed": True}],
        )
        assert rc == 0
        mock_worker.execute.assert_called_once()


# ===========================================================================
# TestExecuteAgenticFailures
# ===========================================================================


class TestExecuteAgenticFailures:
    def test_should_return_one_when_blueprint_path_missing(self, tmp_path: Path):
        rc, *_ = _run_agentic(
            tmp_path,
            bp_path=tmp_path / "nonexistent.yaml",
        )
        assert rc == 1

    def test_should_return_one_for_non_executable_blueprint(self, tmp_path: Path):
        rc, *_ = _run_agentic(
            tmp_path,
            bp_path=BP_PLANNING_AGENT,
        )
        assert rc == 1

    def test_should_return_one_when_worker_fails(self, tmp_path: Path):
        rc, *_ = _run_agentic(
            tmp_path,
            worker_result=_failure_result(),
        )
        assert rc == 1

    def test_should_return_one_when_validators_fail(self, tmp_path: Path):
        rc, *_ = _run_agentic(
            tmp_path,
            validator_results=[{"name": "lint", "passed": False, "error": "bad"}],
        )
        assert rc == 1

    def test_should_handle_validator_exception_gracefully(self, tmp_path: Path):
        rc, *_ = _run_agentic(
            tmp_path,
            validator_exception=RuntimeError("validator exploded"),
        )
        assert rc == 1


# ===========================================================================
# TestExecuteAgenticDryRun
# ===========================================================================


class TestExecuteAgenticDryRun:
    def test_should_skip_worker_in_dry_run(self, tmp_path: Path):
        rc, _run, _sm, mock_worker = _run_agentic(
            tmp_path,
            dry_run=True,
        )
        assert rc == 0
        mock_worker.execute.assert_not_called()


# ===========================================================================
# TestExecuteAgenticStateManagement
# ===========================================================================


class TestExecuteAgenticStateManagement:
    def test_should_persist_executor_logs(self, tmp_path: Path):
        rc, run, state_mgr, _ = _run_agentic(tmp_path)
        assert rc == 0

        log_path = tmp_path / ".kevin" / "runs" / run.run_id / "logs" / "executor.log"
        assert log_path.exists()
        content = log_path.read_text()
        assert "COMPILED PROMPT" in content
        assert "STDOUT" in content

    def test_should_persist_run_state_on_completion(self, tmp_path: Path):
        rc, run, state_mgr, _ = _run_agentic(
            tmp_path,
            worker_result=_success_result(
                stdout="Created PR",
                pr_url="https://github.com/acme/app/pull/42",
            ),
            validator_results=[{"name": "lint", "passed": True}],
        )
        assert rc == 0

        reloaded = state_mgr.load_run(run.run_id)
        assert reloaded.status == "completed"
        assert reloaded.completion_status == "all_passed"
        assert reloaded.pr_number == 42

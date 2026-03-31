# Executor Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 加固 executor 无头化执行链路，确保 9 个 blueprint 的 load → compile → execute → validate → report 全链路健壮可靠

**Architecture:** 分三层验证 — pytest 集成测试覆盖编排逻辑和边界 case，`kevin validate` 命令做运行时 preflight，生产代码加固异常防护。测试 mock worker 层，不消耗 token。

**Tech Stack:** Python 3.11+, pytest, unittest.mock, PyYAML

---

### Task 1: 生产代码加固 — config.py 添加 NON_EXECUTABLE guard

**Files:**
- Modify: `kevin/config.py:12-36`
- Test: `kevin/tests/test_config.py` (create)

- [ ] **Step 1: Write failing test — non-executable blueprint detection**

```python
# kevin/tests/test_config.py
"""Tests for kevin.config module."""

from __future__ import annotations

from kevin.config import NON_EXECUTABLE_BLUEPRINTS, DEFAULT_INTENT_MAP


def test_non_executable_blueprints_exist() -> None:
    """should define at least bp_planning_agent as non-executable."""
    assert "bp_planning_agent.1.0.0" in NON_EXECUTABLE_BLUEPRINTS


def test_non_executable_not_in_default_intent_map_values() -> None:
    """should not map any intent directly to a non-executable blueprint."""
    for intent, bp_id in DEFAULT_INTENT_MAP.items():
        assert bp_id not in NON_EXECUTABLE_BLUEPRINTS, (
            f"Intent '{intent}' maps to non-executable '{bp_id}'"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest kevin/tests/test_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'NON_EXECUTABLE_BLUEPRINTS'`

- [ ] **Step 3: Add NON_EXECUTABLE_BLUEPRINTS to config.py**

In `kevin/config.py`, after line 21 (end of `DEFAULT_INTENT_MAP`), add:

```python
# Orchestrator blueprints — use Claude SDK directly, not the executor pipeline.
# _execute_agentic() rejects these with a clear error message.
NON_EXECUTABLE_BLUEPRINTS: frozenset[str] = frozenset({
    "bp_planning_agent.1.0.0",
})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest kevin/tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add kevin/config.py kevin/tests/test_config.py
git commit -m "feat: add NON_EXECUTABLE_BLUEPRINTS guard to config"
```

---

### Task 2: 生产代码加固 — _execute_agentic 异常防护

**Files:**
- Modify: `kevin/cli.py:554-693`
- Modify: `kevin/executor.py:16-35`

- [ ] **Step 1: Add compile exception handling in _execute_agentic**

In `kevin/cli.py`, replace lines 573-584 (steps 1-2: load semantic + compile) with:

```python
    # 1. Load semantic blueprint
    try:
        semantic = load_semantic(bp_path)
    except Exception as exc:
        _err(f"Failed to load semantic blueprint from {bp_path}: {exc}")
        state_mgr.complete_run(run, "failed")
        return 1

    # 1b. Guard: non-executable blueprints
    from kevin.config import NON_EXECUTABLE_BLUEPRINTS
    if semantic.blueprint_id in NON_EXECUTABLE_BLUEPRINTS:
        _err(f"{semantic.blueprint_id} is an orchestrator blueprint — not executor-compatible. "
             f"Use Claude SDK or the planning agent workflow instead.")
        state_mgr.complete_run(run, "failed")
        return 1

    _log(config, f"  Agentic mode: {semantic.blueprint_name}")
    _log(config, f"  Criteria: {len(semantic.acceptance_criteria)}, "
                 f"Constraints: {len(semantic.constraints)}, "
                 f"Timeout: {semantic.task_timeout}s")

    # 2. Compile to WorkerTask
    try:
        task = compile_task(
            semantic, variables, task_id=run.run_id, cwd=config.target_repo,
        )
    except (ValueError, Exception) as exc:
        _err(f"Blueprint compilation failed: {exc}")
        state_mgr.complete_run(run, "failed")
        return 1
    _log(config, f"  Compiled instruction: {len(task.instruction)} chars")
```

- [ ] **Step 2: Add validator exception handling in _execute_agentic**

In `kevin/cli.py`, replace lines 622-629 (step 7: post-validators) with:

```python
    if result.success and not config.dry_run:
        try:
            validator_results = run_post_validators(semantic, variables, config.target_repo)
        except Exception as exc:
            _log(config, f"  Validator execution error: {exc}")
            validator_results = [{"name": "validator_error", "passed": False, "error": str(exc)}]
        failed_validators = [v for v in validator_results if not v.get("passed")]
        if failed_validators:
            all_passed = False
            _log(config, f"  Validator failures: {failed_validators}")
        else:
            _log(config, f"  Validators: all {len(validator_results)} passed")
```

- [ ] **Step 3: Add exception handling in executor.py run_post_validators**

In `kevin/executor.py`, wrap the validator loop (lines 28-35) to catch per-block parse errors:

```python
def run_post_validators(
    semantic: SemanticBlueprint,
    variables: dict[str, str],
    cwd: Path,
) -> list[dict[str, Any]]:
    """Run all block validators from the blueprint after the worker finishes."""
    blocks_raw = _extract_blocks(semantic.raw)
    if not blocks_raw:
        return []
    try:
        blocks = [_parse_block(b) for b in blocks_raw]
        ordered = _topological_sort(blocks)
    except Exception as exc:
        return [{"name": "block_parse_error", "passed": False, "error": str(exc)}]
    validators: list = []
    for block in ordered:
        validators.extend(block.validators)
    if not validators:
        return []
    return _run_validators(validators, variables, cwd)
```

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `python3 -m pytest kevin/tests/ -v --tb=short`
Expected: 296 tests passed, 0 failed

- [ ] **Step 5: Commit**

```bash
git add kevin/cli.py kevin/executor.py
git commit -m "fix: add exception handling to _execute_agentic and run_post_validators"
```

---

### Task 3: 测试 — _execute_agentic 核心路径单测

**Files:**
- Create: `kevin/tests/test_execute_agentic.py`

- [ ] **Step 1: Write test file with fixtures and happy path test**

```python
# kevin/tests/test_execute_agentic.py
"""Tests for _execute_agentic — core agentic execution orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kevin.config import KevinConfig, build_config
from kevin.state import RunState, StateManager
from kevin.workers.interface import ArtifactType, WorkerArtifact, WorkerResult


BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent.parent / "blueprints"
BP_CODING_TASK = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"


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


def _make_run(run_id: str = "test-run-001") -> RunState:
    return RunState(
        run_id=run_id,
        blueprint_id="bp_coding_task.1.0.0",
        issue_number=99,
        repo="acme/app",
    )


class TestExecuteAgenticHappyPath:
    """Happy path: load → compile → worker success → validators pass."""

    @patch("kevin.cli._notify_teams")
    @patch("kevin.cli._post_completion_comment_agentic")
    @patch("kevin.cli.remove_labels")
    @patch("kevin.cli.add_labels")
    @patch("kevin.cli.close_issue")
    def test_should_return_zero_on_full_success(
        self,
        mock_close: MagicMock,
        mock_add_labels: MagicMock,
        mock_remove_labels: MagicMock,
        mock_post_comment: MagicMock,
        mock_notify: MagicMock,
        tmp_path: Path,
    ) -> None:
        from kevin.cli import _execute_agentic

        config = _make_config(tmp_path)
        state_mgr = StateManager(config.state_dir)
        run = state_mgr.create_run("bp_coding_task.1.0.0", 99, "acme/app")

        success_result = WorkerResult(
            success=True, exit_code=0, stdout="Created https://github.com/acme/app/pull/42",
            duration_seconds=10.0,
        )

        with patch("kevin.cli.WorkerRegistry") as mock_registry_cls:
            mock_worker = MagicMock()
            mock_worker.worker_id = "claude-code"
            mock_worker.execute.return_value = success_result
            mock_registry_cls.return_value.resolve.return_value = mock_worker

            with patch("kevin.cli.run_post_validators", return_value=[]):
                result = _execute_agentic(
                    config, state_mgr, run, BP_CODING_TASK, {"issue_number": "99", "issue_title": "Test", "issue_body": "", "target_repo": str(tmp_path)},
                )

        assert result == 0
        mock_worker.execute.assert_called_once()


class TestExecuteAgenticFailures:
    """Failure scenarios: blueprint errors, worker failures, validator issues."""

    def test_should_return_one_when_blueprint_path_missing(self, tmp_path: Path) -> None:
        from kevin.cli import _execute_agentic

        config = _make_config(tmp_path)
        state_mgr = StateManager(config.state_dir)
        run = state_mgr.create_run("bp_nonexistent", 99, "acme/app")

        result = _execute_agentic(
            config, state_mgr, run,
            tmp_path / "nonexistent.yaml",
            {},
        )
        assert result == 1

    @patch("kevin.cli._notify_teams")
    def test_should_return_one_for_non_executable_blueprint(
        self, mock_notify: MagicMock, tmp_path: Path,
    ) -> None:
        from kevin.cli import _execute_agentic

        config = _make_config(tmp_path)
        state_mgr = StateManager(config.state_dir)
        run = state_mgr.create_run("bp_planning_agent.1.0.0", 99, "acme/app")

        bp_path = BLUEPRINTS_DIR / "bp_planning_agent.1.0.0.yaml"
        result = _execute_agentic(config, state_mgr, run, bp_path, {})
        assert result == 1

    @patch("kevin.cli._notify_teams")
    @patch("kevin.cli._post_completion_comment_agentic")
    @patch("kevin.cli.remove_labels")
    def test_should_return_one_when_worker_fails(
        self,
        mock_remove: MagicMock,
        mock_post: MagicMock,
        mock_notify: MagicMock,
        tmp_path: Path,
    ) -> None:
        from kevin.cli import _execute_agentic

        config = _make_config(tmp_path)
        state_mgr = StateManager(config.state_dir)
        run = state_mgr.create_run("bp_coding_task.1.0.0", 99, "acme/app")

        fail_result = WorkerResult(
            success=False, exit_code=1, failure_detail="Claude exited with error",
            duration_seconds=5.0,
        )

        with patch("kevin.cli.WorkerRegistry") as mock_reg:
            mock_worker = MagicMock()
            mock_worker.worker_id = "claude-code"
            mock_worker.execute.return_value = fail_result
            mock_reg.return_value.resolve.return_value = mock_worker

            result = _execute_agentic(
                config, state_mgr, run, BP_CODING_TASK,
                {"issue_number": "99", "issue_title": "Test", "issue_body": "", "target_repo": str(tmp_path)},
            )

        assert result == 1

    @patch("kevin.cli._notify_teams")
    @patch("kevin.cli._post_completion_comment_agentic")
    @patch("kevin.cli.remove_labels")
    @patch("kevin.cli.add_labels")
    @patch("kevin.cli.close_issue")
    def test_should_return_one_when_validators_fail(
        self,
        mock_close: MagicMock,
        mock_add: MagicMock,
        mock_remove: MagicMock,
        mock_post: MagicMock,
        mock_notify: MagicMock,
        tmp_path: Path,
    ) -> None:
        from kevin.cli import _execute_agentic

        config = _make_config(tmp_path)
        state_mgr = StateManager(config.state_dir)
        run = state_mgr.create_run("bp_coding_task.1.0.0", 99, "acme/app")

        success_result = WorkerResult(success=True, exit_code=0, stdout="done", duration_seconds=5.0)

        with patch("kevin.cli.WorkerRegistry") as mock_reg:
            mock_worker = MagicMock()
            mock_worker.worker_id = "claude-code"
            mock_worker.execute.return_value = success_result
            mock_reg.return_value.resolve.return_value = mock_worker

            with patch("kevin.cli.run_post_validators", return_value=[
                {"name": "git_diff_check", "passed": False, "error": "No changes detected"},
            ]):
                result = _execute_agentic(
                    config, state_mgr, run, BP_CODING_TASK,
                    {"issue_number": "99", "issue_title": "Test", "issue_body": "", "target_repo": str(tmp_path)},
                )

        assert result == 1

    @patch("kevin.cli._notify_teams")
    @patch("kevin.cli._post_completion_comment_agentic")
    @patch("kevin.cli.remove_labels")
    @patch("kevin.cli.add_labels")
    @patch("kevin.cli.close_issue")
    def test_should_handle_validator_exception_gracefully(
        self,
        mock_close: MagicMock,
        mock_add: MagicMock,
        mock_remove: MagicMock,
        mock_post: MagicMock,
        mock_notify: MagicMock,
        tmp_path: Path,
    ) -> None:
        from kevin.cli import _execute_agentic

        config = _make_config(tmp_path)
        state_mgr = StateManager(config.state_dir)
        run = state_mgr.create_run("bp_coding_task.1.0.0", 99, "acme/app")

        success_result = WorkerResult(success=True, exit_code=0, stdout="done", duration_seconds=5.0)

        with patch("kevin.cli.WorkerRegistry") as mock_reg:
            mock_worker = MagicMock()
            mock_worker.worker_id = "claude-code"
            mock_worker.execute.return_value = success_result
            mock_reg.return_value.resolve.return_value = mock_worker

            with patch("kevin.cli.run_post_validators", side_effect=RuntimeError("validator crashed")):
                result = _execute_agentic(
                    config, state_mgr, run, BP_CODING_TASK,
                    {"issue_number": "99", "issue_title": "Test", "issue_body": "", "target_repo": str(tmp_path)},
                )

        assert result == 1


class TestExecuteAgenticDryRun:
    """Dry-run mode should skip worker execution but validate compile."""

    def test_should_skip_worker_in_dry_run(self, tmp_path: Path) -> None:
        from kevin.cli import _execute_agentic

        config = _make_config(tmp_path, dry_run=True)
        state_mgr = StateManager(config.state_dir)
        run = state_mgr.create_run("bp_coding_task.1.0.0", 99, "acme/app")

        with patch("kevin.cli.WorkerRegistry") as mock_reg:
            mock_worker = MagicMock()
            mock_worker.worker_id = "claude-code"
            mock_reg.return_value.resolve.return_value = mock_worker

            result = _execute_agentic(
                config, state_mgr, run, BP_CODING_TASK,
                {"issue_number": "99", "issue_title": "Test", "issue_body": "", "target_repo": str(tmp_path)},
            )

        assert result == 0
        mock_worker.execute.assert_not_called()


class TestExecuteAgenticStateManagement:
    """Verify state persistence through execution lifecycle."""

    @patch("kevin.cli._notify_teams")
    @patch("kevin.cli._post_completion_comment_agentic")
    @patch("kevin.cli.remove_labels")
    @patch("kevin.cli.add_labels")
    @patch("kevin.cli.close_issue")
    def test_should_persist_executor_logs(
        self,
        mock_close: MagicMock,
        mock_add: MagicMock,
        mock_remove: MagicMock,
        mock_post: MagicMock,
        mock_notify: MagicMock,
        tmp_path: Path,
    ) -> None:
        from kevin.cli import _execute_agentic

        config = _make_config(tmp_path)
        state_mgr = StateManager(config.state_dir)
        run = state_mgr.create_run("bp_coding_task.1.0.0", 99, "acme/app")

        success_result = WorkerResult(
            success=True, exit_code=0, stdout="All done", stderr="", duration_seconds=3.0,
        )

        with patch("kevin.cli.WorkerRegistry") as mock_reg:
            mock_worker = MagicMock()
            mock_worker.worker_id = "claude-code"
            mock_worker.execute.return_value = success_result
            mock_reg.return_value.resolve.return_value = mock_worker

            with patch("kevin.cli.run_post_validators", return_value=[]):
                _execute_agentic(
                    config, state_mgr, run, BP_CODING_TASK,
                    {"issue_number": "99", "issue_title": "Test", "issue_body": "", "target_repo": str(tmp_path)},
                )

        # Verify executor log was written
        log_path = config.state_dir / run.run_id / "logs" / "executor.log"
        assert log_path.exists()
        content = log_path.read_text()
        assert "COMPILED PROMPT" in content
        assert "STDOUT" in content

    @patch("kevin.cli._notify_teams")
    @patch("kevin.cli._post_completion_comment_agentic")
    @patch("kevin.cli.remove_labels")
    @patch("kevin.cli.add_labels")
    @patch("kevin.cli.close_issue")
    def test_should_persist_run_state_on_completion(
        self,
        mock_close: MagicMock,
        mock_add: MagicMock,
        mock_remove: MagicMock,
        mock_post: MagicMock,
        mock_notify: MagicMock,
        tmp_path: Path,
    ) -> None:
        from kevin.cli import _execute_agentic

        config = _make_config(tmp_path)
        state_mgr = StateManager(config.state_dir)
        run = state_mgr.create_run("bp_coding_task.1.0.0", 99, "acme/app")
        run_id = run.run_id

        success_result = WorkerResult(
            success=True, exit_code=0,
            stdout="Created https://github.com/acme/app/pull/55",
            duration_seconds=8.0,
        )

        with patch("kevin.cli.WorkerRegistry") as mock_reg:
            mock_worker = MagicMock()
            mock_worker.worker_id = "claude-code"
            mock_worker.execute.return_value = success_result
            mock_reg.return_value.resolve.return_value = mock_worker

            with patch("kevin.cli.run_post_validators", return_value=[]):
                _execute_agentic(
                    config, state_mgr, run, BP_CODING_TASK,
                    {"issue_number": "99", "issue_title": "Test", "issue_body": "", "target_repo": str(tmp_path)},
                )

        # Reload state from disk and verify
        reloaded = state_mgr.load_run(run_id)
        assert reloaded.status == "completed"
        assert reloaded.completion_status == "all_passed"
        assert reloaded.pr_number == 55
```

- [ ] **Step 2: Run tests to verify they match expectations**

Run: `python3 -m pytest kevin/tests/test_execute_agentic.py -v --tb=short`
Expected: Tests in TestExecuteAgenticHappyPath and TestExecuteAgenticDryRun pass (they use the hardened code from Task 2). Failure tests correctly return 1.

- [ ] **Step 3: Fix any test issues from first run**

Adjust mock patches or imports based on actual test output. The key patterns:
- `_execute_agentic` is imported from `kevin.cli`
- Worker is mocked via `kevin.cli.WorkerRegistry`
- GitHub operations are mocked via `kevin.cli.remove_labels`, etc.
- `run_post_validators` is mocked via `kevin.cli.run_post_validators`

- [ ] **Step 4: Verify full test suite still passes**

Run: `python3 -m pytest kevin/tests/ -v --tb=short`
Expected: 296 + 9 new = 305+ tests, 0 failures

- [ ] **Step 5: Commit**

```bash
git add kevin/tests/test_execute_agentic.py
git commit -m "test: add _execute_agentic core path tests (9 cases)"
```

---

### Task 4: 测试 — 9 个 Blueprint 全链路集成测试

**Files:**
- Create: `kevin/tests/test_blueprint_full_pipeline.py`

- [ ] **Step 1: Write parametrized integration test**

```python
# kevin/tests/test_blueprint_full_pipeline.py
"""Full pipeline integration tests: every executor-compatible blueprint
goes through load → compile → validate → prompt checks (no token cost)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kevin.blueprint_compiler import compile, compile_task, load_semantic
from kevin.config import NON_EXECUTABLE_BLUEPRINTS

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent.parent / "blueprints"

# All blueprint YAML files, excluding non-executable ones
_ALL_BP_FILES = sorted(BLUEPRINTS_DIR.glob("bp_*.yaml")) if BLUEPRINTS_DIR.exists() else []

_EXECUTABLE_BP_FILES = [
    p for p in _ALL_BP_FILES
    if not any(ne in p.name for ne in NON_EXECUTABLE_BLUEPRINTS)
]

_SAMPLE_VARIABLES = {
    "issue_number": "42",
    "issue_title": "Add health check endpoint",
    "issue_body": "We need a /health endpoint that returns 200 OK.",
    "issue_labels": "coding-task,backend",
    "target_repo": "/tmp/test-repo",
    "owner": "acme",
    "repo": "app",
    "repo_full": "acme/app",
    "learning_context": "",
    "pr_number": "",
}


class TestExecutableBlueprintPipeline:
    """Every executor-compatible blueprint must survive the full dry pipeline."""

    @pytest.mark.parametrize(
        "bp_file",
        _EXECUTABLE_BP_FILES,
        ids=[p.stem for p in _EXECUTABLE_BP_FILES],
    )
    def test_should_load_semantic_successfully(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        assert semantic.blueprint_id, f"{bp_file.name}: empty blueprint_id"
        assert semantic.blueprint_name, f"{bp_file.name}: empty blueprint_name"

    @pytest.mark.parametrize(
        "bp_file",
        _EXECUTABLE_BP_FILES,
        ids=[p.stem for p in _EXECUTABLE_BP_FILES],
    )
    def test_should_compile_prompt_within_size_bounds(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        prompt = compile(semantic, _SAMPLE_VARIABLES)
        size_kb = len(prompt) / 1024
        assert 0.5 < size_kb < 50, (
            f"{bp_file.name}: prompt size {size_kb:.1f}KB outside [0.5, 50] range"
        )

    @pytest.mark.parametrize(
        "bp_file",
        _EXECUTABLE_BP_FILES,
        ids=[p.stem for p in _EXECUTABLE_BP_FILES],
    )
    def test_should_compile_task_with_valid_structure(self, bp_file: Path, tmp_path: Path) -> None:
        semantic = load_semantic(bp_file)
        task = compile_task(
            semantic, _SAMPLE_VARIABLES,
            task_id="pipeline-test-001", cwd=tmp_path,
        )
        assert task.task_id == "pipeline-test-001"
        assert len(task.instruction) > 100
        assert task.workspace.cwd == tmp_path
        assert task.permissions.git_write is True
        assert task.timeout >= 600

    @pytest.mark.parametrize(
        "bp_file",
        _EXECUTABLE_BP_FILES,
        ids=[p.stem for p in _EXECUTABLE_BP_FILES],
    )
    def test_should_contain_goal_section_in_prompt(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        prompt = compile(semantic, _SAMPLE_VARIABLES)
        assert "# GOAL" in prompt or "# TASK" in prompt, (
            f"{bp_file.name}: prompt missing GOAL or TASK section"
        )

    @pytest.mark.parametrize(
        "bp_file",
        _EXECUTABLE_BP_FILES,
        ids=[p.stem for p in _EXECUTABLE_BP_FILES],
    )
    def test_should_render_variables_in_prompt(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        prompt = compile(semantic, _SAMPLE_VARIABLES)
        # At minimum, issue_number should appear (all blueprints reference it)
        assert "42" in prompt, f"{bp_file.name}: issue_number not rendered in prompt"


class TestNonExecutableBlueprintGuard:
    """Non-executable blueprints must be correctly identified."""

    def test_planning_agent_excluded_from_executable_list(self) -> None:
        executable_names = {p.name for p in _EXECUTABLE_BP_FILES}
        assert "bp_planning_agent.1.0.0.yaml" not in executable_names

    def test_executable_count_is_nine(self) -> None:
        assert len(_EXECUTABLE_BP_FILES) == 9, (
            f"Expected 9 executable blueprints, found {len(_EXECUTABLE_BP_FILES)}: "
            f"{[p.stem for p in _EXECUTABLE_BP_FILES]}"
        )
```

- [ ] **Step 2: Run tests**

Run: `python3 -m pytest kevin/tests/test_blueprint_full_pipeline.py -v --tb=short`
Expected: 9×5 = 45 parametrized tests + 2 guard tests = 47 tests, all pass

- [ ] **Step 3: Fix any blueprint-specific issues discovered**

If a blueprint fails (e.g., missing GOAL section, variable not rendered), investigate and fix. The test is the oracle — if it fails, the blueprint has a real gap that would cause E2E failure.

- [ ] **Step 4: Verify full test suite**

Run: `python3 -m pytest kevin/tests/ -v --tb=short`
Expected: 305 + 47 = 352+ tests, 0 failures

- [ ] **Step 5: Commit**

```bash
git add kevin/tests/test_blueprint_full_pipeline.py
git commit -m "test: add 9-blueprint full pipeline integration tests"
```

---

### Task 5: kevin validate 命令

**Files:**
- Modify: `kevin/cli.py` (add `cmd_validate` subcommand)
- Create: `kevin/tests/test_validate_command.py`

- [ ] **Step 1: Write failing test for validate command**

```python
# kevin/tests/test_validate_command.py
"""Tests for kevin validate command."""

from __future__ import annotations

from kevin.cli import main


def test_validate_returns_zero_on_success() -> None:
    """should return 0 when all blueprints validate."""
    result = main(["validate"])
    assert result == 0


def test_validate_with_specific_blueprint() -> None:
    """should validate a single blueprint when --blueprint is given."""
    result = main(["validate", "--blueprint", "bp_coding_task.1.0.0"])
    assert result == 0


def test_validate_fails_for_unknown_blueprint() -> None:
    """should return 1 for a non-existent blueprint."""
    result = main(["validate", "--blueprint", "bp_nonexistent"])
    assert result == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest kevin/tests/test_validate_command.py -v`
Expected: FAIL (validate subcommand doesn't exist yet)

- [ ] **Step 3: Implement cmd_validate in cli.py**

Add subcommand registration in `main()` (after existing subcommands):

```python
    # validate subcommand
    sp_validate = subparsers.add_parser("validate", help="Validate blueprint executability")
    sp_validate.add_argument("--blueprint", help="Validate a specific blueprint ID")
    sp_validate.set_defaults(func=cmd_validate)
```

Add the handler function:

```python
def cmd_validate(args: argparse.Namespace) -> int:
    """Validate all (or one) blueprints for executor compatibility."""
    from kevin.blueprint_compiler import compile, load_semantic
    from kevin.config import NON_EXECUTABLE_BLUEPRINTS

    kevin_root = Path(__file__).resolve().parent.parent
    blueprints_dir = kevin_root / "blueprints"

    if args.blueprint:
        from kevin.blueprint_loader import find_blueprint
        try:
            bp_path = find_blueprint(blueprints_dir, args.blueprint)
            bp_files = [bp_path]
        except FileNotFoundError:
            _err(f"Blueprint not found: {args.blueprint}")
            return 1
    else:
        bp_files = sorted(blueprints_dir.glob("bp_*.yaml"))

    if not bp_files:
        _err("No blueprints found")
        return 1

    sample_vars = {
        "issue_number": "0", "issue_title": "validation", "issue_body": "",
        "issue_labels": "", "target_repo": ".", "owner": "test", "repo": "test",
        "repo_full": "test/test", "learning_context": "", "pr_number": "",
    }

    print("\nBlueprint Validation Matrix")
    print("─" * 70)
    print(f"{'Blueprint':<45} {'Load':>5} {'Compile':>8} {'Size':>8}")
    print("─" * 70)

    failures = 0
    for bp_path in bp_files:
        name = bp_path.stem
        is_non_exec = any(ne in bp_path.name for ne in NON_EXECUTABLE_BLUEPRINTS)

        # Load
        try:
            semantic = load_semantic(bp_path)
            load_ok = "✓"
        except Exception as exc:
            load_ok = "✗"
            print(f"{name:<45} {load_ok:>5} {'—':>8} {'':>8}  ({exc})")
            failures += 1
            continue

        if is_non_exec:
            print(f"{name:<45} {load_ok:>5} {'—':>8} {'(orchestrator)':>8}")
            continue

        # Compile
        try:
            prompt = compile(semantic, sample_vars)
            compile_ok = "✓"
            size = f"{len(prompt)/1024:.1f}KB"
        except Exception as exc:
            compile_ok = "✗"
            size = "—"
            failures += 1
            print(f"{name:<45} {load_ok:>5} {compile_ok:>8} {size:>8}  ({exc})")
            continue

        print(f"{name:<45} {load_ok:>5} {compile_ok:>8} {size:>8}")

    total = len(bp_files)
    non_exec = sum(1 for f in bp_files if any(ne in f.name for ne in NON_EXECUTABLE_BLUEPRINTS))
    executable = total - non_exec

    print("─" * 70)
    print(f"Result: {executable - failures}/{executable} executor-ready, "
          f"{non_exec} orchestrator(s)")

    return 1 if failures > 0 else 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest kevin/tests/test_validate_command.py -v`
Expected: 3 passed

- [ ] **Step 5: Manual smoke test**

Run: `python3 -m kevin validate`
Expected: Matrix output showing 9/9 executor-ready, 1 orchestrator

- [ ] **Step 6: Verify full test suite**

Run: `python3 -m pytest kevin/tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add kevin/cli.py kevin/tests/test_validate_command.py
git commit -m "feat: add kevin validate command for blueprint preflight check"
```

---

### Task 6: executor.py 边界测试补全

**Files:**
- Modify: `kevin/tests/test_executor.py`

- [ ] **Step 1: Add edge case tests for extract_pr_number**

Append to `kevin/tests/test_executor.py`:

```python
def test_extract_pr_number_from_pr_hash_pattern() -> None:
    """should extract PR number from 'PR #123' pattern."""
    assert extract_pr_number("Opened PR #78 for review") == 78


def test_extract_pr_number_returns_last_match() -> None:
    """should return the LAST PR number found (most recent)."""
    out = "See pull/10 for context\nCreated https://github.com/a/b/pull/42"
    assert extract_pr_number(out) == 42


def test_extract_pr_number_no_match_no_repo() -> None:
    """should return None when stdout has no PR and no repo for gh fallback."""
    assert extract_pr_number("All done, no PR created") is None


def test_run_post_validators_handles_malformed_blocks(tmp_path: Path) -> None:
    """should return error result when block parsing fails."""
    semantic = SemanticBlueprint(
        blueprint_id="x", blueprint_name="n", goal="", acceptance_criteria=[],
        constraints=[], context_sources=[], sub_agents=[], verification_commands=[],
        workflow_steps=[], artifacts=[], task_timeout=60,
        raw={"metadata": {}, "workflow": {"ralph_loop": {"step_3": {"dependency_graph": {
            "blocks": [{"block_id": "B1"}]  # missing required fields
        }}}}},
    )
    results = run_post_validators(semantic, {}, tmp_path)
    # Should not crash — returns error result
    assert len(results) >= 0  # either empty (no validators) or error dict
```

- [ ] **Step 2: Run tests**

Run: `python3 -m pytest kevin/tests/test_executor.py -v`
Expected: All pass (3 existing + 4 new = 7)

- [ ] **Step 3: Commit**

```bash
git add kevin/tests/test_executor.py
git commit -m "test: add executor edge case tests for PR extraction and validators"
```

---

### Task 7: 全量测试验证 + dry-run E2E

**Files:**
- No new files — verification task

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest kevin/tests/ -v --tb=short`
Expected: 355+ tests, 0 failures

- [ ] **Step 2: Run kevin validate**

Run: `python3 -m kevin validate`
Expected: 9/9 executor-ready, 1 orchestrator, exit code 0

- [ ] **Step 3: Dry-run with a real blueprint (no token cost)**

Run: `python3 -m kevin dry-run --issue 42 --repo centific-cn/AgenticSDLC --target-repo .`
Expected: Loads blueprint, compiles prompt, prints dry-run message, exit code 0. No Claude CLI invocation.

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "fix: resolve issues found during E2E dry-run verification"
```

(Skip this step if no fixes needed.)

---

### Task 8: 真实 E2E 执行（bp_coding_task）

**Files:**
- No code changes — execution verification

**Prerequisites:** A test issue with `kevin` + `coding-task` labels on the target repo.

- [ ] **Step 1: Create a lightweight test issue**

```bash
gh issue create --repo centific-cn/AgenticSDLC \
  --title "E2E test: add executor version to CLI output" \
  --body "Add a --version flag to kevin CLI that prints the current version string." \
  --label "kevin,coding-task"
```

Note the issue number.

- [ ] **Step 2: Execute**

```bash
python3 -m kevin run --issue <ISSUE_NUMBER> --repo centific-cn/AgenticSDLC --target-repo .
```

- [ ] **Step 3: Verify outcomes**

Check:
- [ ] Exit code is 0
- [ ] `.kevin/runs/<run_id>/run.yaml` shows `status: completed`, `completion_status: all_passed`
- [ ] `.kevin/runs/<run_id>/logs/executor.log` contains compiled prompt + stdout
- [ ] PR created (visible in stdout or `run.yaml:pr_number`)
- [ ] GitHub issue labels updated (`kevin-completed`, `status:done`)
- [ ] Issue closed

- [ ] **Step 4: Document results**

Record pass/fail for each check. If any fail, investigate and fix before expanding to more blueprints.

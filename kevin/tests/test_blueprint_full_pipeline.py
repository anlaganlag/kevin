"""Full pipeline integration tests: every executor-compatible blueprint
goes through load → compile → validate → prompt checks (no token cost)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kevin.blueprint_compiler import compile, compile_task, load_semantic
from kevin.config import NON_EXECUTABLE_BLUEPRINTS

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent.parent / "blueprints"

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
    @pytest.mark.parametrize("bp_file", _EXECUTABLE_BP_FILES, ids=[p.stem for p in _EXECUTABLE_BP_FILES])
    def test_should_load_semantic_successfully(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        assert semantic.blueprint_id, f"{bp_file.name}: empty blueprint_id"
        assert semantic.blueprint_name, f"{bp_file.name}: empty blueprint_name"

    @pytest.mark.parametrize("bp_file", _EXECUTABLE_BP_FILES, ids=[p.stem for p in _EXECUTABLE_BP_FILES])
    def test_should_compile_prompt_within_size_bounds(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        prompt = compile(semantic, _SAMPLE_VARIABLES)
        size_kb = len(prompt) / 1024
        assert 0.5 < size_kb < 50, f"{bp_file.name}: prompt size {size_kb:.1f}KB outside [0.5, 50] range"

    @pytest.mark.parametrize("bp_file", _EXECUTABLE_BP_FILES, ids=[p.stem for p in _EXECUTABLE_BP_FILES])
    def test_should_compile_task_with_valid_structure(self, bp_file: Path, tmp_path: Path) -> None:
        semantic = load_semantic(bp_file)
        task = compile_task(semantic, _SAMPLE_VARIABLES, task_id="pipeline-test-001", cwd=tmp_path)
        assert task.task_id == "pipeline-test-001"
        assert len(task.instruction) > 100
        assert task.workspace.cwd == tmp_path
        assert task.permissions.git_write is True
        assert task.timeout >= 600

    @pytest.mark.parametrize("bp_file", _EXECUTABLE_BP_FILES, ids=[p.stem for p in _EXECUTABLE_BP_FILES])
    def test_should_contain_goal_section_in_prompt(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        prompt = compile(semantic, _SAMPLE_VARIABLES)
        assert "# GOAL" in prompt or "# TASK" in prompt, f"{bp_file.name}: prompt missing GOAL or TASK section"

    @pytest.mark.parametrize("bp_file", _EXECUTABLE_BP_FILES, ids=[p.stem for p in _EXECUTABLE_BP_FILES])
    def test_should_render_variables_in_prompt(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        prompt = compile(semantic, _SAMPLE_VARIABLES)
        assert "42" in prompt, f"{bp_file.name}: issue_number not rendered in prompt"


class TestNonExecutableBlueprintGuard:
    def test_planning_agent_excluded_from_executable_list(self) -> None:
        executable_names = {p.name for p in _EXECUTABLE_BP_FILES}
        assert "bp_planning_agent.1.0.0.yaml" not in executable_names

    def test_executable_count_is_nine(self) -> None:
        assert len(_EXECUTABLE_BP_FILES) == 9, (
            f"Expected 9 executable blueprints, found {len(_EXECUTABLE_BP_FILES)}: "
            f"{[p.stem for p in _EXECUTABLE_BP_FILES]}"
        )

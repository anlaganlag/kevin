"""Tests for kevin.blueprint_compiler — semantic extraction and prompt compilation."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from kevin.blueprint_compiler import (
    SemanticBlueprint,
    compile,
    compile_task,
    load_semantic,
)
from kevin.workers.interface import WorkerTask

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent.parent / "blueprints"

# Collect all real blueprint YAML files for parametrized tests
_ALL_BP_FILES = sorted(BLUEPRINTS_DIR.glob("*.yaml")) if BLUEPRINTS_DIR.exists() else []


class TestLoadSemantic:
    """Test semantic extraction from real Blueprint YAML files."""

    def test_should_extract_coding_task_blueprint(self) -> None:
        bp_path = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"
        if not bp_path.exists():
            pytest.skip("Blueprint file not found")

        semantic = load_semantic(bp_path)

        assert semantic.blueprint_id == "bp_coding_task.1.0.0"
        assert "Coding Task" in semantic.blueprint_name
        assert len(semantic.acceptance_criteria) > 0
        assert len(semantic.workflow_steps) == 3  # B1, B2, B3
        assert len(semantic.verification_commands) > 0
        assert semantic.task_timeout > 0

    def test_should_extract_backend_tdd_blueprint(self) -> None:
        bp_path = BLUEPRINTS_DIR / "bp_backend_coding_tdd_automation.1.0.0.yaml"
        if not bp_path.exists():
            pytest.skip("Blueprint file not found")

        semantic = load_semantic(bp_path)

        assert semantic.blueprint_id == "bp_backend_coding_tdd_automation.1.0.0"
        assert len(semantic.constraints) > 5  # Has inline rules + constraints
        assert len(semantic.sub_agents) > 0
        assert len(semantic.acceptance_criteria) > 10

    def test_should_extract_goal_from_metadata_and_execution(self) -> None:
        bp_path = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"
        if not bp_path.exists():
            pytest.skip("Blueprint file not found")

        semantic = load_semantic(bp_path)

        assert "Analyze issue requirements" in semantic.goal
        assert "Implement solution" in semantic.goal

    def test_should_deduplicate_acceptance_criteria(self) -> None:
        bp_path = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"
        if not bp_path.exists():
            pytest.skip("Blueprint file not found")

        semantic = load_semantic(bp_path)

        # No exact duplicates
        assert len(semantic.acceptance_criteria) == len(set(semantic.acceptance_criteria))

    def test_should_extract_verification_commands(self) -> None:
        bp_path = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"
        if not bp_path.exists():
            pytest.skip("Blueprint file not found")

        semantic = load_semantic(bp_path)

        types_found = set()
        for cmd in semantic.verification_commands:
            if "git" in cmd.lower():
                types_found.add("git")
            if "file" in cmd.lower() or "exists" in cmd.lower():
                types_found.add("file")
            if cmd.startswith("Run:"):
                types_found.add("command")

        assert "git" in types_found
        assert "file" in types_found

    def test_should_extract_artifacts(self) -> None:
        bp_path = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"
        if not bp_path.exists():
            pytest.skip("Blueprint file not found")

        semantic = load_semantic(bp_path)

        assert len(semantic.artifacts) > 0
        artifact_text = " ".join(semantic.artifacts).lower()
        assert "implementation" in artifact_text or "source" in artifact_text


class TestCompile:
    """Test prompt compilation from SemanticBlueprint."""

    def test_should_produce_prompt_with_all_sections(self) -> None:
        semantic = SemanticBlueprint(
            blueprint_id="test.1.0.0",
            blueprint_name="Test Blueprint",
            goal="Build a widget",
            acceptance_criteria=["Widget works", "Tests pass"],
            constraints=["No external deps"],
            context_sources=["GitHub Issue"],
            sub_agents=[{"agent_type": "QA", "role": "Tester", "responsibilities": ["Test"]}],
            verification_commands=["Run: pytest"],
            workflow_steps=["Analyze", "Implement", "Test"],
            artifacts=["widget.py"],
            task_timeout=600,
            raw={},
        )
        variables = {
            "issue_number": "1",
            "issue_title": "Build widget",
            "issue_body": "Build a nice widget",
        }

        prompt = compile(semantic, variables)

        assert "GOAL" in prompt
        assert "Build a widget" in prompt
        assert "TASK" in prompt
        assert "Issue #1" in prompt
        assert "ACCEPTANCE CRITERIA" in prompt
        assert "Widget works" in prompt
        assert "CONSTRAINTS" in prompt
        assert "No external deps" in prompt
        assert "WORKFLOW GUIDANCE" in prompt
        assert "VERIFICATION" in prompt
        assert "SUB-AGENTS" in prompt
        assert "EXPECTED ARTIFACTS" in prompt

    def test_should_render_variables_in_prompt(self) -> None:
        semantic = SemanticBlueprint(
            blueprint_id="test",
            blueprint_name="Test",
            goal="Fix issue {{issue_number}}",
            acceptance_criteria=["Done"],
            constraints=[],
            context_sources=[],
            sub_agents=[],
            verification_commands=[],
            workflow_steps=[],
            artifacts=[],
            task_timeout=300,
            raw={},
        )
        variables = {"issue_number": "42", "issue_title": "Fix bug", "issue_body": "details"}

        prompt = compile(semantic, variables)

        assert "Fix issue 42" in prompt
        assert "{{issue_number}}" not in prompt

    def test_should_include_learning_context_when_present(self) -> None:
        semantic = SemanticBlueprint(
            blueprint_id="test",
            blueprint_name="Test",
            goal="Do thing",
            acceptance_criteria=["Done"],
            constraints=[],
            context_sources=[],
            sub_agents=[],
            verification_commands=[],
            workflow_steps=[],
            artifacts=[],
            task_timeout=300,
            raw={},
        )
        variables = {
            "issue_number": "1",
            "issue_title": "X",
            "issue_body": "Y",
            "learning_context": "[History] 80% success rate (5 runs)",
        }

        prompt = compile(semantic, variables)

        assert "HISTORICAL CONTEXT" in prompt
        assert "80% success rate" in prompt

    def test_should_omit_empty_sections(self) -> None:
        semantic = SemanticBlueprint(
            blueprint_id="test",
            blueprint_name="Test",
            goal="Do thing",
            acceptance_criteria=["Done"],
            constraints=[],
            context_sources=[],
            sub_agents=[],
            verification_commands=[],
            workflow_steps=[],
            artifacts=[],
            task_timeout=300,
            raw={},
        )
        variables = {"issue_number": "1", "issue_title": "X", "issue_body": "Y"}

        prompt = compile(semantic, variables)

        assert "CONSTRAINTS" not in prompt
        assert "SUB-AGENTS" not in prompt
        assert "VERIFICATION" not in prompt
        assert "WORKFLOW GUIDANCE" not in prompt
        assert "EXPECTED ARTIFACTS" not in prompt

    def test_should_produce_reasonable_size_for_real_blueprint(self) -> None:
        bp_path = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"
        if not bp_path.exists():
            pytest.skip("Blueprint file not found")

        semantic = load_semantic(bp_path)
        variables = {
            "issue_number": "42",
            "issue_title": "Add endpoint",
            "issue_body": "Add /health endpoint",
            "learning_context": "",
        }
        prompt = compile(semantic, variables)

        # Should be 1-5KB, not 30-50KB like the raw YAML
        assert len(prompt) < 6000
        assert len(prompt) > 500


# ---------------------------------------------------------------------------
# Edge-case tests for load_semantic
# ---------------------------------------------------------------------------


class TestLoadSemanticEdgeCases:
    """Test semantic extraction with missing, empty, and unusual YAML structures."""

    def test_should_handle_blueprint_with_no_blocks(self, tmp_path: Path) -> None:
        """YAML has no workflow.ralph_loop.step_3 section."""
        bp_file = tmp_path / "bp_no_blocks.yaml"
        bp_file.write_text(yaml.dump({
            "blueprint": {
                "metadata": {"blueprint_id": "no_blocks", "blueprint_name": "No Blocks"},
                "execution": {},
                "completion": {},
            }
        }))

        semantic = load_semantic(bp_file)

        assert semantic.blueprint_id == "no_blocks"
        assert semantic.workflow_steps == []
        assert semantic.verification_commands == []
        assert semantic.acceptance_criteria == []

    def test_should_handle_blueprint_with_no_completion(self, tmp_path: Path) -> None:
        """Missing completion section should yield empty artifacts and criteria."""
        bp_file = tmp_path / "bp_no_completion.yaml"
        bp_file.write_text(yaml.dump({
            "blueprint": {
                "metadata": {"blueprint_id": "nc", "blueprint_name": "No Completion"},
                "execution": {},
            }
        }))

        semantic = load_semantic(bp_file)

        assert semantic.artifacts == []
        assert semantic.acceptance_criteria == []

    def test_should_handle_blueprint_with_no_configuration(self, tmp_path: Path) -> None:
        """Missing configuration section should yield empty constraints."""
        bp_file = tmp_path / "bp_no_config.yaml"
        bp_file.write_text(yaml.dump({
            "blueprint": {
                "metadata": {"blueprint_id": "nc", "blueprint_name": "No Config"},
                "execution": {},
                "completion": {},
            }
        }))

        semantic = load_semantic(bp_file)

        assert semantic.constraints == []

    def test_should_handle_blueprint_with_empty_blocks(self, tmp_path: Path) -> None:
        """blocks: [] should produce empty workflow steps and criteria."""
        bp_file = tmp_path / "bp_empty_blocks.yaml"
        bp_file.write_text(yaml.dump({
            "blueprint": {
                "metadata": {"blueprint_id": "eb", "blueprint_name": "Empty Blocks"},
                "workflow": {"ralph_loop": {"step_3": {"dependency_graph": {"blocks": []}}}},
                "execution": {},
                "completion": {},
            }
        }))

        semantic = load_semantic(bp_file)

        assert semantic.workflow_steps == []
        assert semantic.verification_commands == []
        assert semantic.acceptance_criteria == []
        assert semantic.task_timeout == 600  # minimum

    def test_should_handle_inline_rules_as_list(self, tmp_path: Path) -> None:
        """inline can be a list of rules (planning_agent format) instead of a dict."""
        rules_list = [
            {"name": "rule_a", "rule": "Do A always"},
            {"name": "rule_b", "rule": "Never do B"},
        ]
        bp_file = tmp_path / "bp_list_rules.yaml"
        bp_file.write_text(yaml.dump({
            "blueprint": {
                "metadata": {"blueprint_id": "lr", "blueprint_name": "List Rules"},
                "configuration": {"rules": {"inline": rules_list}},
                "execution": {},
                "completion": {},
            }
        }))

        semantic = load_semantic(bp_file)

        assert len(semantic.constraints) >= 2
        assert any("Do A always" in c for c in semantic.constraints)
        assert any("Never do B" in c for c in semantic.constraints)

    @pytest.mark.parametrize(
        "bp_file",
        _ALL_BP_FILES,
        ids=[p.name for p in _ALL_BP_FILES],
    )
    def test_should_handle_all_real_blueprints(self, bp_file: Path) -> None:
        """Every real blueprint YAML should load without error."""
        semantic = load_semantic(bp_file)

        # Some YAMLs (e.g. state machine) may lack standard metadata
        assert isinstance(semantic.blueprint_id, str)
        assert isinstance(semantic.blueprint_name, str)
        assert isinstance(semantic.acceptance_criteria, list)
        assert isinstance(semantic.constraints, list)
        assert isinstance(semantic.workflow_steps, list)
        assert isinstance(semantic.task_timeout, int)

    def test_should_handle_nested_constraints(self, tmp_path: Path) -> None:
        """Deeply nested inline constraints should be flattened."""
        bp_file = tmp_path / "bp_nested.yaml"
        bp_file.write_text(yaml.dump({
            "blueprint": {
                "metadata": {"blueprint_id": "nested", "blueprint_name": "Nested"},
                "configuration": {
                    "constraints": {
                        "inline": {
                            "level1": {
                                "level2": {
                                    "level3": "deep value"
                                }
                            },
                            "flat": "shallow value",
                        }
                    }
                },
                "execution": {},
                "completion": {},
            }
        }))

        semantic = load_semantic(bp_file)

        # Both the deeply nested and flat values should appear
        assert any("deep value" in c for c in semantic.constraints)
        assert any("shallow value" in c for c in semantic.constraints)


# ---------------------------------------------------------------------------
# Edge-case tests for compile
# ---------------------------------------------------------------------------


class TestCompileEdgeCases:
    """Test prompt compilation with unusual inputs."""

    @staticmethod
    def _minimal_semantic(**overrides: Any) -> SemanticBlueprint:
        defaults = {
            "blueprint_id": "test",
            "blueprint_name": "Test",
            "goal": "Do thing",
            "acceptance_criteria": ["Done"],
            "constraints": [],
            "context_sources": [],
            "sub_agents": [],
            "verification_commands": [],
            "workflow_steps": [],
            "artifacts": [],
            "task_timeout": 300,
            "raw": {},
        }
        defaults.update(overrides)
        return SemanticBlueprint(**defaults)

    def test_should_handle_missing_variables_gracefully(self) -> None:
        """Unknown {{var}} placeholders should be left as-is, not crash."""
        semantic = self._minimal_semantic(goal="Fix {{unknown_var}} issue")
        variables = {"issue_number": "1", "issue_title": "X", "issue_body": "Y"}

        prompt = compile(semantic, variables)

        assert "{{unknown_var}}" in prompt

    def test_should_handle_very_long_issue_body(self) -> None:
        """50KB issue body should not crash or be truncated in the prompt."""
        long_body = "A" * 50_000
        semantic = self._minimal_semantic()
        variables = {
            "issue_number": "99",
            "issue_title": "Big Issue",
            "issue_body": long_body,
        }

        prompt = compile(semantic, variables)

        assert long_body in prompt

    def test_should_handle_special_characters_in_variables(self) -> None:
        """Newlines, quotes, and braces in variable values should not break rendering."""
        body_with_specials = 'Line1\nLine2\n"quoted"\n{braces}\n{{double}}'
        semantic = self._minimal_semantic()
        variables = {
            "issue_number": "1",
            "issue_title": "Special's \"chars\"",
            "issue_body": body_with_specials,
        }

        prompt = compile(semantic, variables)

        assert "Line1" in prompt
        assert '"quoted"' in prompt
        assert "{braces}" in prompt

    def test_should_handle_empty_acceptance_criteria(self) -> None:
        """Empty acceptance_criteria list should omit the section entirely."""
        semantic = self._minimal_semantic(acceptance_criteria=[])
        variables = {"issue_number": "1", "issue_title": "X", "issue_body": "Y"}

        prompt = compile(semantic, variables)

        assert "ACCEPTANCE CRITERIA" not in prompt

    @pytest.mark.parametrize(
        "bp_file",
        _ALL_BP_FILES,
        ids=[p.name for p in _ALL_BP_FILES],
    )
    def test_should_produce_valid_prompt_for_all_real_blueprints(
        self, bp_file: Path
    ) -> None:
        """Every real blueprint should compile into a prompt with GOAL section."""
        semantic = load_semantic(bp_file)
        variables = {
            "issue_number": "1",
            "issue_title": "Test",
            "issue_body": "Test body",
        }

        prompt = compile(semantic, variables)

        assert "GOAL" in prompt
        assert len(prompt) > 100


# ---------------------------------------------------------------------------
# compile_task tests
# ---------------------------------------------------------------------------


class TestCompileTask:
    """Test compile_task() produces a valid WorkerTask."""

    def test_should_return_worker_task(self) -> None:
        bp_path = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"
        if not bp_path.exists():
            pytest.skip("Blueprint file not found")
        semantic = load_semantic(bp_path)
        variables = {
            "issue_number": "42",
            "issue_title": "Add endpoint",
            "issue_body": "Add /health",
            "target_repo": "/tmp/test",
            "owner": "test",
            "repo": "test",
            "repo_full": "test/test",
            "learning_context": "",
        }
        task = compile_task(
            semantic, variables, task_id="run-001", cwd=Path("/tmp/test")
        )
        assert isinstance(task, WorkerTask)
        assert task.task_id == "run-001"
        assert task.timeout == semantic.task_timeout
        assert len(task.instruction) > 100
        assert "ACCEPTANCE CRITERIA" in task.instruction
        assert task.workspace.cwd == Path("/tmp/test")
        assert task.permissions.git_write is True
        assert task.permissions.git_push is True

    def test_should_embed_metadata(self) -> None:
        bp_path = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"
        if not bp_path.exists():
            pytest.skip("Blueprint file not found")
        semantic = load_semantic(bp_path)
        variables = {"issue_number": "42", "issue_title": "X", "issue_body": "Y"}
        task = compile_task(semantic, variables, task_id="t1", cwd=Path("/tmp"))
        assert task.metadata["blueprint_id"] == "bp_coding_task.1.0.0"
        assert task.metadata["issue_number"] == "42"

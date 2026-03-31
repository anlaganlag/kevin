"""Robust tests for blueprint integrity and executor compatibility.

Validates that all blueprints:
1. Load without error
2. Compile to valid prompts
3. Pass execution validation
4. Have no hardcoded language-specific test commands in validators
5. Use claude-code runner for test execution blocks (not shell)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from kevin.blueprint_compiler import (
    SemanticBlueprint,
    compile,
    compile_task,
    load_semantic,
    validate_for_execution,
)
from kevin.config import NON_EXECUTABLE_BLUEPRINTS

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent.parent / "blueprints"
_ALL_BP_FILES = sorted(BLUEPRINTS_DIR.glob("bp_*.yaml")) if BLUEPRINTS_DIR.exists() else []

# Known non-executable / non-standard files to skip for execution tests
_SKIP_EXECUTION = {f"{bp_id}.yaml" for bp_id in NON_EXECUTABLE_BLUEPRINTS}
_EXECUTABLE_BP_FILES = [p for p in _ALL_BP_FILES if p.name not in _SKIP_EXECUTION]

# Hardcoded language-specific commands that should NOT appear in validators
_HARDCODED_TEST_COMMANDS = [
    "go test",
    "npm test",
    "npx jest",
    "npx playwright",
    "npx vitest",
    "npx cypress",
    "semgrep ",
    "k6 run",
    "k6 cloud",
]

_STANDARD_VARIABLES = {
    "issue_number": "99",
    "issue_title": "Robust test issue",
    "issue_body": "Validate all blueprints compile correctly.",
    "issue_labels": "kevin, testing",
    "target_repo": "/tmp/test-repo",
    "owner": "test-org",
    "repo": "test-repo",
    "repo_full": "test-org/test-repo",
    "pr_number": "42",
    "learning_context": "",
}


# ============================================================
# 1. Blueprint Loading Integrity
# ============================================================


class TestBlueprintLoadingIntegrity:
    """Every blueprint YAML must load into a valid SemanticBlueprint."""

    @pytest.mark.parametrize(
        "bp_file", _ALL_BP_FILES, ids=[p.name for p in _ALL_BP_FILES]
    )
    def test_should_load_without_error(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        assert isinstance(semantic.blueprint_id, str)
        assert len(semantic.blueprint_id) > 0
        assert isinstance(semantic.blueprint_name, str)

    @pytest.mark.parametrize(
        "bp_file", _ALL_BP_FILES, ids=[p.name for p in _ALL_BP_FILES]
    )
    def test_should_have_valid_yaml_structure(self, bp_file: Path) -> None:
        with open(bp_file) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), f"{bp_file.name}: not a valid YAML dict"
        assert "blueprint" in data, f"{bp_file.name}: missing top-level 'blueprint' key"

    @pytest.mark.parametrize(
        "bp_file", _ALL_BP_FILES, ids=[p.name for p in _ALL_BP_FILES]
    )
    def test_should_have_metadata_with_id_and_name(self, bp_file: Path) -> None:
        with open(bp_file) as f:
            data = yaml.safe_load(f)
        meta = data.get("blueprint", {}).get("metadata", {})
        assert "blueprint_id" in meta, f"{bp_file.name}: missing metadata.blueprint_id"
        assert "blueprint_name" in meta, f"{bp_file.name}: missing metadata.blueprint_name"


# ============================================================
# 2. Compile Pipeline (load → compile → validate)
# ============================================================


class TestCompilePipeline:
    """Every executable blueprint must pass the full compile pipeline."""

    @pytest.mark.parametrize(
        "bp_file", _EXECUTABLE_BP_FILES, ids=[p.name for p in _EXECUTABLE_BP_FILES]
    )
    def test_should_compile_to_prompt_with_goal(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        prompt = compile(semantic, _STANDARD_VARIABLES)
        assert "GOAL" in prompt, f"{bp_file.name}: compiled prompt missing GOAL"
        assert len(prompt) > 200, f"{bp_file.name}: prompt too short ({len(prompt)} chars)"

    @pytest.mark.parametrize(
        "bp_file", _EXECUTABLE_BP_FILES, ids=[p.name for p in _EXECUTABLE_BP_FILES]
    )
    def test_should_produce_valid_worker_task(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        task = compile_task(
            semantic, _STANDARD_VARIABLES, task_id="robustness-test", cwd=Path("/tmp/test")
        )
        assert task.task_id == "robustness-test"
        assert task.timeout > 0
        assert len(task.instruction) > 200

    @pytest.mark.parametrize(
        "bp_file", _EXECUTABLE_BP_FILES, ids=[p.name for p in _EXECUTABLE_BP_FILES]
    )
    def test_should_pass_execution_validation(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        validation = validate_for_execution(semantic)
        assert validation.valid is True, (
            f"{bp_file.name}: validation failed — {validation.warnings}"
        )

    @pytest.mark.parametrize(
        "bp_file", _EXECUTABLE_BP_FILES, ids=[p.name for p in _EXECUTABLE_BP_FILES]
    )
    def test_should_have_acceptance_criteria(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        assert len(semantic.acceptance_criteria) > 0, (
            f"{bp_file.name}: no acceptance criteria found"
        )

    @pytest.mark.parametrize(
        "bp_file", _EXECUTABLE_BP_FILES, ids=[p.name for p in _EXECUTABLE_BP_FILES]
    )
    def test_prompt_should_not_exceed_size_limit(self, bp_file: Path) -> None:
        """Compiled prompts should stay under 10KB to avoid token waste."""
        semantic = load_semantic(bp_file)
        prompt = compile(semantic, _STANDARD_VARIABLES)
        assert len(prompt) < 10_000, (
            f"{bp_file.name}: prompt too large ({len(prompt)} chars), "
            f"may waste executor tokens"
        )


# ============================================================
# 3. No Hardcoded Language-Specific Test Commands
# ============================================================


class TestNoHardcodedTestCommands:
    """Validators and shell runners must not contain hardcoded language-specific test commands.

    Test execution blocks should use claude-code runner with auto-detection,
    not hardcoded shell commands that assume a specific language/framework.
    """

    @staticmethod
    def _extract_matching(data: dict[str, Any], predicate: Any) -> list[dict[str, Any]]:
        """Recursively find all dicts matching a predicate."""
        found: list[dict[str, Any]] = []

        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                if predicate(obj):
                    found.append(obj)
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)
        return found

    @pytest.mark.parametrize(
        "bp_file", _ALL_BP_FILES, ids=[p.name for p in _ALL_BP_FILES]
    )
    def test_validators_should_not_have_hardcoded_test_commands(
        self, bp_file: Path
    ) -> None:
        with open(bp_file) as f:
            data = yaml.safe_load(f)

        validators = self._extract_matching(
                data, lambda d: d.get("type") == "command" and "command" in d
            )
        for v in validators:
            cmd = v["command"].strip().lower()
            for forbidden in _HARDCODED_TEST_COMMANDS:
                assert forbidden not in cmd, (
                    f"{bp_file.name}: validator has hardcoded '{forbidden}' "
                    f"in command: {v['command'][:80]}"
                )

    @pytest.mark.parametrize(
        "bp_file",
        [p for p in _ALL_BP_FILES if "test_" in p.name],
        ids=[p.name for p in _ALL_BP_FILES if "test_" in p.name],
    )
    def test_test_blueprints_should_use_claude_code_for_execution(
        self, bp_file: Path
    ) -> None:
        """Test execution blocks (run tests, execute tests) should use claude-code runner."""
        with open(bp_file) as f:
            data = yaml.safe_load(f)

        shell_runners = self._extract_matching(
                data, lambda d: d.get("runner") == "shell" and "runner_config" in d
            )
        for block in shell_runners:
            cmd = block.get("runner_config", {}).get("command", "").lower()
            name = block.get("name", block.get("block_id", "unknown"))
            # Shell runners in test blueprints should not run test frameworks
            for forbidden in _HARDCODED_TEST_COMMANDS:
                assert forbidden not in cmd, (
                    f"{bp_file.name} block '{name}': shell runner has hardcoded "
                    f"'{forbidden}' — should use claude-code runner with auto-detection"
                )


# ============================================================
# 4. NON_EXECUTABLE Guard
# ============================================================


class TestNonExecutableGuard:
    """Non-executable blueprints must be properly guarded."""

    def test_should_have_planning_agent_in_non_executable_set(self) -> None:
        assert "bp_planning_agent.1.0.0" in NON_EXECUTABLE_BLUEPRINTS

    @pytest.mark.parametrize(
        "bp_id", sorted(NON_EXECUTABLE_BLUEPRINTS), ids=sorted(NON_EXECUTABLE_BLUEPRINTS)
    )
    def test_non_executable_should_fail_validation(self, bp_id: str) -> None:
        bp_path = BLUEPRINTS_DIR / f"{bp_id}.yaml"
        if not bp_path.exists():
            pytest.skip(f"{bp_id}.yaml not found")
        semantic = load_semantic(bp_path)
        validation = validate_for_execution(semantic)
        assert validation.valid is False, (
            f"{bp_id} is in NON_EXECUTABLE_BLUEPRINTS but passed validation"
        )


# ============================================================
# 5. Blueprint ID Consistency
# ============================================================


class TestBlueprintIdConsistency:
    """Blueprint ID in YAML must match the filename."""

    @pytest.mark.parametrize(
        "bp_file", _ALL_BP_FILES, ids=[p.name for p in _ALL_BP_FILES]
    )
    def test_should_match_filename(self, bp_file: Path) -> None:
        with open(bp_file) as f:
            data = yaml.safe_load(f)
        bp_id = data.get("blueprint", {}).get("metadata", {}).get("blueprint_id", "")
        expected_id = bp_file.stem  # e.g. "bp_coding_task.1.0.0"
        assert bp_id == expected_id, (
            f"{bp_file.name}: metadata.blueprint_id='{bp_id}' "
            f"does not match filename '{expected_id}'"
        )


# ============================================================
# 6. Edge Function Blueprint Sync
# ============================================================


class TestEdgeFunctionBlueprintSync:
    """The TypeScript blueprint list in _shared/blueprints.ts must match config.py."""

    SYNC_SCRIPT = (
        Path(__file__).resolve().parent.parent.parent / "scripts" / "sync_blueprints_ts.py"
    )

    def test_should_match_config_intent_map(self) -> None:
        if not self.SYNC_SCRIPT.exists():
            pytest.skip("sync_blueprints_ts.py not found")

        import subprocess

        result = subprocess.run(
            ["python3", str(self.SYNC_SCRIPT), "--check"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"blueprints.ts out of sync with config.py — "
            f"run: python scripts/sync_blueprints_ts.py\n{result.stdout}"
        )


# ============================================================
# 7. Variable Substitution Robustness
# ============================================================


class TestVariableSubstitution:
    """Compiled prompts should handle variable edge cases gracefully."""

    @pytest.mark.parametrize(
        "bp_file", _EXECUTABLE_BP_FILES[:3], ids=[p.name for p in _EXECUTABLE_BP_FILES[:3]]
    )
    def test_should_substitute_all_standard_variables(self, bp_file: Path) -> None:
        semantic = load_semantic(bp_file)
        prompt = compile(semantic, _STANDARD_VARIABLES)
        # Standard variables should be resolved
        assert "{{issue_number}}" not in prompt or "issue_number" not in str(semantic.goal)

    def test_should_handle_empty_issue_body(self) -> None:
        bp_file = _EXECUTABLE_BP_FILES[0] if _EXECUTABLE_BP_FILES else None
        if not bp_file:
            pytest.skip("No executable blueprints found")
        semantic = load_semantic(bp_file)
        variables = {**_STANDARD_VARIABLES, "issue_body": ""}
        prompt = compile(semantic, variables)
        assert "GOAL" in prompt

    def test_should_handle_unicode_in_variables(self) -> None:
        bp_file = _EXECUTABLE_BP_FILES[0] if _EXECUTABLE_BP_FILES else None
        if not bp_file:
            pytest.skip("No executable blueprints found")
        semantic = load_semantic(bp_file)
        variables = {
            **_STANDARD_VARIABLES,
            "issue_title": "修复中文标题的 bug 🐛",
            "issue_body": "详细描述：需要支持多语言",
        }
        prompt = compile(semantic, variables)
        assert "修复中文标题" in prompt

    def test_should_handle_special_chars_without_injection(self) -> None:
        bp_file = _EXECUTABLE_BP_FILES[0] if _EXECUTABLE_BP_FILES else None
        if not bp_file:
            pytest.skip("No executable blueprints found")
        semantic = load_semantic(bp_file)
        variables = {
            **_STANDARD_VARIABLES,
            "issue_body": '"; DROP TABLE users; --\n<script>alert(1)</script>',
        }
        prompt = compile(semantic, variables)
        # Should include the text as-is (prompt, not HTML/SQL)
        assert "DROP TABLE" in prompt

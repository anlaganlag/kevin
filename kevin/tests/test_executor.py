"""Tests for kevin.executor — agentic execution and PR extraction."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from kevin.blueprint_compiler import SemanticBlueprint
from kevin.executor import ExecutorResult, execute, extract_pr_number, run_post_validators


class TestExecute:
    def test_should_return_dry_run_result(self, tmp_path) -> None:
        result = execute(
            "test prompt",
            cwd=tmp_path,
            timeout=10,
            dry_run=True,
        )
        assert result.success is True
        assert "dry-run" in result.stdout
        assert result.prompt == "test prompt"

    def test_should_preserve_prompt_in_result(self, tmp_path) -> None:
        result = execute(
            "my prompt content",
            cwd=tmp_path,
            timeout=10,
            dry_run=True,
        )
        assert result.prompt == "my prompt content"


class TestExtractPrNumber:
    def test_should_extract_from_github_url(self) -> None:
        stdout = "Created PR: https://github.com/owner/repo/pull/42\nDone."
        assert extract_pr_number(stdout) == 42

    def test_should_extract_from_pr_hash_pattern(self) -> None:
        stdout = "Opened PR #123 for review."
        assert extract_pr_number(stdout) == 123

    def test_should_extract_from_pull_request_pattern(self) -> None:
        stdout = "Created pull request #55"
        assert extract_pr_number(stdout) == 55

    def test_should_return_none_when_no_pr(self) -> None:
        stdout = "No PR created."
        assert extract_pr_number(stdout) is None

    def test_should_prefer_github_url_over_hash(self) -> None:
        stdout = "PR #99 at https://github.com/owner/repo/pull/42"
        # GitHub URL takes priority
        assert extract_pr_number(stdout) == 42

    def test_should_fallback_to_gh_cli(self) -> None:
        with patch("kevin.executor._find_pr_via_gh", return_value=7) as mock_gh:
            result = extract_pr_number("no pr here", repo="owner/repo", issue_number=5)
            assert result == 7
            mock_gh.assert_called_once_with("owner/repo", 5)

    def test_should_return_none_when_no_repo_for_fallback(self) -> None:
        result = extract_pr_number("no pr here")
        assert result is None


# ---------------------------------------------------------------------------
# Edge-case tests for execute()
# ---------------------------------------------------------------------------


class TestExecuteEdgeCases:
    """Test execute() with unusual inputs and context_filter behavior."""

    def test_should_handle_empty_prompt(self, tmp_path: Path) -> None:
        """Empty prompt string should still produce a valid dry-run result."""
        result = execute("", cwd=tmp_path, timeout=10, dry_run=True)

        assert result.success is True
        assert result.prompt == ""
        assert "0 chars" in result.stdout

    def test_should_handle_context_filter_creates_claudeignore(self, tmp_path: Path) -> None:
        """context_filter should create a .claudeignore and clean it up after."""
        # We mock run_with_heartbeat so no real subprocess is spawned
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.exit_code = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""

        claudeignore = tmp_path / ".claudeignore"
        assert not claudeignore.exists()

        with patch("kevin.executor.run_with_heartbeat", return_value=mock_result):
            result = execute(
                "test prompt",
                cwd=tmp_path,
                timeout=10,
                context_filter=["node_modules/", "*.log"],
            )

        assert result.success is True
        # .claudeignore should be cleaned up after execution
        assert not claudeignore.exists()

    def test_should_not_overwrite_existing_claudeignore(self, tmp_path: Path) -> None:
        """Pre-existing .claudeignore should NOT be touched."""
        claudeignore = tmp_path / ".claudeignore"
        original_content = "# user's own ignore\nbuild/\n"
        claudeignore.write_text(original_content)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.exit_code = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""

        with patch("kevin.executor.run_with_heartbeat", return_value=mock_result):
            execute(
                "test prompt",
                cwd=tmp_path,
                timeout=10,
                context_filter=["node_modules/"],
            )

        # Original content should be preserved
        assert claudeignore.read_text() == original_content

    def test_should_record_duration(self, tmp_path: Path) -> None:
        """Non-dry-run execution should have a positive duration_seconds."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.exit_code = 0
        mock_result.stdout = "done"
        mock_result.stderr = ""

        with patch("kevin.executor.run_with_heartbeat", return_value=mock_result):
            result = execute("test prompt", cwd=tmp_path, timeout=10)

        assert result.duration_seconds > 0


# ---------------------------------------------------------------------------
# Edge-case tests for run_post_validators()
# ---------------------------------------------------------------------------


def _make_semantic_with_validators(
    validators: list[list[dict[str, Any]]],
) -> SemanticBlueprint:
    """Helper: build a SemanticBlueprint with blocks containing given validators."""
    blocks = []
    for i, block_validators in enumerate(validators):
        blocks.append({
            "block_id": f"B{i}",
            "name": f"Block {i}",
            "validators": block_validators,
        })
    return SemanticBlueprint(
        blueprint_id="test",
        blueprint_name="Test",
        goal="test",
        acceptance_criteria=[],
        constraints=[],
        context_sources=[],
        sub_agents=[],
        verification_commands=[],
        workflow_steps=[],
        artifacts=[],
        task_timeout=300,
        raw={
            "workflow": {
                "ralph_loop": {
                    "step_3": {
                        "dependency_graph": {"blocks": blocks}
                    }
                }
            }
        },
    )


class TestRunPostValidators:
    """Test post-validator execution edge cases."""

    def test_should_run_validators_from_semantic_blueprint(self, tmp_path: Path) -> None:
        """Validators defined in blocks should be dispatched via VALIDATORS registry."""
        semantic = _make_semantic_with_validators([
            [{"type": "git_diff_check"}],
        ])
        variables = {"issue_number": "1", "issue_title": "X", "issue_body": "Y"}

        fake_result = {"type": "git_diff_check", "passed": True}
        with patch("kevin.agent_runner.VALIDATORS", {"git_diff_check": lambda v, vars, cwd: fake_result}):
            results = run_post_validators(semantic, variables, tmp_path)

        assert len(results) == 1
        assert results[0]["passed"] is True

    def test_should_handle_blueprint_with_no_validators(self, tmp_path: Path) -> None:
        """Blueprint with no validators should return empty results list."""
        semantic = _make_semantic_with_validators([[]])
        variables = {"issue_number": "1", "issue_title": "X", "issue_body": "Y"}

        results = run_post_validators(semantic, variables, tmp_path)

        assert results == []

    def test_should_deduplicate_validators(self, tmp_path: Path) -> None:
        """Same validator appearing in multiple blocks should run only once."""
        same_validator = {"type": "git_diff_check"}
        semantic = _make_semantic_with_validators([
            [same_validator],
            [same_validator],
        ])
        variables = {"issue_number": "1", "issue_title": "X", "issue_body": "Y"}

        call_count = 0

        def counting_validator(v, vars, cwd):
            nonlocal call_count
            call_count += 1
            return {"type": "git_diff_check", "passed": True}

        with patch("kevin.agent_runner.VALIDATORS", {"git_diff_check": counting_validator}):
            results = run_post_validators(semantic, variables, tmp_path)

        assert call_count == 1
        assert len(results) == 1

    def test_should_handle_unknown_validator_type(self, tmp_path: Path) -> None:
        """Unknown validator type should produce a failure result, not crash."""
        semantic = _make_semantic_with_validators([
            [{"type": "nonexistent_check"}],
        ])
        variables = {"issue_number": "1", "issue_title": "X", "issue_body": "Y"}

        results = run_post_validators(semantic, variables, tmp_path)

        assert len(results) == 1
        assert results[0]["passed"] is False
        assert "Unknown validator" in results[0]["error"]


# ---------------------------------------------------------------------------
# Edge-case tests for extract_pr_number()
# ---------------------------------------------------------------------------


class TestExtractPrNumberEdgeCases:
    """Additional edge cases for PR number extraction."""

    def test_should_handle_multiple_pr_urls_returns_first(self) -> None:
        """Multiple PR URLs in stdout should return the first match."""
        stdout = (
            "Created https://github.com/owner/repo/pull/10\n"
            "Also see https://github.com/owner/repo/pull/20\n"
        )
        assert extract_pr_number(stdout) == 10

    def test_should_handle_empty_stdout(self) -> None:
        """Empty string should return None."""
        assert extract_pr_number("") is None

    def test_should_handle_non_numeric_pr_pattern(self) -> None:
        """PR # followed by non-numeric text should not match."""
        stdout = "See PR #abc for details"
        assert extract_pr_number(stdout) is None

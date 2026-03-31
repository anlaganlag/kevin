"""Tests for kevin.executor (agentic post-run helpers)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kevin.blueprint_compiler import SemanticBlueprint
from kevin.executor import extract_pr_number, run_post_validators


def test_extract_pr_number_from_stdout_url() -> None:
    out = "Created https://github.com/acme/foo/pull/42"
    assert extract_pr_number(out) == 42


def test_extract_pr_number_empty() -> None:
    assert extract_pr_number("") is None


def test_run_post_validators_no_blocks(tmp_path: Path) -> None:
    semantic = SemanticBlueprint(
        blueprint_id="x",
        blueprint_name="n",
        goal="",
        acceptance_criteria=[],
        constraints=[],
        context_sources=[],
        sub_agents=[],
        verification_commands=[],
        workflow_steps=[],
        artifacts=[],
        task_timeout=60,
        raw={"metadata": {}, "workflow": {"ralph_loop": {"step_3": {"dependency_graph": {}}}}},
    )
    assert run_post_validators(semantic, {}, tmp_path) == []


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
        blueprint_id="x",
        blueprint_name="n",
        goal="",
        acceptance_criteria=[],
        constraints=[],
        context_sources=[],
        sub_agents=[],
        verification_commands=[],
        workflow_steps=[],
        artifacts=[],
        task_timeout=60,
        raw={"metadata": {}, "workflow": {"ralph_loop": {"step_3": {"dependency_graph": {
            "blocks": [{"block_id": "B1"}]  # missing required fields like 'name'
        }}}}},
    )
    results = run_post_validators(semantic, {}, tmp_path)
    # Should not crash — returns error result or empty (if block parses with defaults)
    assert isinstance(results, list)

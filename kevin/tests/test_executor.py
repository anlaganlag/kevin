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

"""Post-execution helpers for agentic (single-worker) blueprint runs."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from kevin.agent_runner import _run_validators
from kevin.blueprint_compiler import SemanticBlueprint
from kevin.blueprint_loader import _extract_blocks, _parse_block, _topological_sort


def run_post_validators(
    semantic: SemanticBlueprint,
    variables: dict[str, str],
    cwd: Path,
) -> list[dict[str, Any]]:
    """Run all block validators from the blueprint after the worker finishes.

    Uses the same validator implementations as block-by-block mode, in dependency order.
    """
    blocks_raw = _extract_blocks(semantic.raw)
    if not blocks_raw:
        return []
    blocks = [_parse_block(b) for b in blocks_raw]
    ordered = _topological_sort(blocks)
    validators: list = []
    for block in ordered:
        validators.extend(block.validators)
    if not validators:
        return []
    return _run_validators(validators, variables, cwd)


def extract_pr_number(
    stdout: str,
    *,
    repo: str = "",
    issue_number: int = 0,
) -> int | None:
    """Best-effort PR number from worker stdout, then optional gh search."""
    if not stdout:
        return _pr_from_gh_issue(repo, issue_number)

    patterns = [
        r"github\.com/[^/\s]+/[^/\s]+/pull/(\d+)",
        r"https://github\.com/[^/\s]+/[^/\s]+/pull/(\d+)",
        r"\bpull/(\d+)\b",
        r"PR\s*#(\d+)",
        r"#(\d+)\s+(?:merged|opened|created)",
    ]
    found: list[int] = []
    for pat in patterns:
        for m in re.finditer(pat, stdout, re.IGNORECASE):
            try:
                found.append(int(m.group(1)))
            except (ValueError, IndexError):
                continue
    if found:
        return found[-1]

    return _pr_from_gh_issue(repo, issue_number)


def _pr_from_gh_issue(repo: str, issue_number: int) -> int | None:
    if not repo or issue_number <= 0:
        return None
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                repo,
                "--state",
                "open",
                "--search",
                f"closes:#{issue_number}",
                "--json",
                "number",
                "--limit",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        prs = json.loads(result.stdout or "[]")
        return int(prs[0]["number"]) if prs else None
    except Exception:
        return None

"""Tests for _notify_teams() duration_seconds field in the Teams payload."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from kevin.blueprint_loader import Block
from kevin.config import KevinConfig
from kevin.state import BlockState, RunState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(dry_run: bool = False) -> KevinConfig:
    from pathlib import Path
    return KevinConfig(
        kevin_root=Path("/tmp"),
        blueprints_dir=Path("/tmp/blueprints"),
        target_repo=Path("/tmp/target"),
        state_dir=Path("/tmp/.kevin/runs"),
        repo_owner="owner",
        repo_name="repo",
        dry_run=dry_run,
        verbose=False,
    )


def _make_run(blocks: dict[str, BlockState] | None = None) -> RunState:
    return RunState(
        run_id="20260328-000000-abc123",
        blueprint_id="test_bp",
        issue_number=1,
        repo="owner/repo",
        status="completed",
        blocks=blocks or {},
    )


def _make_block(block_id: str = "B1", name: str = "Test Block") -> Block:
    """Create a minimal Block object for testing."""
    b = MagicMock(spec=Block)
    b.block_id = block_id
    b.name = name
    return b


def _capture_payload(
    config: KevinConfig,
    run: RunState,
    blocks: list[Block],
    status: str = "completed",
) -> dict[str, Any]:
    """Call _notify_teams() with a mocked urlopen and return the decoded payload."""
    from kevin.cli import _notify_teams

    captured: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: int = 10) -> None:  # noqa: ARG001
        captured.update(json.loads(req.data))

    env_patch = {
        "TEAMS_BOT_URL": "http://fake-bot",
        "GITHUB_RUN_ID": "",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_REPOSITORY": "",
    }

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with patch("os.environ", env_patch):
            with patch("os.getenv", side_effect=lambda k, default="": env_patch.get(k, default)):
                _notify_teams(config, run, blocks, issue=None, status=status)

    return captured


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNotifyPayloadPrNumber:
    """_notify_teams() includes pr_number and pr_url when B3 output has a GitHub PR URL."""

    def test_should_extract_pr_number_from_b3_output(self) -> None:
        """B3 output_summary is a PR URL → payload has pr_number=7 and pr_url."""
        b3 = BlockState(
            block_id="B3",
            status="passed",
            started_at="2026-03-28T10:00:00+00:00",
            completed_at="2026-03-28T10:00:10+00:00",
            output_summary="https://github.com/centific-cn/kevin-test-target/pull/7",
        )
        run = _make_run(blocks={"B3": b3})
        block = _make_block("B3", "Create PR")

        payload = _capture_payload(_make_config(), run, [block])

        assert payload["pr_number"] == 7
        assert payload["pr_url"] == "https://github.com/owner/repo/pull/7"

    def test_should_handle_gh_pr_create_output_format(self) -> None:
        """B3 output has multiline text with PR URL embedded → extracts pr_number=42."""
        b3 = BlockState(
            block_id="B3",
            status="passed",
            started_at="2026-03-28T10:00:00+00:00",
            completed_at="2026-03-28T10:00:10+00:00",
            output_summary="Creating pull request...\nhttps://github.com/owner/repo/pull/42\nDone.",
        )
        run = _make_run(blocks={"B3": b3})
        block = _make_block("B3", "Create PR")

        payload = _capture_payload(_make_config(), run, [block])

        assert payload["pr_number"] == 42

    def test_should_not_include_pr_number_when_no_pr_url_in_output(self) -> None:
        """B3 output_summary has no PR URL → no pr_number or pr_url in payload."""
        b3 = BlockState(
            block_id="B3",
            status="passed",
            started_at="2026-03-28T10:00:00+00:00",
            completed_at="2026-03-28T10:00:10+00:00",
            output_summary="All checks passed",
        )
        run = _make_run(blocks={"B3": b3})
        block = _make_block("B3", "Create PR")

        payload = _capture_payload(_make_config(), run, [block])

        assert "pr_number" not in payload
        assert "pr_url" not in payload

    def test_should_not_include_pr_number_when_status_is_running(self) -> None:
        """Even if B3 has PR URL, status='running' → no pr_number in payload."""
        b3 = BlockState(
            block_id="B3",
            status="passed",
            started_at="2026-03-28T10:00:00+00:00",
            completed_at="2026-03-28T10:00:10+00:00",
            output_summary="https://github.com/owner/repo/pull/99",
        )
        run = _make_run(blocks={"B3": b3})
        block = _make_block("B3", "Create PR")

        payload = _capture_payload(_make_config(), run, [block], status="running")

        assert "pr_number" not in payload
        assert "pr_url" not in payload


class TestNotifyTeamsDurationSeconds:
    """_notify_teams() block payload includes correct duration_seconds."""

    def test_should_include_duration_when_block_has_timestamps(self) -> None:
        """BlockState with started_at and completed_at 32s apart yields duration_seconds=32.0."""
        bs = BlockState(
            block_id="B1",
            status="passed",
            started_at="2026-03-28T10:00:00+00:00",
            completed_at="2026-03-28T10:00:32+00:00",
        )
        run = _make_run(blocks={"B1": bs})
        block = _make_block("B1", "First Block")

        payload = _capture_payload(_make_config(), run, [block])

        b1_entry = next(b for b in payload["blocks"] if b["block_id"] == "B1")
        assert b1_entry["duration_seconds"] == 32.0

    def test_should_omit_duration_when_block_has_no_completed_at(self) -> None:
        """Running block with only started_at should yield duration_seconds=None."""
        bs = BlockState(
            block_id="B1",
            status="running",
            started_at="2026-03-28T10:00:00+00:00",
            completed_at="",  # not yet finished
        )
        run = _make_run(blocks={"B1": bs})
        block = _make_block("B1", "First Block")

        payload = _capture_payload(_make_config(), run, [block], status="running")

        b1_entry = next(b for b in payload["blocks"] if b["block_id"] == "B1")
        assert b1_entry["duration_seconds"] is None

    def test_should_omit_duration_when_block_is_pending(self) -> None:
        """Block with no BlockState in run.blocks yields duration_seconds=None."""
        run = _make_run(blocks={})  # no block state at all
        block = _make_block("B1", "First Block")

        payload = _capture_payload(_make_config(), run, [block], status="running")

        b1_entry = next(b for b in payload["blocks"] if b["block_id"] == "B1")
        assert b1_entry["duration_seconds"] is None

"""Tests for kevin/dashboard/data_loader.py.

Structure: Arrange → Act → Assert (AAA)
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from kevin.dashboard.data_loader import (
    BlockInfo,
    BlueprintBlockInfo,
    BlueprintInfo,
    RunDetail,
    RunSummary,
    list_blueprints,
    list_runs,
    load_block_log,
    load_blueprint,
    load_run,
)

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

BLUEPRINTS_DIR = Path(__file__).parent.parent.parent / "blueprints"


def _make_run_yaml(
    tmp_path: Path,
    run_id: str,
    *,
    blueprint_id: str = "bp_test.1.0.0",
    issue_number: int = 42,
    repo: str = "org/repo",
    status: str = "completed",
    created_at: str = "2026-03-27T10:00:00+00:00",
    completed_at: str = "2026-03-27T10:05:30+00:00",
    blocks: dict | None = None,
    variables: dict | None = None,
) -> Path:
    """Write a minimal run.yaml into tmp_path/{run_id}/run.yaml."""
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "run_id": run_id,
        "blueprint_id": blueprint_id,
        "issue_number": issue_number,
        "repo": repo,
        "status": status,
        "created_at": created_at,
        "completed_at": completed_at,
        "blocks": blocks or {},
        "variables": variables or {},
    }
    run_file = run_dir / "run.yaml"
    run_file.write_text(yaml.safe_dump(data), encoding="utf-8")
    return run_dir


def _block_data(
    block_id: str,
    *,
    status: str = "passed",
    runner: str = "claude_cli",
    exit_code: int | None = 0,
    retries: int = 0,
    started_at: str = "2026-03-27T10:01:00+00:00",
    completed_at: str = "2026-03-27T10:02:00+00:00",
    validator_results: list | None = None,
    error: str = "",
    output_summary: str = "",
) -> dict:
    return {
        "block_id": block_id,
        "status": status,
        "runner": runner,
        "exit_code": exit_code,
        "retries": retries,
        "started_at": started_at,
        "completed_at": completed_at,
        "validator_results": validator_results or [],
        "error": error,
        "output_summary": output_summary,
    }


# ---------------------------------------------------------------------------
# TestListRuns
# ---------------------------------------------------------------------------


class TestListRuns:
    def test_should_return_summaries_newest_first(self, tmp_path: Path) -> None:
        """list_runs should return RunSummary list sorted newest-first by run_id."""
        _make_run_yaml(
            tmp_path,
            "20260327-100000-aaaaaa",
            status="completed",
            created_at="2026-03-27T10:00:00+00:00",
            completed_at="2026-03-27T10:05:30+00:00",
            blocks={"B1": _block_data("B1", status="passed")},
        )
        _make_run_yaml(
            tmp_path,
            "20260327-110000-bbbbbb",
            status="running",
            created_at="2026-03-27T11:00:00+00:00",
            completed_at="",
            blocks={
                "B1": _block_data("B1", status="passed"),
                "B2": _block_data("B2", status="running"),
            },
        )

        summaries = list_runs(tmp_path)

        assert len(summaries) == 2
        assert all(isinstance(s, RunSummary) for s in summaries)
        # Newest first
        assert summaries[0].run_id == "20260327-110000-bbbbbb"
        assert summaries[1].run_id == "20260327-100000-aaaaaa"

    def test_should_compute_blocks_passed_and_total(self, tmp_path: Path) -> None:
        """RunSummary.blocks_passed / blocks_total should reflect block statuses."""
        _make_run_yaml(
            tmp_path,
            "20260327-100000-cccccc",
            blocks={
                "B1": _block_data("B1", status="passed"),
                "B2": _block_data("B2", status="failed"),
                "B3": _block_data("B3", status="pending"),
            },
        )

        summaries = list_runs(tmp_path)

        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.blocks_total == 3
        assert summary.blocks_passed == 1

    def test_should_compute_elapsed_seconds_when_both_timestamps_present(
        self, tmp_path: Path
    ) -> None:
        """elapsed_seconds should be positive float when run has start and end times."""
        _make_run_yaml(
            tmp_path,
            "20260327-100000-dddddd",
            created_at="2026-03-27T10:00:00+00:00",
            completed_at="2026-03-27T10:05:30+00:00",
        )

        summaries = list_runs(tmp_path)

        assert summaries[0].elapsed_seconds == pytest.approx(330.0)

    def test_should_return_none_elapsed_when_run_is_incomplete(
        self, tmp_path: Path
    ) -> None:
        """elapsed_seconds is None when completed_at is empty/missing."""
        _make_run_yaml(
            tmp_path,
            "20260327-100000-eeeeee",
            completed_at="",
        )

        summaries = list_runs(tmp_path)

        assert summaries[0].elapsed_seconds is None

    def test_should_return_empty_list_when_dir_does_not_exist(self, tmp_path: Path) -> None:
        """list_runs should return [] for a nonexistent directory."""
        nonexistent = tmp_path / "no_such_dir"

        summaries = list_runs(nonexistent)

        assert summaries == []

    def test_should_skip_unparseable_run_dirs(self, tmp_path: Path) -> None:
        """Corrupt YAML files should be skipped without raising."""
        bad_dir = tmp_path / "20260327-000000-corrupt"
        bad_dir.mkdir()
        (bad_dir / "run.yaml").write_text("not: valid: yaml: [[[", encoding="utf-8")
        _make_run_yaml(tmp_path, "20260327-100000-ffffff")

        summaries = list_runs(tmp_path)

        assert len(summaries) == 1
        assert summaries[0].run_id == "20260327-100000-ffffff"

    def test_should_skip_dirs_without_run_yaml(self, tmp_path: Path) -> None:
        """Directories without run.yaml should be silently skipped."""
        (tmp_path / "not_a_run").mkdir()
        _make_run_yaml(tmp_path, "20260327-100000-gggggg")

        summaries = list_runs(tmp_path)

        assert len(summaries) == 1

    def test_should_use_created_at_as_started_at(self, tmp_path: Path) -> None:
        """RunSummary.started_at should equal the run's created_at."""
        _make_run_yaml(tmp_path, "20260327-100000-hhhhhh", created_at="2026-03-27T10:00:00+00:00")

        summaries = list_runs(tmp_path)

        assert summaries[0].started_at == "2026-03-27T10:00:00+00:00"

    def test_summaries_are_frozen_dataclasses(self, tmp_path: Path) -> None:
        """RunSummary instances must be immutable (frozen dataclass)."""
        _make_run_yaml(tmp_path, "20260327-100000-iiiiii")
        summaries = list_runs(tmp_path)

        with pytest.raises((AttributeError, TypeError)):
            summaries[0].status = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestLoadRun
# ---------------------------------------------------------------------------


class TestLoadRun:
    def test_should_return_run_detail_with_all_blocks(self, tmp_path: Path) -> None:
        """load_run should return RunDetail with all blocks as BlockInfo."""
        blocks = {
            "B2": _block_data("B2", status="passed"),
            "B1": _block_data("B1", status="failed", exit_code=1, error="boom"),
        }
        _make_run_yaml(tmp_path, "run-001", blocks=blocks, variables={"FOO": "bar"})

        detail = load_run(tmp_path, "run-001")

        assert isinstance(detail, RunDetail)
        assert detail.run_id == "run-001"
        assert detail.variables == {"FOO": "bar"}
        assert len(detail.blocks) == 2

    def test_should_sort_blocks_by_block_id(self, tmp_path: Path) -> None:
        """Blocks in RunDetail should be sorted by block_id alphabetically."""
        blocks = {
            "B3": _block_data("B3"),
            "B1": _block_data("B1"),
            "B2": _block_data("B2"),
        }
        _make_run_yaml(tmp_path, "run-002", blocks=blocks)

        detail = load_run(tmp_path, "run-002")

        block_ids = [b.block_id for b in detail.blocks]
        assert block_ids == ["B1", "B2", "B3"]

    def test_should_map_block_fields_correctly(self, tmp_path: Path) -> None:
        """BlockInfo fields should map correctly from YAML data."""
        block = _block_data(
            "B1",
            status="failed",
            runner="shell",
            exit_code=1,
            retries=2,
            error="subprocess error",
            started_at="2026-03-27T10:01:00+00:00",
            completed_at="2026-03-27T10:01:30+00:00",
            validator_results=[{"type": "file_exists", "passed": False}],
        )
        _make_run_yaml(tmp_path, "run-003", blocks={"B1": block})

        detail = load_run(tmp_path, "run-003")

        b = detail.blocks[0]
        assert b.block_id == "B1"
        assert b.status == "failed"
        assert b.runner == "shell"
        assert b.exit_code == 1
        assert b.retries == 2
        assert b.error == "subprocess error"
        assert list(b.validator_results) == [{"type": "file_exists", "passed": False}]

    def test_should_raise_file_not_found_for_missing_run(self, tmp_path: Path) -> None:
        """load_run should raise FileNotFoundError for unknown run_id."""
        with pytest.raises(FileNotFoundError):
            load_run(tmp_path, "nonexistent-run-id")

    def test_run_detail_is_frozen(self, tmp_path: Path) -> None:
        """RunDetail must be immutable."""
        _make_run_yaml(tmp_path, "run-frozen")
        detail = load_run(tmp_path, "run-frozen")

        with pytest.raises((AttributeError, TypeError)):
            detail.status = "mutated"  # type: ignore[misc]

    def test_block_info_is_frozen(self, tmp_path: Path) -> None:
        """BlockInfo must be immutable."""
        _make_run_yaml(tmp_path, "run-block-frozen", blocks={"B1": _block_data("B1")})
        detail = load_run(tmp_path, "run-block-frozen")

        with pytest.raises((AttributeError, TypeError)):
            detail.blocks[0].status = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestLoadBlockLog
# ---------------------------------------------------------------------------


class TestLoadBlockLog:
    def test_should_return_log_content(self, tmp_path: Path) -> None:
        """load_block_log should return the content of the block log file."""
        _make_run_yaml(tmp_path, "run-log-001")
        logs_dir = tmp_path / "run-log-001" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "B1.log").write_text("=== STDOUT ===\nhello world", encoding="utf-8")

        content = load_block_log(tmp_path, "run-log-001", "B1")

        assert content == "=== STDOUT ===\nhello world"

    def test_should_return_empty_string_when_log_missing(self, tmp_path: Path) -> None:
        """load_block_log should return '' when the log file doesn't exist."""
        _make_run_yaml(tmp_path, "run-log-002")

        content = load_block_log(tmp_path, "run-log-002", "B99")

        assert content == ""

    def test_should_return_empty_string_when_run_dir_missing(self, tmp_path: Path) -> None:
        """load_block_log should return '' when the run directory doesn't exist."""
        content = load_block_log(tmp_path, "no-such-run", "B1")

        assert content == ""


# ---------------------------------------------------------------------------
# TestListBlueprints
# ---------------------------------------------------------------------------


class TestListBlueprints:
    @pytest.mark.skipif(
        not BLUEPRINTS_DIR.exists(),
        reason="blueprints/ directory not found",
    )
    def test_should_return_blueprint_infos_from_real_dir(self) -> None:
        """list_blueprints should load BlueprintInfo objects from real blueprints/ dir."""
        infos = list_blueprints(BLUEPRINTS_DIR)

        assert len(infos) > 0
        assert all(isinstance(b, BlueprintInfo) for b in infos)
        assert all(b.blueprint_id for b in infos)

    @pytest.mark.skipif(
        not BLUEPRINTS_DIR.exists(),
        reason="blueprints/ directory not found",
    )
    def test_should_populate_blueprint_block_info(self) -> None:
        """BlueprintInfo.blocks should contain BlueprintBlockInfo items."""
        infos = list_blueprints(BLUEPRINTS_DIR)

        # At least one blueprint should have blocks
        blueprints_with_blocks = [b for b in infos if b.blocks]
        assert blueprints_with_blocks

        for block in blueprints_with_blocks[0].blocks:
            assert isinstance(block, BlueprintBlockInfo)
            assert block.block_id

    @pytest.mark.skipif(
        not BLUEPRINTS_DIR.exists(),
        reason="blueprints/ directory not found",
    )
    def test_should_return_blueprint_infos_frozen(self) -> None:
        """BlueprintInfo should be immutable."""
        infos = list_blueprints(BLUEPRINTS_DIR)

        with pytest.raises((AttributeError, TypeError)):
            infos[0].blueprint_id = "mutated"  # type: ignore[misc]

    def test_should_return_empty_list_when_dir_does_not_exist(self, tmp_path: Path) -> None:
        """list_blueprints should return [] for a nonexistent directory."""
        nonexistent = tmp_path / "no_blueprints"

        infos = list_blueprints(nonexistent)

        assert infos == []

    def test_should_return_empty_list_when_dir_has_no_yaml(self, tmp_path: Path) -> None:
        """list_blueprints should return [] when no .yaml files exist."""
        (tmp_path / "not_a_blueprint.txt").write_text("ignore me")

        infos = list_blueprints(tmp_path)

        assert infos == []

    def test_should_skip_unparseable_blueprint_files(self, tmp_path: Path) -> None:
        """Corrupt blueprint YAMLs should be skipped without raising."""
        (tmp_path / "bad.yaml").write_text("not: valid: yaml: [[[", encoding="utf-8")

        infos = list_blueprints(tmp_path)

        assert infos == []

    @pytest.mark.skipif(
        not BLUEPRINTS_DIR.exists(),
        reason="blueprints/ directory not found",
    )
    def test_should_load_specific_blueprint_by_id(self) -> None:
        """load_blueprint should return a BlueprintInfo for bp_coding_task.1.0.0."""
        info = load_blueprint(BLUEPRINTS_DIR, "bp_coding_task.1.0.0")

        assert isinstance(info, BlueprintInfo)
        assert info.blueprint_id == "bp_coding_task.1.0.0"

    def test_should_raise_for_nonexistent_blueprint(self, tmp_path: Path) -> None:
        """load_blueprint should raise FileNotFoundError for unknown blueprint_id."""
        with pytest.raises(FileNotFoundError):
            load_blueprint(tmp_path, "bp_nonexistent.1.0.0")

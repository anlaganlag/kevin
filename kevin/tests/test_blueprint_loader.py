"""Tests for kevin.blueprint_loader — YAML parsing, topo-sort, new fields."""

import pytest
from pathlib import Path
from kevin.blueprint_loader import load, find_blueprint, Block


BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent.parent / "blueprints"


class TestLoad:
    """Blueprint YAML loading and parsing."""

    def test_should_load_coding_task_blueprint(self) -> None:
        bp = load(find_blueprint(BLUEPRINTS_DIR, "bp_coding_task.1.0.0"))
        assert bp.blueprint_id == "bp_coding_task.1.0.0"
        assert len(bp.blocks) == 3

    def test_should_parse_block_fields(self) -> None:
        bp = load(find_blueprint(BLUEPRINTS_DIR, "bp_coding_task.1.0.0"))
        b1 = bp.blocks[0]
        assert b1.block_id == "B1"
        assert b1.runner == "claude_cli"
        assert b1.timeout == 300

    def test_should_sort_blocks_topologically(self) -> None:
        bp = load(find_blueprint(BLUEPRINTS_DIR, "bp_coding_task.1.0.0"))
        ids = [b.block_id for b in bp.blocks]
        assert ids == ["B1", "B2", "B3"]

    def test_should_parse_pre_check_field(self) -> None:
        bp = load(find_blueprint(BLUEPRINTS_DIR, "bp_coding_task.1.0.0"))
        b1, b2, b3 = bp.blocks
        assert "analysis.md" in b1.pre_check
        assert "git checkout" in b2.pre_check
        assert b3.pre_check == ""

    def test_should_parse_context_filter(self) -> None:
        bp = load(find_blueprint(BLUEPRINTS_DIR, "bp_coding_task.1.0.0"))
        b2 = bp.blocks[1]
        ctx = b2.runner_config.get("context_filter", [])
        assert "node_modules" in ctx
        assert "dist" in ctx

    def test_should_parse_validators(self) -> None:
        bp = load(find_blueprint(BLUEPRINTS_DIR, "bp_coding_task.1.0.0"))
        b1 = bp.blocks[0]
        assert len(b1.validators) == 1
        assert b1.validators[0].type == "file_exists"

    def test_should_default_pre_check_to_empty(self) -> None:
        bp = load(find_blueprint(BLUEPRINTS_DIR, "bp_coding_task.1.0.0"))
        b3 = bp.blocks[2]
        assert b3.pre_check == ""


class TestFindBlueprint:
    """Blueprint file discovery."""

    def test_should_find_by_exact_id(self) -> None:
        path = find_blueprint(BLUEPRINTS_DIR, "bp_coding_task.1.0.0")
        assert path.exists()
        assert path.name == "bp_coding_task.1.0.0.yaml"

    def test_should_raise_when_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            find_blueprint(BLUEPRINTS_DIR, "bp_nonexistent.1.0.0")

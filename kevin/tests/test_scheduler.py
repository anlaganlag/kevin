"""Tests for kevin.scheduler -- wave computation with cwd conflict resolution."""

import pytest
from pathlib import Path
from kevin.scheduler import Wave, compute_waves
from kevin.blueprint_loader import Block, Validator


def _make_block(block_id: str, dependencies: list[str] = None, cwd: str = ".") -> Block:
    """Factory for Block with sensible defaults."""
    return Block(
        block_id=block_id,
        name=f"test_{block_id}",
        assigned_to="",
        dependencies=dependencies or [],
        runner="shell",
        runner_config={"cwd": cwd, "command": "echo ok"},
        timeout=10,
        max_retries=0,
        prompt_template="",
        output="",
        validators=[],
        acceptance_criteria=[],
        pre_check="",
        raw={},
    )


class TestComputeWaves:
    def test_should_produce_one_block_per_wave_for_linear_chain(self) -> None:
        blocks = [
            _make_block("B1"),
            _make_block("B2", ["B1"]),
            _make_block("B3", ["B2"]),
        ]
        waves = compute_waves(blocks, {})
        assert len(waves) == 3
        assert all(len(w.blocks) == 1 for w in waves)
        assert [w.blocks[0].block_id for w in waves] == ["B1", "B2", "B3"]

    def test_should_produce_parallel_wave_for_diamond_graph(self) -> None:
        blocks = [
            _make_block("B1", cwd="/app"),
            _make_block("B2", ["B1"], cwd="/app/mod_a"),
            _make_block("B3", ["B1"], cwd="/app/mod_b"),
            _make_block("B4", ["B2", "B3"], cwd="/app"),
        ]
        waves = compute_waves(blocks, {})
        parallel_wave = [w for w in waves if len(w.blocks) == 2]
        assert len(parallel_wave) == 1
        ids = {b.block_id for b in parallel_wave[0].blocks}
        assert ids == {"B2", "B3"}

    def test_should_split_sub_wave_on_cwd_conflict(self) -> None:
        blocks = [
            _make_block("B1", cwd="/app"),
            _make_block("B2", ["B1"], cwd="/app"),
            _make_block("B3", ["B1"], cwd="/app"),
        ]
        waves = compute_waves(blocks, {})
        level_1_waves = [w for w in waves if w.index == 1]
        assert len(level_1_waves) == 2
        assert level_1_waves[0].subindex == 1
        assert level_1_waves[1].subindex == 2

    def test_should_allow_parallel_with_different_cwd(self) -> None:
        blocks = [
            _make_block("B1"),
            _make_block("B2", ["B1"], cwd="/app"),
            _make_block("B3", ["B1"], cwd="/infra"),
        ]
        waves = compute_waves(blocks, {})
        level_1_waves = [w for w in waves if w.index == 1]
        assert len(level_1_waves) == 1
        assert len(level_1_waves[0].blocks) == 2

    def test_should_resolve_cwd_using_variables(self) -> None:
        blocks = [
            _make_block("B1"),
            _make_block("B2", ["B1"], cwd="{{target_repo}}/mod_a"),
            _make_block("B3", ["B1"], cwd="{{target_repo}}/mod_b"),
        ]
        variables = {"target_repo": "/tmp/repo"}
        waves = compute_waves(blocks, variables)
        level_1_waves = [w for w in waves if w.index == 1]
        assert len(level_1_waves) == 1

    def test_should_put_no_deps_blocks_in_wave_0(self) -> None:
        blocks = [
            _make_block("B1", cwd="/a"),
            _make_block("B2", cwd="/b"),
            _make_block("B3", cwd="/c"),
        ]
        waves = compute_waves(blocks, {})
        assert len(waves) == 1
        assert waves[0].index == 0
        assert len(waves[0].blocks) == 3

    def test_should_format_wave_label(self) -> None:
        w = Wave(index=2, subindex=1, blocks=())
        assert w.label == "Wave 3.1"

    def test_should_format_sub_wave_label(self) -> None:
        w = Wave(index=2, subindex=2, blocks=())
        assert w.label == "Wave 3.2"

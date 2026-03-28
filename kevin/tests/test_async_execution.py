"""Tests for async wave execution — parallel blocks, failure semantics, state updates."""

import asyncio
import time
from pathlib import Path

import pytest

from kevin.agent_runner import run_block_async
from kevin.blueprint_loader import Block, Validator
from kevin.scheduler import compute_waves


def _make_block(
    block_id: str,
    dependencies: list[str] | None = None,
    cwd: str = ".",
    command: str = "echo ok",
    timeout: int = 10,
) -> Block:
    return Block(
        block_id=block_id,
        name=f"test_{block_id}",
        assigned_to="",
        dependencies=dependencies or [],
        runner="shell",
        runner_config={"cwd": cwd, "command": command},
        timeout=timeout,
        max_retries=0,
        prompt_template="",
        output="",
        validators=[],
        acceptance_criteria=[],
        pre_check="",
        raw={},
    )


class TestRunBlockAsync:

    @pytest.mark.asyncio
    async def test_should_run_shell_block_async(self) -> None:
        block = _make_block("B1", command="echo hello")
        result = await run_block_async(block, {})
        assert result.success
        assert "hello" in result.stdout

    @pytest.mark.asyncio
    async def test_should_report_failure_async(self) -> None:
        block = _make_block("B1", command="exit 1")
        result = await run_block_async(block, {})
        assert not result.success


class TestParallelExecution:

    @pytest.mark.asyncio
    async def test_should_run_parallel_blocks_concurrently(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        blocks = [
            _make_block("B1", cwd=str(dir_a), command="sleep 1 && echo a"),
            _make_block("B2", cwd=str(dir_b), command="sleep 1 && echo b"),
        ]
        waves = compute_waves(blocks, {})
        assert len(waves) == 1

        start = time.monotonic()
        results = await asyncio.gather(*[
            run_block_async(b, {}) for b in waves[0].blocks
        ])
        elapsed = time.monotonic() - start

        assert all(r.success for r in results)
        assert elapsed < 1.8  # parallel: ~1s, not ~2s

    @pytest.mark.asyncio
    async def test_should_collect_all_results_even_on_failure(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "wave_fail_a"
        dir_b = tmp_path / "wave_fail_b"
        dir_a.mkdir()
        dir_b.mkdir()
        blocks = [
            _make_block("B1", cwd=str(dir_a), command="sleep 0.5 && exit 1"),
            _make_block("B2", cwd=str(dir_b), command="sleep 0.5 && echo ok"),
        ]
        waves = compute_waves(blocks, {})
        results = await asyncio.gather(*[
            run_block_async(b, {}) for b in waves[0].blocks
        ])
        assert len(results) == 2
        assert not results[0].success
        assert results[1].success

    @pytest.mark.asyncio
    async def test_should_support_dry_run(self) -> None:
        block = _make_block("B1", command="exit 1")
        result = await run_block_async(block, {}, dry_run=True)
        assert result.success
        assert "dry-run" in result.stdout

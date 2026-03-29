# Kevin v1.1: Event Bus + Learning Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add wave-based parallel Block execution and SQLite-backed Learning Agent to Kevin.

**Architecture:** Replace the serial `for` loop in `_execute_blocks()` with an `asyncio`-based wave scheduler that groups Blocks by dependency level and cwd isolation. Add a Harvester (post-run knowledge extraction) and Advisor (pre-run context injection) backed by SQLite + FTS5.

**Tech Stack:** Python 3.11+ asyncio, sqlite3 (stdlib), FTS5

**Spec:** `docs/superpowers/specs/2026-03-28-kevin-event-bus-learning-agent-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `kevin/utils.py` | Shared `resolve_cwd()` extracted from agent_runner, `extract_keywords()` |
| `kevin/scheduler.py` | `Wave` dataclass, `compute_waves()` with cwd conflict splitting |
| `kevin/learning/__init__.py` | Public exports: `advise`, `harvest_run`, `harvest_all` |
| `kevin/learning/db.py` | SQLite schema creation, connection helper, CRUD operations |
| `kevin/learning/harvester.py` | Post-run extraction: `harvest_run()`, `harvest_all()`, log parsing |
| `kevin/learning/advisor.py` | Pre-run query: `advise()`, `format_learning_context()`, dataclasses |
| `kevin/tests/test_scheduler.py` | Scheduler unit tests |
| `kevin/tests/test_async_execution.py` | Async wave execution integration tests |
| `kevin/tests/test_learning_db.py` | SQLite schema and CRUD tests |
| `kevin/tests/test_harvester.py` | Harvester unit tests |
| `kevin/tests/test_advisor.py` | Advisor unit tests |

### Modified Files

| File | Change |
|------|--------|
| `kevin/agent_runner.py:363-368` | Extract `_resolve_cwd` to `utils.py`, add import, add `run_block_async()` |
| `kevin/config.py:27-51` | Add `knowledge_db` property to `KevinConfig` |
| `kevin/cli.py:95-148` | Add advisor call in `cmd_run()`; replace `_execute_blocks` with async version |

---

### Task 1: Extract `resolve_cwd` to shared utils

**Files:**
- Create: `kevin/utils.py`
- Modify: `kevin/agent_runner.py:363-368`
- Test: `kevin/tests/test_prompt_template.py` (existing, verify no breakage)

- [ ] **Step 1: Create `kevin/utils.py` with `resolve_cwd`**

```python
"""Shared utilities used by scheduler and agent_runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kevin.prompt_template import render


def resolve_cwd(runner_config: dict[str, Any], variables: dict[str, str]) -> Path:
    """Resolve the working directory from runner_config or default to cwd.

    Shared between scheduler (cwd conflict detection) and agent_runner (execution).
    """
    cwd_raw = runner_config.get("cwd", "")
    if cwd_raw:
        return Path(render(cwd_raw, variables)).resolve()
    return Path.cwd().resolve()
```

Note: `.resolve()` added to both paths so comparison is on absolute canonical paths.

- [ ] **Step 2: Update `kevin/agent_runner.py` to import from utils**

Replace lines 363-368 in `kevin/agent_runner.py`:

```python
# Old:
def _resolve_cwd(runner_config: dict[str, Any], variables: dict[str, str]) -> Path:
    """Resolve the working directory from runner_config or default to cwd."""
    cwd_raw = runner_config.get("cwd", "")
    if cwd_raw:
        return Path(render(cwd_raw, variables))
    return Path.cwd()
```

With:

```python
from kevin.utils import resolve_cwd

def _resolve_cwd(runner_config: dict[str, Any], variables: dict[str, str]) -> Path:
    """Resolve the working directory from runner_config or default to cwd."""
    return resolve_cwd(runner_config, variables)
```

This preserves the private `_resolve_cwd` name for all existing internal callers while delegating to the shared implementation.

- [ ] **Step 3: Run existing tests to verify no breakage**

Run: `python -m pytest kevin/tests/ -v --tb=short`
Expected: All existing tests PASS (no behavior change, only extraction)

- [ ] **Step 4: Commit**

```bash
git add kevin/utils.py kevin/agent_runner.py
git commit -m "refactor: extract resolve_cwd to shared utils module"
```

---

### Task 2: Wave Scheduler — data structures and algorithm

**Files:**
- Create: `kevin/scheduler.py`
- Test: `kevin/tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests for `compute_waves`**

Create `kevin/tests/test_scheduler.py`:

```python
"""Tests for kevin.scheduler — wave computation with cwd conflict resolution."""

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
    """Wave computation from dependency graph."""

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
        # B2 and B3 are at the same level with different cwds → same wave
        parallel_wave = [w for w in waves if len(w.blocks) == 2]
        assert len(parallel_wave) == 1
        ids = {b.block_id for b in parallel_wave[0].blocks}
        assert ids == {"B2", "B3"}

    def test_should_split_sub_wave_on_cwd_conflict(self) -> None:
        blocks = [
            _make_block("B1", cwd="/app"),
            _make_block("B2", ["B1"], cwd="/app"),
            _make_block("B3", ["B1"], cwd="/app"),  # same cwd as B2
        ]
        waves = compute_waves(blocks, {})
        # B2 and B3 at same level but same cwd → split into 2 sub-waves
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
        assert len(level_1_waves) == 1  # different resolved cwds → parallel

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest kevin/tests/test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kevin.scheduler'`

- [ ] **Step 3: Implement `kevin/scheduler.py`**

```python
"""Wave-based parallel scheduler for Blueprint Blocks.

Groups Blocks by dependency level, then splits within each level
by resolved cwd to prevent parallel Blocks from writing the same directory.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from kevin.blueprint_loader import Block
from kevin.utils import resolve_cwd


@dataclass(frozen=True)
class Wave:
    """A group of Blocks that can execute concurrently."""

    index: int          # dependency level (0-based)
    subindex: int       # cwd-conflict split within level (1-based)
    blocks: tuple[Block, ...]

    @property
    def label(self) -> str:
        return f"Wave {self.index + 1}.{self.subindex}"


def compute_waves(blocks: list[Block], variables: dict[str, str]) -> list[Wave]:
    """Compute execution waves from a topologically sorted Block list.

    Algorithm:
    1. Compute level for each block:
       level[b] = 0 if no dependencies
       level[b] = 1 + max(level[dep] for dep in b.dependencies)
    2. Group blocks by level
    3. Within each level, split by resolved cwd conflict
    4. Return flat list of Wave objects in execution order

    Args:
        blocks: Topologically sorted Block list (from blueprint_loader).
        variables: Runtime variables for cwd template resolution.
    """
    if not blocks:
        return []

    # Step 1: compute levels
    block_map = {b.block_id: b for b in blocks}
    levels: dict[str, int] = {}

    for block in blocks:
        _compute_level(block.block_id, block_map, levels)

    # Step 2: group by level
    level_groups: dict[int, list[Block]] = defaultdict(list)
    for block in blocks:
        level_groups[levels[block.block_id]].append(block)

    # Step 3: split each level by cwd conflict
    waves: list[Wave] = []
    for level_idx in sorted(level_groups.keys()):
        group = level_groups[level_idx]
        sub_waves = _split_by_cwd(group, variables)
        for sub_idx, sub_blocks in enumerate(sub_waves, start=1):
            waves.append(Wave(
                index=level_idx,
                subindex=sub_idx,
                blocks=tuple(sub_blocks),
            ))

    return waves


def _compute_level(
    block_id: str,
    block_map: dict[str, Block],
    levels: dict[str, int],
) -> int:
    """Recursively compute the dependency level for a block."""
    if block_id in levels:
        return levels[block_id]

    block = block_map[block_id]
    if not block.dependencies:
        levels[block_id] = 0
        return 0

    dep_levels = [
        _compute_level(dep, block_map, levels)
        for dep in block.dependencies
        if dep in block_map
    ]
    level = 1 + max(dep_levels) if dep_levels else 0
    levels[block_id] = level
    return level


def _split_by_cwd(
    blocks: list[Block],
    variables: dict[str, str],
) -> list[list[Block]]:
    """Split a same-level group into sub-waves by resolved cwd conflict.

    Blocks are scanned in original order. If a block's resolved cwd
    is already claimed by the current sub-wave, it goes to the next one.
    """
    if len(blocks) <= 1:
        return [blocks]

    sub_waves: list[list[Block]] = [[]]
    cwd_sets: list[set[str]] = [set()]

    for block in blocks:
        resolved = str(resolve_cwd(block.runner_config, variables))
        placed = False
        for i, cwd_set in enumerate(cwd_sets):
            if resolved not in cwd_set:
                cwd_set.add(resolved)
                sub_waves[i].append(block)
                placed = True
                break
        if not placed:
            cwd_sets.append({resolved})
            sub_waves.append([block])

    return [sw for sw in sub_waves if sw]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest kevin/tests/test_scheduler.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add kevin/scheduler.py kevin/tests/test_scheduler.py
git commit -m "feat: add wave-based parallel scheduler with cwd conflict resolution"
```

---

### Task 3: Async execution engine

**Files:**
- Modify: `kevin/agent_runner.py` (add `run_block_async`)
- Modify: `kevin/cli.py:287-356` (replace `_execute_blocks` with async version)
- Test: `kevin/tests/test_async_execution.py`

- [ ] **Step 1: Write failing tests for async execution**

Create `kevin/tests/test_async_execution.py`:

```python
"""Tests for async wave execution — parallel blocks, failure semantics, state updates."""

import asyncio
import time
from pathlib import Path

import pytest

from kevin.agent_runner import run_block_async
from kevin.blueprint_loader import Block, Validator
from kevin.scheduler import compute_waves


def _make_block(block_id: str, dependencies: list[str] = None, cwd: str = ".",
                command: str = "echo ok", timeout: int = 10) -> Block:
    return Block(
        block_id=block_id, name=f"test_{block_id}", assigned_to="",
        dependencies=dependencies or [], runner="shell",
        runner_config={"cwd": cwd, "command": command},
        timeout=timeout, max_retries=0, prompt_template="", output="",
        validators=[], acceptance_criteria=[], pre_check="", raw={},
    )


class TestRunBlockAsync:
    """Async wrapper for run_block."""

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
    """Wave-level parallel execution."""

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
        assert len(waves) == 1  # both in wave 0, different cwds

        start = time.monotonic()
        results = await asyncio.gather(*[
            run_block_async(b, {}) for b in waves[0].blocks
        ])
        elapsed = time.monotonic() - start

        assert all(r.success for r in results)
        assert elapsed < 1.8  # parallel: ~1s, not ~2s

    @pytest.mark.asyncio
    async def test_should_collect_all_results_even_on_failure(self) -> None:
        blocks = [
            _make_block("B1", cwd="/tmp/wave_a", command="sleep 0.5 && exit 1"),
            _make_block("B2", cwd="/tmp/wave_b", command="sleep 0.5 && echo ok"),
        ]
        waves = compute_waves(blocks, {})
        results = await asyncio.gather(*[
            run_block_async(b, {}) for b in waves[0].blocks
        ])
        # Both complete — gather does not cancel on first failure
        assert len(results) == 2
        assert not results[0].success  # B1 failed
        assert results[1].success      # B2 still completed

    @pytest.mark.asyncio
    async def test_should_support_dry_run(self) -> None:
        block = _make_block("B1", command="exit 1")  # would fail if executed
        result = await run_block_async(block, {}, dry_run=True)
        assert result.success
        assert "dry-run" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest kevin/tests/test_async_execution.py -v`
Expected: FAIL — `ImportError: cannot import name 'run_block_async'`

Note: Install pytest-asyncio if not present: `pip install pytest-asyncio`

- [ ] **Step 3: Add `run_block_async` to `kevin/agent_runner.py`**

Add at the end of `kevin/agent_runner.py` (after the `_resolve_cwd` function):

```python
# ---------------------------------------------------------------------------
# Async wrapper
# ---------------------------------------------------------------------------

async def run_block_async(
    block: Block,
    variables: dict[str, str],
    *,
    dry_run: bool = False,
    is_retry: bool = False,
) -> BlockResult:
    """Async wrapper — runs synchronous run_block in a thread pool.

    run_block() internals (subprocess, heartbeat, validators) are unchanged.
    Only the scheduling layer is async. Uses asyncio.to_thread (Python 3.11+).
    """
    import asyncio
    return await asyncio.to_thread(
        run_block, block, variables, dry_run=dry_run, is_retry=is_retry,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest kevin/tests/test_async_execution.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add kevin/agent_runner.py kevin/tests/test_async_execution.py
git commit -m "feat: add run_block_async wrapper for parallel wave execution"
```

---

### Task 4: Integrate wave scheduler into `cli.py`

**Files:**
- Modify: `kevin/cli.py:287-356` (replace `_execute_blocks` body)

- [ ] **Step 1: Replace `_execute_blocks` with async wave dispatch**

Replace the `_execute_blocks` function (lines 287-356 in `kevin/cli.py`) with:

```python
def _execute_blocks(
    config: KevinConfig,
    state_mgr: StateManager,
    run: RunState,
    blocks: list[Block],
    variables: dict[str, str],
    *,
    issue: Issue | None = None,
) -> int:
    """Execute blocks using wave-based parallel scheduler."""
    import asyncio
    return asyncio.run(
        _execute_blocks_async(config, state_mgr, run, blocks, variables, issue=issue)
    )


async def _execute_blocks_async(
    config: KevinConfig,
    state_mgr: StateManager,
    run: RunState,
    blocks: list[Block],
    variables: dict[str, str],
    *,
    issue: Issue | None = None,
) -> int:
    """Execute blocks as parallel waves with retry logic."""
    import asyncio
    from kevin.scheduler import compute_waves
    from kevin.agent_runner import run_block_async

    waves = compute_waves(blocks, variables)
    all_passed = True

    for wave in waves:
        parallel = len(wave.blocks) > 1
        suffix = " (parallel)" if parallel else ""
        block_ids = [b.block_id for b in wave.blocks]
        _log(config, f"\n--- {wave.label}: {block_ids}{suffix} ---")

        # Mark all blocks in wave as running + set started_at
        for block in wave.blocks:
            bs = BlockState(block_id=block.block_id, status="running", runner=block.runner)
            bs.started_at = _now()
            state_mgr.update_block(run, bs)

        if not config.dry_run:
            _notify_teams(config, run, blocks, issue, "running")

        # Execute wave — all blocks in parallel via gather
        async def _run_single(block: Block) -> tuple[Block, bool]:
            """Run a single block with retry logic. Returns (block, success)."""
            success = False
            for attempt in range(block.max_retries + 1):
                if attempt > 0:
                    _log(config, f"  {block.block_id}: Retry {attempt}/{block.max_retries}...")

                result = await run_block_async(
                    block, variables, dry_run=config.dry_run, is_retry=attempt > 0,
                )

                # Save logs (event loop thread — safe)
                log_id = f"{block.block_id}.attempt-{attempt}" if attempt > 0 else block.block_id
                state_mgr.save_block_logs(
                    run.run_id, log_id,
                    prompt=result.prompt or block.prompt_template,
                    stdout=result.stdout or "",
                    stderr=result.stderr or "",
                )

                bs = run.blocks.get(block.block_id, BlockState(block_id=block.block_id))
                bs.retries = attempt
                bs.exit_code = result.exit_code
                bs.output_summary = result.stdout[:500] if result.stdout else ""
                bs.validator_results = result.validator_results or []

                if result.success:
                    bs.status = "passed"
                    bs.completed_at = _now()
                    state_mgr.update_block(run, bs)
                    _log(config, f"  {block.block_id}: PASSED")
                    success = True
                    break
                else:
                    _log(config, f"  {block.block_id}: FAILED: {result.stderr[:200]}")
                    bs.error = result.stderr[:500]

            if not success:
                bs.status = "failed"
                bs.completed_at = _now()
                state_mgr.update_block(run, bs)
                _err(f"Block {block.block_id} failed after {block.max_retries + 1} attempts")

            return block, success

        results = await asyncio.gather(*[_run_single(b) for b in wave.blocks])

        # Check wave results — any failure stops subsequent waves
        if any(not success for _, success in results):
            all_passed = False
            break

    # Finalize run
    final_status = "completed" if all_passed else "failed"
    state_mgr.complete_run(run, final_status)

    # Harvest knowledge (never blocks main path — constraint C1)
    try:
        from kevin.learning import harvest_run
        harvest_run(config.knowledge_db, config.state_dir, run.run_id)
    except Exception:
        pass

    # Post completion comment
    if not config.dry_run:
        _post_completion_comment(config, run)

    _log(config, f"\nRun {run.run_id}: {final_status}")
    return 0 if all_passed else 1
```

Add the `_now` import at the top of `cli.py` if not already present:

```python
from kevin.state import BlockState, RunState, StateManager
# Add:
from datetime import datetime, timezone

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
```

- [ ] **Step 2: Run all existing tests to verify backward compatibility**

Run: `python -m pytest kevin/tests/ -v --tb=short`
Expected: All existing tests PASS (serial blueprints produce one-block waves, identical behavior)

- [ ] **Step 3: Commit**

```bash
git add kevin/cli.py
git commit -m "feat: integrate wave scheduler into execution loop with async dispatch"
```

---

### Task 5: Add `knowledge_db` to KevinConfig

**Files:**
- Modify: `kevin/config.py:27-51`

- [ ] **Step 1: Add `knowledge_db` property to `KevinConfig`**

Add after line 50 in `kevin/config.py` (after `repo_full_name` property):

```python
    @property
    def knowledge_db(self) -> Path:
        """Path to the SQLite knowledge database."""
        return self.target_repo / ".kevin" / "knowledge.db"
```

- [ ] **Step 2: Run existing tests**

Run: `python -m pytest kevin/tests/ -v --tb=short`
Expected: All PASS (property is read-only, no behavior change)

- [ ] **Step 3: Commit**

```bash
git add kevin/config.py
git commit -m "feat: add knowledge_db path property to KevinConfig"
```

---

### Task 6: Learning DB — SQLite schema and connection

**Files:**
- Create: `kevin/learning/__init__.py`
- Create: `kevin/learning/db.py`
- Test: `kevin/tests/test_learning_db.py`

- [ ] **Step 1: Write failing tests for DB schema**

Create `kevin/tests/test_learning_db.py`:

```python
"""Tests for kevin.learning.db — SQLite schema creation and operations."""

import json
import sqlite3
from pathlib import Path

import pytest

from kevin.learning.db import connect, ensure_schema, upsert_run, upsert_block, upsert_fts, delete_fts


@pytest.fixture
def db(tmp_path: Path):
    db_path = tmp_path / "test_knowledge.db"
    conn = connect(db_path)
    ensure_schema(conn)
    yield conn
    conn.close()


class TestSchema:
    def test_should_create_tables_on_first_connect(self, db: sqlite3.Connection) -> None:
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {t[0] for t in tables}
        assert "run_history" in names
        assert "block_history" in names
        # FTS tables show up differently
        fts_check = db.execute(
            "SELECT * FROM block_logs_fts LIMIT 0"
        ).fetchall()
        assert fts_check == []  # table exists, no rows


class TestUpsertRun:
    def test_should_insert_run(self, db: sqlite3.Connection) -> None:
        upsert_run(db, run_id="r1", blueprint_id="bp_test.1.0.0",
                    issue_number=42, issue_title="Add feature",
                    repo="owner/repo", status="completed",
                    total_blocks=3, passed_blocks=3,
                    failed_block_id=None, failure_reason=None,
                    elapsed_seconds=120.5, created_at="2026-03-28T10:00:00Z",
                    variables_json='{"issue_number": "42"}')
        row = db.execute("SELECT * FROM run_history WHERE run_id='r1'").fetchone()
        assert row is not None

    def test_should_upsert_same_run_id(self, db: sqlite3.Connection) -> None:
        for status in ("running", "completed"):
            upsert_run(db, run_id="r1", blueprint_id="bp_test.1.0.0",
                        issue_number=42, issue_title="Add feature",
                        repo="o/r", status=status,
                        total_blocks=3, passed_blocks=3,
                        failed_block_id=None, failure_reason=None,
                        elapsed_seconds=100.0, created_at="2026-03-28T10:00:00Z",
                        variables_json="{}")
        count = db.execute("SELECT COUNT(*) FROM run_history WHERE run_id='r1'").fetchone()[0]
        assert count == 1


class TestUpsertBlock:
    def test_should_insert_block(self, db: sqlite3.Connection) -> None:
        upsert_block(db, run_id="r1", block_id="B1", blueprint_id="bp_test.1.0.0",
                      block_name="analyze", runner="claude_cli",
                      status="passed", exit_code=0, retries=0,
                      elapsed_seconds=30.0, error=None, validator_json="[]")
        row = db.execute("SELECT * FROM block_history WHERE run_id='r1' AND block_id='B1'").fetchone()
        assert row is not None


class TestFtsIdempotency:
    def test_should_have_exactly_one_row_after_double_insert(self, db: sqlite3.Connection) -> None:
        for _ in range(2):
            delete_fts(db, run_id="r1", block_id="B1")
            upsert_fts(db, run_id="r1", block_id="B1", blueprint_id="bp_test.1.0.0",
                        status="passed", issue_title="Add feature",
                        issue_body="body text", prompt="do something",
                        output_summary="done")
        count = db.execute(
            "SELECT COUNT(*) FROM block_logs_fts WHERE run_id='r1' AND block_id='B1'"
        ).fetchone()[0]
        assert count == 1


class TestVariablesWhitelist:
    def test_should_only_serialize_safe_fields(self) -> None:
        from kevin.learning.db import safe_variables_json
        variables = {
            "issue_number": "42",
            "issue_title": "Add feature",
            "target_repo": "/home/secret/path",
            "issue_body": "long body text...",
        }
        result = json.loads(safe_variables_json(variables))
        assert "issue_number" in result
        assert "issue_title" in result
        assert "target_repo" not in result
        assert "issue_body" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest kevin/tests/test_learning_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kevin.learning'`

- [ ] **Step 3: Create `kevin/learning/__init__.py`**

```python
"""Kevin Learning Agent — knowledge extraction and context injection."""

from kevin.learning.advisor import advise, format_learning_context
from kevin.learning.harvester import harvest_run, harvest_all

__all__ = ["advise", "format_learning_context", "harvest_run", "harvest_all"]
```

- [ ] **Step 4: Implement `kevin/learning/db.py`**

```python
"""SQLite schema, connection, and CRUD operations for the knowledge database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

VARIABLES_WHITELIST = frozenset({
    "issue_number", "issue_title", "issue_labels",
    "repo_full", "owner", "repo",
})

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS run_history (
    run_id          TEXT PRIMARY KEY,
    blueprint_id    TEXT NOT NULL,
    issue_number    INTEGER,
    issue_title     TEXT,
    repo            TEXT,
    status          TEXT NOT NULL,
    total_blocks    INTEGER,
    passed_blocks   INTEGER,
    failed_block_id TEXT,
    failure_reason  TEXT,
    elapsed_seconds REAL,
    created_at      TEXT,
    variables_json  TEXT
);

CREATE TABLE IF NOT EXISTS block_history (
    run_id          TEXT NOT NULL,
    block_id        TEXT NOT NULL,
    blueprint_id    TEXT NOT NULL,
    block_name      TEXT,
    runner          TEXT,
    status          TEXT NOT NULL,
    exit_code       INTEGER,
    retries         INTEGER DEFAULT 0,
    elapsed_seconds REAL,
    error           TEXT,
    validator_json  TEXT,
    PRIMARY KEY (run_id, block_id)
);
"""

_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS block_logs_fts USING fts5(
    run_id,
    block_id,
    blueprint_id,
    status,
    issue_title,
    issue_body,
    prompt,
    output_summary,
    tokenize='porter unicode61'
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Open or create the knowledge database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.Connection(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables and FTS if they don't exist."""
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_FTS_SQL)


def upsert_run(conn: sqlite3.Connection, *, run_id: str, blueprint_id: str,
               issue_number: int | None, issue_title: str | None,
               repo: str | None, status: str,
               total_blocks: int, passed_blocks: int,
               failed_block_id: str | None, failure_reason: str | None,
               elapsed_seconds: float | None, created_at: str | None,
               variables_json: str) -> None:
    """Insert or replace a run record."""
    conn.execute(
        "INSERT OR REPLACE INTO run_history VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, blueprint_id, issue_number, issue_title, repo, status,
         total_blocks, passed_blocks, failed_block_id, failure_reason,
         elapsed_seconds, created_at, variables_json),
    )
    conn.commit()


def upsert_block(conn: sqlite3.Connection, *, run_id: str, block_id: str,
                 blueprint_id: str, block_name: str | None, runner: str | None,
                 status: str, exit_code: int | None, retries: int,
                 elapsed_seconds: float | None, error: str | None,
                 validator_json: str | None) -> None:
    """Insert or replace a block record."""
    conn.execute(
        "INSERT OR REPLACE INTO block_history VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, block_id, blueprint_id, block_name, runner, status,
         exit_code, retries, elapsed_seconds, error, validator_json),
    )
    conn.commit()


def delete_fts(conn: sqlite3.Connection, *, run_id: str, block_id: str) -> None:
    """Delete FTS rows for a specific (run_id, block_id) pair."""
    conn.execute(
        "DELETE FROM block_logs_fts WHERE run_id = ? AND block_id = ?",
        (run_id, block_id),
    )


def upsert_fts(conn: sqlite3.Connection, *, run_id: str, block_id: str,
               blueprint_id: str, status: str, issue_title: str,
               issue_body: str, prompt: str, output_summary: str) -> None:
    """Insert an FTS row. Call delete_fts first for idempotency."""
    conn.execute(
        "INSERT INTO block_logs_fts VALUES (?,?,?,?,?,?,?,?)",
        (run_id, block_id, blueprint_id, status, issue_title,
         issue_body, prompt, output_summary),
    )
    conn.commit()


def safe_variables_json(variables: dict[str, str]) -> str:
    """Serialize only whitelisted variable keys."""
    return json.dumps({k: v for k, v in variables.items() if k in VARIABLES_WHITELIST})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest kevin/tests/test_learning_db.py -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add kevin/learning/__init__.py kevin/learning/db.py kevin/tests/test_learning_db.py
git commit -m "feat: add SQLite knowledge database schema and CRUD operations"
```

---

### Task 7: Harvester — post-run knowledge extraction

**Files:**
- Create: `kevin/learning/harvester.py`
- Modify: `kevin/utils.py` (add `extract_keywords`)
- Test: `kevin/tests/test_harvester.py`

- [ ] **Step 1: Write failing tests**

Create `kevin/tests/test_harvester.py`:

```python
"""Tests for kevin.learning.harvester — run extraction, log parsing, batch harvest."""

import json
from pathlib import Path

import pytest
import yaml

from kevin.learning.db import connect, ensure_schema
from kevin.learning.harvester import harvest_run, harvest_all, _find_final_log, _parse_attempt_number


@pytest.fixture
def knowledge_db(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    conn = connect(db_path)
    ensure_schema(conn)
    conn.close()
    return db_path


def _seed_run(state_dir: Path, run_id: str, status: str = "completed",
              blocks: dict | None = None, variables: dict | None = None) -> Path:
    """Create a minimal .kevin/runs/{run_id}/ structure."""
    run_dir = state_dir / run_id
    run_dir.mkdir(parents=True)
    logs_dir = run_dir / "logs"
    logs_dir.mkdir()

    run_data = {
        "run_id": run_id,
        "blueprint_id": "bp_coding_task.1.0.0",
        "issue_number": 42,
        "repo": "owner/repo",
        "status": status,
        "created_at": "2026-03-28T10:00:00+00:00",
        "completed_at": "2026-03-28T10:05:00+00:00",
        "variables": variables or {"issue_number": "42", "issue_title": "Add feature"},
        "blocks": blocks or {
            "B1": {"block_id": "B1", "status": "passed", "runner": "claude_cli",
                   "exit_code": 0, "retries": 0, "error": "",
                   "started_at": "2026-03-28T10:00:05+00:00",
                   "completed_at": "2026-03-28T10:02:00+00:00",
                   "output_summary": "analysis done", "validator_results": []},
        },
    }
    with (run_dir / "run.yaml").open("w") as f:
        yaml.safe_dump(run_data, f)

    # Write a sample log
    (logs_dir / "B1.log").write_text(
        "=== PROMPT ===\nAnalyze the repo\n\n=== STDOUT ===\nanalysis done\n"
    )
    return run_dir


class TestFindFinalLog:
    def test_should_select_highest_attempt(self, tmp_path: Path) -> None:
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "B2.log").touch()
        (logs / "B2.attempt-1.log").touch()
        (logs / "B2.attempt-10.log").touch()
        result = _find_final_log(logs, "B2")
        assert result is not None
        assert result.name == "B2.attempt-10.log"

    def test_should_select_base_log_when_no_retries(self, tmp_path: Path) -> None:
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "B1.log").touch()
        result = _find_final_log(logs, "B1")
        assert result is not None
        assert result.name == "B1.log"

    def test_should_return_none_when_no_logs(self, tmp_path: Path) -> None:
        logs = tmp_path / "logs"
        logs.mkdir()
        assert _find_final_log(logs, "B99") is None


class TestParseAttemptNumber:
    def test_base_log_is_attempt_0(self) -> None:
        assert _parse_attempt_number("B2.log", "B2") == 0

    def test_attempt_1(self) -> None:
        assert _parse_attempt_number("B2.attempt-1.log", "B2") == 1

    def test_attempt_10(self) -> None:
        assert _parse_attempt_number("B2.attempt-10.log", "B2") == 10


class TestHarvestRun:
    def test_should_insert_records(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1")
        harvest_run(knowledge_db, state_dir, "r1")

        conn = connect(knowledge_db)
        row = conn.execute("SELECT * FROM run_history WHERE run_id='r1'").fetchone()
        assert row is not None
        blocks = conn.execute("SELECT * FROM block_history WHERE run_id='r1'").fetchall()
        assert len(blocks) == 1
        conn.close()

    def test_should_be_idempotent(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1")
        harvest_run(knowledge_db, state_dir, "r1")
        harvest_run(knowledge_db, state_dir, "r1")  # second harvest

        conn = connect(knowledge_db)
        count = conn.execute("SELECT COUNT(*) FROM run_history").fetchone()[0]
        assert count == 1
        fts_count = conn.execute(
            "SELECT COUNT(*) FROM block_logs_fts WHERE run_id='r1' AND block_id='B1'"
        ).fetchone()[0]
        assert fts_count == 1
        conn.close()

    def test_should_skip_running_status(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1", status="running")
        harvest_run(knowledge_db, state_dir, "r1")

        conn = connect(knowledge_db)
        count = conn.execute("SELECT COUNT(*) FROM run_history").fetchone()[0]
        assert count == 0
        conn.close()

    def test_should_compute_elapsed_seconds(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1")
        harvest_run(knowledge_db, state_dir, "r1")

        conn = connect(knowledge_db)
        elapsed = conn.execute(
            "SELECT elapsed_seconds FROM run_history WHERE run_id='r1'"
        ).fetchone()[0]
        assert elapsed is not None
        assert elapsed == pytest.approx(300.0, abs=1.0)  # 5 min
        conn.close()


class TestHarvestAll:
    def test_should_harvest_multiple_runs(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1")
        _seed_run(state_dir, "r2")
        result = harvest_all(knowledge_db, state_dir)
        assert result.harvested == 2
        assert result.failed_parse == 0

    def test_should_skip_broken_runs(self, tmp_path: Path, knowledge_db: Path) -> None:
        state_dir = tmp_path / "runs"
        _seed_run(state_dir, "r1")
        broken = state_dir / "r_broken"
        broken.mkdir(parents=True)
        (broken / "run.yaml").write_text("{{invalid yaml")
        result = harvest_all(knowledge_db, state_dir)
        assert result.harvested == 1
        assert result.failed_parse == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest kevin/tests/test_harvester.py -v`
Expected: FAIL — `ImportError: cannot import name 'harvest_run'`

- [ ] **Step 3: Add `extract_keywords` to `kevin/utils.py`**

Append to `kevin/utils.py`:

```python
import re

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "do", "does", "did", "have", "has", "had", "will", "would",
    "can", "could", "should", "may", "might", "shall",
    "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "and", "or", "not", "no", "but", "if", "then", "else",
    "this", "that", "it", "its", "as", "so",
})


def extract_keywords(text: str, max_keywords: int = 8) -> str:
    """Extract meaningful keywords from text for FTS5 search.

    Removes stop words, keeps alphanumeric tokens, returns space-joined string.
    """
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    keywords = [t for t in tokens if t not in _STOP_WORDS and len(t) > 2]
    return " ".join(keywords[:max_keywords])
```

- [ ] **Step 4: Implement `kevin/learning/harvester.py`**

```python
"""Post-run knowledge extraction — reads .kevin/runs/ and writes to SQLite."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from kevin.learning.db import (
    connect,
    delete_fts,
    ensure_schema,
    safe_variables_json,
    upsert_block,
    upsert_fts,
    upsert_run,
)


@dataclass(frozen=True)
class HarvestResult:
    """Statistics from a batch harvest operation."""

    harvested: int
    skipped_existing: int
    failed_parse: int


def harvest_run(db_path: Path, state_dir: Path, run_id: str) -> None:
    """Extract knowledge from a single run into SQLite.

    Idempotent: safe to call multiple times for the same run_id.
    Skips runs with status other than 'completed' or 'failed' (constraint C2).
    """
    run_file = state_dir / run_id / "run.yaml"
    if not run_file.exists():
        return

    with run_file.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    status = data.get("status", "")
    if status not in ("completed", "failed"):
        return

    conn = connect(db_path)
    ensure_schema(conn)

    try:
        _harvest_run_data(conn, data, state_dir / run_id)
    finally:
        conn.close()


def harvest_all(db_path: Path, state_dir: Path) -> HarvestResult:
    """Batch-harvest all historical runs."""
    if not state_dir.exists():
        return HarvestResult(harvested=0, skipped_existing=0, failed_parse=0)

    conn = connect(db_path)
    ensure_schema(conn)

    harvested = 0
    failed_parse = 0

    existing = {
        row[0]
        for row in conn.execute("SELECT run_id FROM run_history").fetchall()
    }
    skipped = 0

    try:
        for run_dir in sorted(state_dir.iterdir()):
            run_file = run_dir / "run.yaml"
            if not (run_dir.is_dir() and run_file.exists()):
                continue

            run_id = run_dir.name
            if run_id in existing:
                skipped += 1
                continue

            try:
                with run_file.open(encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if data.get("status") not in ("completed", "failed"):
                    skipped += 1
                    continue

                _harvest_run_data(conn, data, run_dir)
                harvested += 1
            except Exception:
                failed_parse += 1
    finally:
        conn.close()

    return HarvestResult(
        harvested=harvested,
        skipped_existing=skipped,
        failed_parse=failed_parse,
    )


def _harvest_run_data(conn: "sqlite3.Connection", data: dict[str, Any], run_dir: Path) -> None:
    """Extract and write a single run's data to the database."""
    run_id = data.get("run_id", "")
    blueprint_id = data.get("blueprint_id", "")
    variables = data.get("variables", {})
    issue_title = variables.get("issue_title", "")
    issue_body = variables.get("issue_body", "")
    blocks_data: dict[str, dict] = data.get("blocks", {})

    # Compute elapsed seconds
    elapsed = _compute_elapsed(data.get("created_at", ""), data.get("completed_at", ""))

    # Find first failed block
    failed_block_id = None
    failure_reason = None
    for bid, bdata in blocks_data.items():
        if bdata.get("status") == "failed":
            failed_block_id = bid
            failure_reason = (bdata.get("error", "") or "")[:500]
            break

    passed_blocks = sum(1 for b in blocks_data.values() if b.get("status") == "passed")

    upsert_run(
        conn,
        run_id=run_id,
        blueprint_id=blueprint_id,
        issue_number=data.get("issue_number"),
        issue_title=issue_title,
        repo=data.get("repo"),
        status=data.get("status", ""),
        total_blocks=len(blocks_data),
        passed_blocks=passed_blocks,
        failed_block_id=failed_block_id,
        failure_reason=failure_reason,
        elapsed_seconds=elapsed,
        created_at=data.get("created_at"),
        variables_json=safe_variables_json(variables),
    )

    # Block history + FTS
    logs_dir = run_dir / "logs"
    for bid, bdata in blocks_data.items():
        block_elapsed = _compute_elapsed(
            bdata.get("started_at", ""), bdata.get("completed_at", ""),
        )
        upsert_block(
            conn,
            run_id=run_id,
            block_id=bid,
            blueprint_id=blueprint_id,
            block_name=bdata.get("name", ""),
            runner=bdata.get("runner", ""),
            status=bdata.get("status", ""),
            exit_code=bdata.get("exit_code"),
            retries=int(bdata.get("retries", 0)),
            elapsed_seconds=block_elapsed,
            error=(bdata.get("error") or "")[:500] or None,
            validator_json=json.dumps(bdata.get("validator_results", [])),
        )

        # FTS: index final attempt log only
        if logs_dir.exists():
            log_file = _find_final_log(logs_dir, bid)
            if log_file:
                prompt, output = _parse_log_file(log_file)
                delete_fts(conn, run_id=run_id, block_id=bid)
                upsert_fts(
                    conn,
                    run_id=run_id,
                    block_id=bid,
                    blueprint_id=blueprint_id,
                    status=bdata.get("status", ""),
                    issue_title=issue_title,
                    issue_body=issue_body,
                    prompt=prompt[:2000],
                    output_summary=(bdata.get("output_summary", "") or output)[:500],
                )


def _find_final_log(logs_dir: Path, block_id: str) -> Path | None:
    """Find the final attempt log for a block. Parses attempt numbers explicitly."""
    max_attempt = -1
    best = None
    for f in logs_dir.glob(f"{block_id}*.log"):
        attempt = _parse_attempt_number(f.name, block_id)
        if attempt > max_attempt:
            max_attempt = attempt
            best = f
    return best


def _parse_attempt_number(filename: str, block_id: str) -> int:
    """Extract attempt number from log filename.

    'B2.log' → 0
    'B2.attempt-1.log' → 1
    'B2.attempt-10.log' → 10
    """
    if filename == f"{block_id}.log":
        return 0
    match = re.search(rf"{re.escape(block_id)}\.attempt-(\d+)\.log$", filename)
    if match:
        return int(match.group(1))
    return -1  # unrecognized format


def _parse_log_file(log_path: Path) -> tuple[str, str]:
    """Extract prompt and stdout from a log file. Returns (prompt, stdout)."""
    content = log_path.read_text(encoding="utf-8", errors="replace")
    prompt = ""
    stdout = ""

    if "=== PROMPT ===" in content:
        parts = content.split("=== PROMPT ===\n", 1)
        if len(parts) > 1:
            section = parts[1]
            for marker in ("=== STDOUT ===", "=== STDERR ==="):
                if marker in section:
                    section = section.split(marker)[0]
            prompt = section.strip()

    if "=== STDOUT ===" in content:
        parts = content.split("=== STDOUT ===\n", 1)
        if len(parts) > 1:
            section = parts[1]
            if "=== STDERR ===" in section:
                section = section.split("=== STDERR ===")[0]
            stdout = section.strip()

    return prompt, stdout


def _compute_elapsed(started_at: str, completed_at: str) -> float | None:
    """Compute elapsed seconds between ISO timestamps. Returns None if unparseable."""
    if not started_at or not completed_at:
        return None
    try:
        start = _parse_iso(started_at)
        end = _parse_iso(completed_at)
        return (end - start).total_seconds()
    except (ValueError, TypeError):
        return None


def _parse_iso(ts: str) -> datetime:
    """Parse ISO 8601 timestamp, handling Z suffix."""
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest kevin/tests/test_harvester.py -v`
Expected: All 10 tests PASS

- [ ] **Step 6: Commit**

```bash
git add kevin/utils.py kevin/learning/harvester.py kevin/tests/test_harvester.py
git commit -m "feat: add Harvester for post-run knowledge extraction to SQLite"
```

---

### Task 8: Advisor — pre-run context query and rendering

**Files:**
- Create: `kevin/learning/advisor.py`
- Test: `kevin/tests/test_advisor.py`

- [ ] **Step 1: Write failing tests**

Create `kevin/tests/test_advisor.py`:

```python
"""Tests for kevin.learning.advisor — context query, rendering, silent degradation."""

from pathlib import Path

import pytest

from kevin.learning.advisor import (
    FailurePattern,
    LearningContext,
    SimilarSnippet,
    advise,
    format_learning_context,
)
from kevin.learning.db import connect, ensure_schema, upsert_run, upsert_block, upsert_fts, delete_fts


@pytest.fixture
def knowledge_db(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    conn = connect(db_path)
    ensure_schema(conn)
    conn.close()
    return db_path


def _seed_completed_run(db_path: Path, run_id: str, blueprint_id: str = "bp_coding_task.1.0.0",
                         status: str = "completed", failed_block: str | None = None,
                         failure_reason: str | None = None,
                         issue_title: str = "Add feature") -> None:
    conn = connect(db_path)
    ensure_schema(conn)
    upsert_run(conn, run_id=run_id, blueprint_id=blueprint_id,
               issue_number=42, issue_title=issue_title,
               repo="o/r", status=status, total_blocks=3,
               passed_blocks=2 if failed_block else 3,
               failed_block_id=failed_block, failure_reason=failure_reason,
               elapsed_seconds=120.0, created_at="2026-03-28T10:00:00Z",
               variables_json='{}')
    for bid in ["B1", "B2", "B3"]:
        s = "failed" if bid == failed_block else "passed"
        err = failure_reason if bid == failed_block else None
        upsert_block(conn, run_id=run_id, block_id=bid, blueprint_id=blueprint_id,
                      block_name=f"test_{bid}", runner="shell", status=s,
                      exit_code=0 if s == "passed" else 1, retries=0,
                      elapsed_seconds=30.0, error=err, validator_json="[]")
        if s == "passed":
            delete_fts(conn, run_id=run_id, block_id=bid)
            upsert_fts(conn, run_id=run_id, block_id=bid, blueprint_id=blueprint_id,
                        status="passed", issue_title=issue_title,
                        issue_body="some body", prompt="do stuff",
                        output_summary=f"completed {bid}")
    conn.close()


class TestAdvise:
    def test_should_return_empty_context_when_no_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "nonexistent" / "knowledge.db"
        ctx = advise(db_path, "bp_test.1.0.0", "title", "body")
        assert ctx.success_rate is None
        assert ctx.total_runs == 0
        assert ctx.common_failures == []
        assert ctx.similar_snippets == []

    def test_should_return_empty_context_when_empty_db(self, knowledge_db: Path) -> None:
        ctx = advise(knowledge_db, "bp_test.1.0.0", "title", "body")
        assert ctx.success_rate is None
        assert ctx.total_runs == 0

    def test_should_compute_blueprint_stats(self, knowledge_db: Path) -> None:
        _seed_completed_run(knowledge_db, "r1", status="completed")
        _seed_completed_run(knowledge_db, "r2", status="completed")
        _seed_completed_run(knowledge_db, "r3", status="failed", failed_block="B2",
                             failure_reason="tests failed")
        ctx = advise(knowledge_db, "bp_coding_task.1.0.0", "title", "body")
        assert ctx.total_runs == 3
        assert ctx.success_rate == pytest.approx(2 / 3, abs=0.01)

    def test_should_aggregate_common_failures(self, knowledge_db: Path) -> None:
        _seed_completed_run(knowledge_db, "r1", status="failed", failed_block="B2",
                             failure_reason="tests failed")
        _seed_completed_run(knowledge_db, "r2", status="failed", failed_block="B2",
                             failure_reason="tests failed")
        _seed_completed_run(knowledge_db, "r3", status="failed", failed_block="B3",
                             failure_reason="lint error")
        ctx = advise(knowledge_db, "bp_coding_task.1.0.0", "title", "body")
        assert len(ctx.common_failures) >= 1
        top = ctx.common_failures[0]
        assert top.block_id == "B2"
        assert top.count == 2

    def test_should_find_similar_by_issue_title(self, knowledge_db: Path) -> None:
        _seed_completed_run(knowledge_db, "r1", issue_title="Add user avatar upload")
        ctx = advise(knowledge_db, "bp_coding_task.1.0.0", "Add avatar feature", "body")
        assert len(ctx.similar_snippets) >= 1


class TestFormatLearningContext:
    def test_should_return_empty_string_for_empty_context(self) -> None:
        ctx = LearningContext(success_rate=None, total_runs=0,
                               common_failures=[], similar_snippets=[], risk_warnings=[])
        assert format_learning_context(ctx) == ""

    def test_should_contain_no_emoji_or_unicode(self) -> None:
        ctx = LearningContext(
            success_rate=0.75, total_runs=4,
            common_failures=[FailurePattern("B2", "tests failed", 3)],
            similar_snippets=[SimilarSnippet("r1", "Add feature", "done")],
            risk_warnings=["B2 failed last time"],
        )
        result = format_learning_context(ctx)
        assert all(ord(c) < 128 for c in result), f"Non-ASCII found: {result}"

    def test_should_respect_max_chars(self) -> None:
        ctx = LearningContext(
            success_rate=0.5, total_runs=100,
            common_failures=[FailurePattern("B2", "x" * 500, 10)],
            similar_snippets=[SimilarSnippet("r1", "y" * 200, "z" * 500)],
            risk_warnings=["warning " * 50],
        )
        result = format_learning_context(ctx, max_chars=200)
        assert len(result) <= 200

    def test_should_include_stats_line(self) -> None:
        ctx = LearningContext(success_rate=0.85, total_runs=20,
                               common_failures=[], similar_snippets=[], risk_warnings=[])
        result = format_learning_context(ctx)
        assert "[History]" in result
        assert "85%" in result
        assert "20 runs" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest kevin/tests/test_advisor.py -v`
Expected: FAIL — `ImportError: cannot import name 'advise'`

- [ ] **Step 3: Implement `kevin/learning/advisor.py`**

```python
"""Pre-run context query — generates learning context from historical runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kevin.utils import extract_keywords


@dataclass(frozen=True)
class FailurePattern:
    """A recurring failure pattern for a specific Block."""

    block_id: str
    reason: str
    count: int


@dataclass(frozen=True)
class SimilarSnippet:
    """A snippet from a historically similar successful run."""

    run_id: str
    issue_title: str
    output_summary: str


@dataclass(frozen=True)
class LearningContext:
    """Structured learning context (machine-readable)."""

    success_rate: float | None
    total_runs: int
    common_failures: list[FailurePattern] = field(default_factory=list)
    similar_snippets: list[SimilarSnippet] = field(default_factory=list)
    risk_warnings: list[str] = field(default_factory=list)


_EMPTY_CONTEXT = LearningContext(success_rate=None, total_runs=0)


def advise(
    db_path: Path,
    blueprint_id: str,
    issue_title: str,
    issue_body: str,
) -> LearningContext:
    """Query SQLite and generate historical context for the current run.

    Silent degradation: returns empty LearningContext on ANY error (constraint C1).
    """
    try:
        return _advise_impl(db_path, blueprint_id, issue_title, issue_body)
    except Exception:
        return _EMPTY_CONTEXT


def _advise_impl(
    db_path: Path,
    blueprint_id: str,
    issue_title: str,
    issue_body: str,
) -> LearningContext:
    if not db_path.exists():
        return _EMPTY_CONTEXT

    from kevin.learning.db import connect, ensure_schema

    conn = connect(db_path)
    ensure_schema(conn)

    try:
        stats = _query_stats(conn, blueprint_id)
        if stats is None:
            return _EMPTY_CONTEXT

        success_rate, total_runs = stats
        failures = _query_common_failures(conn, blueprint_id)
        similar = _query_similar_runs(conn, blueprint_id, issue_title, issue_body)
        warnings = _build_risk_warnings(conn, blueprint_id)

        return LearningContext(
            success_rate=success_rate,
            total_runs=total_runs,
            common_failures=failures,
            similar_snippets=similar,
            risk_warnings=warnings,
        )
    finally:
        conn.close()


def _query_stats(conn, blueprint_id: str) -> tuple[float, int] | None:
    """Return (success_rate, total_runs) or None if no data."""
    row = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) "
        "FROM run_history WHERE blueprint_id = ?",
        (blueprint_id,),
    ).fetchone()
    total = row[0] or 0
    if total == 0:
        return None
    completed = row[1] or 0
    return completed / total, total


def _query_common_failures(conn, blueprint_id: str) -> list[FailurePattern]:
    """Return top failure patterns grouped by (block_id, error)."""
    rows = conn.execute(
        "SELECT block_id, error, COUNT(*) as cnt "
        "FROM block_history "
        "WHERE blueprint_id = ? AND status = 'failed' AND error IS NOT NULL AND error != '' "
        "GROUP BY block_id, error "
        "ORDER BY cnt DESC "
        "LIMIT 5",
        (blueprint_id,),
    ).fetchall()
    return [FailurePattern(block_id=r[0], reason=(r[1] or "")[:200], count=r[2]) for r in rows]


def _query_similar_runs(conn, blueprint_id: str, issue_title: str, issue_body: str) -> list[SimilarSnippet]:
    """Search FTS for similar issues and return successful output snippets."""
    keywords = extract_keywords(issue_title)
    if not keywords:
        return []

    try:
        rows = conn.execute(
            "SELECT run_id, issue_title, output_summary, rank "
            "FROM block_logs_fts "
            "WHERE block_logs_fts MATCH ? "
            "AND status = 'passed' "
            "AND blueprint_id = ? "
            "ORDER BY rank "
            "LIMIT 5",
            (keywords, blueprint_id),
        ).fetchall()
    except Exception:
        return []

    seen_runs: set[str] = set()
    snippets: list[SimilarSnippet] = []
    for r in rows:
        rid = r[0]
        if rid in seen_runs:
            continue
        seen_runs.add(rid)
        snippets.append(SimilarSnippet(
            run_id=rid,
            issue_title=(r[1] or "")[:200],
            output_summary=(r[2] or "")[:300],
        ))
        if len(snippets) >= 2:
            break
    return snippets


def _build_risk_warnings(conn, blueprint_id: str) -> list[str]:
    """Generate risk warnings based on recent history."""
    warnings: list[str] = []
    last_run = conn.execute(
        "SELECT status, failed_block_id FROM run_history "
        "WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1",
        (blueprint_id,),
    ).fetchone()
    if last_run and last_run[0] == "failed" and last_run[1]:
        warnings.append(f"Last run failed at {last_run[1]}")
    return warnings


def format_learning_context(ctx: LearningContext, *, max_chars: int = 1200) -> str:
    """Render structured context into plain-text prompt injection.

    Output is plain ASCII. No emoji, no unicode symbols (constraint C5).
    """
    sections: list[str] = []

    if ctx.success_rate is not None:
        pct = f"{ctx.success_rate:.0%}"
        sections.append(f"[History] This Blueprint: {pct} success rate ({ctx.total_runs} runs)")

    for fp in ctx.common_failures[:2]:
        sections.append(f"[Warning] {fp.block_id} common failure: {fp.reason} ({fp.count}x)")

    for sn in ctx.similar_snippets[:2]:
        truncated = sn.output_summary[:300]
        sections.append(f"[Reference] Similar issue '{sn.issue_title}': {truncated}")

    for w in ctx.risk_warnings[:2]:
        sections.append(f"[Risk] {w}")

    result = "\n".join(sections)
    return result[:max_chars]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest kevin/tests/test_advisor.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add kevin/learning/advisor.py kevin/tests/test_advisor.py
git commit -m "feat: add Advisor for pre-run learning context injection"
```

---

### Task 9: Integrate Advisor into `cmd_run()`

**Files:**
- Modify: `kevin/cli.py:95-148` (add advisor call)

- [ ] **Step 1: Add advisor call in `cmd_run()`**

In `kevin/cli.py`, after line 125 (`variables = _build_variables(config, issue)`) and before line 128 (`state_mgr = StateManager(...)`), insert:

```python
    # 4b. Learning Agent — inject historical context
    try:
        from kevin.learning import advise
        from kevin.learning.advisor import format_learning_context
        ctx = advise(config.knowledge_db, intent.blueprint_id, issue.title, issue.body)
        lc = format_learning_context(ctx)
        if lc:
            variables["learning_context"] = lc
            _log(config, f"  Learning: injected {len(lc)} chars of historical context")
        else:
            _log(config, "  Learning: no historical data available")
    except Exception:
        _log(config, "  Learning: advisor unavailable (silent degradation)")
```

- [ ] **Step 2: Run all tests to verify no breakage**

Run: `python -m pytest kevin/tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add kevin/cli.py
git commit -m "feat: integrate Learning Agent advisor into cmd_run"
```

---

### Task 10: Full integration test

**Files:**
- Test: `kevin/tests/test_integration.py` (add new test class)

- [ ] **Step 1: Add integration test for wave execution + learning**

Append to `kevin/tests/test_integration.py`:

```python
class TestWaveSchedulerIntegration:
    """Verify wave scheduler works end-to-end with real blocks."""

    def test_should_execute_parallel_shell_blocks(self, target_repo: Path) -> None:
        """Two independent shell blocks should run in parallel."""
        from kevin.scheduler import compute_waves
        from kevin.blueprint_loader import Block

        dir_a = target_repo / "mod_a"
        dir_b = target_repo / "mod_b"
        dir_a.mkdir(exist_ok=True)
        dir_b.mkdir(exist_ok=True)

        blocks = [
            Block(
                block_id="B1", name="task_a", assigned_to="", dependencies=[],
                runner="shell", runner_config={"cwd": str(dir_a), "command": "echo a > result.txt"},
                timeout=10, max_retries=0, prompt_template="", output="",
                validators=[], acceptance_criteria=[], pre_check="", raw={},
            ),
            Block(
                block_id="B2", name="task_b", assigned_to="", dependencies=[],
                runner="shell", runner_config={"cwd": str(dir_b), "command": "echo b > result.txt"},
                timeout=10, max_retries=0, prompt_template="", output="",
                validators=[], acceptance_criteria=[], pre_check="", raw={},
            ),
        ]

        waves = compute_waves(blocks, {})
        assert len(waves) == 1
        assert len(waves[0].blocks) == 2

        # Execute via run_block (synchronous — just verify both complete)
        from kevin.agent_runner import run_block
        for block in blocks:
            result = run_block(block, {})
            assert result.success

        assert (dir_a / "result.txt").exists()
        assert (dir_b / "result.txt").exists()


class TestLearningIntegration:
    """Verify harvest + advise cycle works end-to-end."""

    def test_should_harvest_then_advise(self, tmp_path: Path) -> None:
        from kevin.learning.harvester import harvest_run
        from kevin.learning.advisor import advise
        from kevin.learning.db import connect, ensure_schema

        # Setup: create a fake run state
        state_dir = tmp_path / "runs"
        run_dir = state_dir / "test-run-001"
        run_dir.mkdir(parents=True)
        logs_dir = run_dir / "logs"
        logs_dir.mkdir()

        import yaml
        run_data = {
            "run_id": "test-run-001",
            "blueprint_id": "bp_coding_task.1.0.0",
            "issue_number": 1,
            "repo": "test/repo",
            "status": "completed",
            "created_at": "2026-03-28T10:00:00+00:00",
            "completed_at": "2026-03-28T10:05:00+00:00",
            "variables": {"issue_number": "1", "issue_title": "Add login page"},
            "blocks": {
                "B1": {"block_id": "B1", "status": "passed", "runner": "shell",
                       "exit_code": 0, "retries": 0, "error": "",
                       "started_at": "2026-03-28T10:00:05+00:00",
                       "completed_at": "2026-03-28T10:02:00+00:00",
                       "output_summary": "login page analysis complete",
                       "validator_results": []},
            },
        }
        with (run_dir / "run.yaml").open("w") as f:
            yaml.safe_dump(run_data, f)
        (logs_dir / "B1.log").write_text(
            "=== PROMPT ===\nAnalyze login\n\n=== STDOUT ===\nlogin page analysis complete\n"
        )

        # Harvest
        db_path = tmp_path / "knowledge.db"
        harvest_run(db_path, state_dir, "test-run-001")

        # Advise — should find the harvested run
        ctx = advise(db_path, "bp_coding_task.1.0.0", "Add login feature", "body")
        assert ctx.total_runs == 1
        assert ctx.success_rate == 1.0
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest kevin/tests/test_integration.py -v -k "Wave or Learning"`
Expected: All new tests PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest kevin/tests/ -v --tb=short`
Expected: ALL tests PASS (existing + new)

- [ ] **Step 4: Commit**

```bash
git add kevin/tests/test_integration.py
git commit -m "test: add integration tests for wave scheduler and learning agent"
```

---

## Self-Review

**Spec coverage check:**
- Spec 2.1-2.2 (Wave concept + algorithm) → Task 2 ✅
- Spec 2.3 (Wave dataclass) → Task 2 ✅
- Spec 2.4 (Failure semantics) → Task 3 tests + Task 4 implementation ✅
- Spec 2.5 (cwd conflict) → Task 2 `_split_by_cwd` ✅
- Spec 2.6 (Async model) → Task 3 `run_block_async` ✅
- Spec 2.7 (StateManager zero changes) → verified, no state.py in modified files ✅
- Spec 2.8 (Backward compat) → Task 4 sync wrapper ✅
- Spec 3.3 (SQLite schema) → Task 6 ✅
- Spec 3.4 (Harvester) → Task 7 ✅
- Spec 3.5 (Final attempt) → Task 7 `_find_final_log` + `_parse_attempt_number` ✅
- Spec 3.6 (Advisor dataclasses) → Task 8 ✅
- Spec 3.7 (Similar search) → Task 8 `_query_similar_runs` ✅
- Spec 3.8 (Variables whitelist) → Task 6 `safe_variables_json` ✅
- Spec 3.9 (Rendering) → Task 8 `format_learning_context` ✅
- Spec 3.10 (Integration) → Task 9 (advisor in cmd_run) + Task 4 (harvester in _execute_blocks_async) ✅
- Spec 3.12 (knowledge_db) → Task 5 ✅
- Spec 3.13 (elapsed prerequisite) → Task 4 `_now()` calls ✅
- Constraint C1 (silent degrade) → Task 8 try/except in `advise()` ✅
- Constraint C2 (final state only) → Task 7 status check in `harvest_run` ✅
- Constraint C3 (parse attempt) → Task 7 `_parse_attempt_number` ✅
- Constraint C4 (elapsed source) → Task 4 + Task 7 ✅
- Constraint C5 (plain ASCII) → Task 8 format test ✅
- Constraint C6 (FTS idempotency) → Task 6 `delete_fts` + Task 7 ✅

**Placeholder scan:** No TBD, TODO, or "implement later" found.

**Type consistency:** `LearningContext`, `FailurePattern`, `SimilarSnippet`, `Wave`, `HarvestResult` — names consistent across all tasks. `resolve_cwd` signature matches between utils.py and scheduler.py usage.

# Kevin v1.1: Event Bus + Learning Agent Design Spec

> 进程内并行调度 + SQLite 知识库 — 最小改动面的 pragmatic 实现

**Status**: FROZEN
**Date**: 2026-03-28
**Scope**: Kevin v1.1 (两个核心 Gap)
**Authors**: Randy + Claude

---

## Table of Contents

1. [Design Decisions Summary](#1-design-decisions-summary)
2. [Section 1: Event Bus — Wave-Based Parallel Scheduler](#2-section-1-event-bus--wave-based-parallel-scheduler)
3. [Section 2: Learning Agent — Harvester + Advisor + SQLite](#3-section-2-learning-agent--harvester--advisor--sqlite)
4. [Implementation Constraints](#4-implementation-constraints)
5. [File Change Summary](#5-file-change-summary)
6. [Test Plan](#6-test-plan)

---

## 1. Design Decisions Summary

All decisions locked during brainstorming. No open questions remain.

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Runtime model | CLI / Serverless (run-to-completion) | No long-running server, no Kafka, no infra overhead |
| Event Bus | Process-internal `asyncio` | Single-run Block parallelism, destroyed on exit |
| Parallelism granularity | Block-level within a single run | No cross-run concurrency in v1.1 |
| Knowledge storage | SQLite + FTS5 | Zero-dependency, Python built-in `sqlite3`, full-text search |
| Learning content | Structured stats + FTS5 context injection | No embedding API, no vector DB |
| `max_concurrency` | Not implemented | Deferred — current Blueprints have max 2-3 parallel Blocks |
| `read_only` Block metadata | Not implemented | Same resolved `cwd` = no parallel, period |

---

## 2. Section 1: Event Bus — Wave-Based Parallel Scheduler

### 2.1 Core Concept

Replace the sequential `for block in blocks` loop in `_execute_blocks()` with a **wave-based scheduler** that groups Blocks by dependency level and executes each wave's Blocks concurrently via `asyncio.gather`.

```
Dependency graph:  B1 → B2 → B3 (cwd=/app)
                         ↘ B4 (cwd=/app)
                         ↘ B5 (cwd=/infra)
                               ↘ B6 (depends: B4, B5)

Wave computation (with cwd conflict resolution):
  Wave 1.1: [B1]
  Wave 2.1: [B2]
  Wave 3.1: [B3(cwd=/app), B5(cwd=/infra)]   -- parallel safe
  Wave 3.2: [B4(cwd=/app)]                    -- B3 shares cwd, deferred
  Wave 4.1: [B6]
```

### 2.2 Wave Computation Algorithm

```python
def compute_waves(blocks: list[Block], variables: dict[str, str]) -> list[Wave]:
    """
    1. Compute level for each block:
       level[b] = 0 if no dependencies
       level[b] = 1 + max(level[dep] for dep in b.dependencies)
    2. Group blocks by level
    3. Within each level, scan blocks in original order:
       - Resolve cwd via shared resolve_cwd(block.runner_config, variables)
       - If resolved cwd already claimed by current sub-wave → start new sub-wave
    4. Return flat list of Wave objects
    """
```

**Inputs**: `list[Block]` (topologically sorted), `dict[str, str]` (runtime variables)
**Output**: `list[Wave]` — linear execution sequence

The scheduler is NOT a pure-static DAG layerer. It requires `variables` because cwd conflict detection depends on template variable resolution (e.g., `{{target_repo}}`).

### 2.3 Data Structures

```python
# kevin/scheduler.py

@dataclass(frozen=True)
class Wave:
    """A group of Blocks that can execute concurrently."""
    index: int        # dependency level (0-based)
    subindex: int     # cwd-conflict split within level (1-based)
    blocks: tuple[Block, ...]

    @property
    def label(self) -> str:
        return f"Wave {self.index + 1}.{self.subindex}"
```

### 2.4 Failure Semantics

**Rule**: Finish current wave, then stop.

- `asyncio.gather(return_exceptions=True)` collects all results from the current wave
- If ANY Block in the wave failed, subsequent waves are NOT scheduled
- Other Blocks in the same wave that are still running are NOT cancelled
  (rationale: `asyncio.to_thread` wraps blocking subprocess — cannot cleanly cancel)
- Failed Blocks within a wave are all recorded in state; the first failure is flagged in the run summary

### 2.5 cwd Conflict Protection

**Rule**: Same resolved `cwd` = never parallel, no exceptions.

- No "read-only runner" optimization in v1.1
- `api_call` runner also treated as non-parallelizable if same cwd (may have side effects)
- Future: add `read_only: true` Block metadata to relax this constraint

**Conflict detection uses `resolve_cwd()`** — the exact same function used by `agent_runner.py` at execution time. This function is extracted to `kevin/utils.py` so both scheduler and runner share it. No string comparison of raw config values.

### 2.6 Async Execution Model

```python
# kevin/agent_runner.py — new function
async def run_block_async(
    block: Block,
    variables: dict[str, str],
    *,
    dry_run: bool = False,
    is_retry: bool = False,
) -> BlockResult:
    """Async wrapper — runs synchronous run_block in thread pool.

    run_block() internals (subprocess, heartbeat, validators) are unchanged.
    Only the scheduling layer is async.
    """
    return await asyncio.to_thread(
        run_block, block, variables, dry_run=dry_run, is_retry=is_retry
    )
```

**What does NOT change**:
- All Runner internals (Claude CLI, Shell, API Call)
- Heartbeat watchdog
- pre_check / Validator logic
- Blueprint YAML format (dependencies field already exists)
- StateManager (see below)

### 2.7 StateManager: Zero Changes

State updates (`update_block`, `save_block_logs`) are called from the async scheduling layer (event loop thread), NOT from within `to_thread`. Therefore:

- Python object mutations are naturally serialized by the event loop
- `run.yaml` writes are serialized by the event loop
- `{block_id}.log` writes target distinct files — no conflict

No file locking, no flush aggregation, no `state.py` changes needed.

The only prerequisite: `_execute_blocks_async` must call `state_mgr.update_block()` AFTER `await`, not inside the threaded function.

### 2.8 Backward Compatibility

- Fully serial Blueprints (B1→B2→B3, no branching) produce one Block per wave — behavior identical to current code
- Blueprint YAML format unchanged — parallel capability is derived from existing `dependencies` field
- All existing tests pass without modification (they test `run_block` synchronously)
- `_execute_blocks()` sync wrapper calls `asyncio.run(_execute_blocks_async(...))` — CLI entry point stays synchronous

### 2.9 Retry Safety

Retry + `pre_check` is safe because:
- `pre_check` resets the working directory of a specific Block
- Same-cwd Blocks are never in the same sub-wave
- Therefore `pre_check` of one Block cannot destroy another Block's artifacts

### 2.10 Result Ordering

`asyncio.gather()` returns results in task creation order (not completion order). This is preserved — log output, failure summaries, and test assertions all use scheduler-defined Block order.

### 2.11 Observability

CLI log output:

```
--- Wave 1.1: [B1] ---
Block B1: analyze_requirements (runner: claude_cli)
  PASSED

--- Wave 2.1: [B2] ---
Block B2: implement_solution (runner: claude_cli)
  PASSED

--- Wave 3.1: [B3, B5] (parallel) ---
Block B3: testing (runner: shell)
Block B5: security_scan (runner: shell)
  B3: PASSED
  B5: PASSED

--- Wave 3.2: [B4] ---
Block B4: create_pr (runner: shell)
  PASSED
```

Dashboard: Wave observability in v1.1 is **CLI log output only** (the wave labels shown above). The Streamlit dashboard continues to read from `.kevin/runs/` state files (not from SQLite). Wave-aware dashboard visualization is **future work** — it would require either adding wave metadata to `BlockState` or reading from `knowledge.db`. Neither is in scope for v1.1.

---

## 3. Section 2: Learning Agent — Harvester + Advisor + SQLite

### 3.1 Architecture

```
                    Kevin Run Lifecycle
                    ====================

  ┌── Startup ─────────────────── Execution ──── Teardown ──┐
  │                                                          │
  │  cmd_run()                _execute_blocks_async()        │
  │     │                            │                       │
  │     ▼                            │                       │
  │  advise()──→ variables ──→ prompt rendering               │
  │     ↑            │               │                       │
  │     │            ▼               ▼                       │
  │   SQLite    create_run()    complete_run()                │
  │     ↑                            │                       │
  │     │                            ▼                       │
  │     └──────────────── harvest_run() ──→ SQLite           │
  │                                                          │
  │              .kevin/knowledge.db                         │
  └──────────────────────────────────────────────────────────┘
```

### 3.2 File Structure

```
kevin/
├── learning/
│   ├── __init__.py          -- exports advise, harvest_run, harvest_all
│   ├── db.py                -- SQLite schema, connection, read/write ops (~100 lines)
│   ├── harvester.py         -- Post-run knowledge extraction (~150 lines)
│   └── advisor.py           -- Pre-run context generation (~120 lines)
├── utils.py                 -- Shared resolve_cwd, extract_keywords (~30 lines)
└── ...
```

### 3.3 SQLite Schema (`db.py`)

Database location: `.kevin/knowledge.db` (managed by `KevinConfig.knowledge_db` property)

```sql
-- Table 1: Structured run summaries (statistics)
CREATE TABLE IF NOT EXISTS run_history (
    run_id          TEXT PRIMARY KEY,
    blueprint_id    TEXT NOT NULL,
    issue_number    INTEGER,
    issue_title     TEXT,
    repo            TEXT,
    status          TEXT NOT NULL,           -- completed | failed
    total_blocks    INTEGER,
    passed_blocks   INTEGER,
    failed_block_id TEXT,                     -- first failed Block (NULL if all passed)
    failure_reason  TEXT,                     -- stderr first 500 chars
    elapsed_seconds REAL,                     -- computed from created_at / completed_at
    created_at      TEXT,
    variables_json  TEXT                      -- whitelisted fields only (see 3.8)
);

-- Table 2: Block-level execution records (failure analysis)
CREATE TABLE IF NOT EXISTS block_history (
    run_id          TEXT NOT NULL,
    block_id        TEXT NOT NULL,
    blueprint_id    TEXT NOT NULL,            -- denormalized for query simplicity
    block_name      TEXT,
    runner          TEXT,
    status          TEXT NOT NULL,            -- passed | failed
    exit_code       INTEGER,
    retries         INTEGER DEFAULT 0,
    elapsed_seconds REAL,
    error           TEXT,
    validator_json  TEXT,
    PRIMARY KEY (run_id, block_id)
);

-- Table 3: Full-text search on issue text + block output (context injection)
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
```

**Why three tables**:
- `run_history` → Advisor statistics ("this Blueprint succeeds 85% of the time")
- `block_history` → failure pattern analysis ("B2 fails due to test coverage 3 times")
- `block_logs_fts` → similar-issue search ("find successful runs with similar Issue text")

**No `content=''`** — first version stores data inline in FTS table for simplicity and debuggability. Optimization deferred until data volume justifies it.

### 3.4 Harvester (`harvester.py`)

**Trigger**: Called after `complete_run()` in ALL command paths that finalize a run, wrapped in `try/except` (see constraint C1).

The harvest call is placed inside `_execute_blocks_async()` itself, immediately after `state_mgr.complete_run()`, NOT in individual command functions. This ensures knowledge is captured regardless of entry point:
- `cmd_run()` — full run
- `cmd_resume()` — resumed run reaching completion
- `cmd_run_block()` — single block re-run (harvests the updated run state)

```python
def harvest_run(db_path: Path, state_dir: Path, run_id: str) -> None:
    """Extract knowledge from .kevin/runs/{run_id}/ into SQLite.

    Idempotent: same run_id can be harvested multiple times via upsert.
    FTS rows are deleted-then-inserted to prevent duplicates.
    """

def harvest_all(db_path: Path, state_dir: Path) -> HarvestResult:
    """Batch-harvest all historical runs. For initialization or data repair.

    Returns:
        HarvestResult(harvested=N, skipped_existing=N, failed_parse=N)
    """

@dataclass(frozen=True)
class HarvestResult:
    harvested: int
    skipped_existing: int
    failed_parse: int
```

**Key behaviors**:
- **Idempotent**: `INSERT OR REPLACE` for `run_history`/`block_history`; `DELETE + INSERT` for FTS rows on same `(run_id, block_id)`
- **Final-attempt-only indexing**: For FTS, only index the final attempt log per Block (see constraint C3)
- **Fault-tolerant**: `harvest_all()` skips unparseable runs, counts them in `failed_parse`
- **Whitelist serialization**: `variables_json` only contains safe fields (see 3.8)
- **issue_title source**: `RunState.variables` contains `issue_title` (set by `_build_variables()`). Harvester reads it from `variables_json` or the whitelisted variables dict. No additional data source needed.

### 3.5 Final Attempt Log Selection

Block log files follow the naming convention:
- `B2.log` — first attempt (attempt 0)
- `B2.attempt-1.log` — retry 1
- `B2.attempt-2.log` — retry 2

**Selection algorithm** (NOT string sort — explicit attempt parsing):

```python
def _find_final_log(logs_dir: Path, block_id: str) -> Path | None:
    """Find the log file for the final attempt of a block.

    Parses attempt numbers explicitly. Does NOT rely on lexicographic sort.
    - 'B2.log' → attempt 0
    - 'B2.attempt-3.log' → attempt 3
    Returns the highest attempt number's log file.
    """
    max_attempt = -1
    best = None
    for f in logs_dir.glob(f"{block_id}*.log"):
        attempt = _parse_attempt_number(f.name, block_id)
        if attempt > max_attempt:
            max_attempt = attempt
            best = f
    return best
```

### 3.6 Advisor (`advisor.py`)

**Trigger**: Called in `cmd_run()` after intent classification, before `create_run()`.

```python
@dataclass(frozen=True)
class FailurePattern:
    block_id: str
    reason: str
    count: int

@dataclass(frozen=True)
class SimilarSnippet:
    run_id: str
    issue_title: str
    output_summary: str       # truncated to 300 chars

@dataclass(frozen=True)
class LearningContext:
    """Structured learning context (machine-readable)."""
    success_rate: float | None     # 0.0~1.0, None = no data
    total_runs: int
    common_failures: list[FailurePattern]
    similar_snippets: list[SimilarSnippet]
    risk_warnings: list[str]


def advise(
    db_path: Path,
    blueprint_id: str,
    issue_title: str,
    issue_body: str,
) -> LearningContext:
    """Query SQLite, generate historical context for current run.

    Silent degradation: returns empty LearningContext on any error.
    """
```

### 3.7 Similar-Issue Search Strategy

Two-step retrieval — search by Issue text, not by prompt template:

```python
def _search_similar_runs(db, blueprint_id, issue_title, issue_body):
    """
    Step 1: Extract keywords from issue_title
    Step 2: FTS5 MATCH against issue_title + issue_body columns
            Filter: status='passed' AND blueprint_id matches
    Step 3: Return top results with output_summary snippets
    """
    keywords = _extract_keywords(issue_title)

    cursor = db.execute("""
        SELECT run_id, block_id, issue_title, output_summary, rank
        FROM block_logs_fts
        WHERE block_logs_fts MATCH ?
          AND status = 'passed'
          AND blueprint_id = ?
        ORDER BY rank
        LIMIT 5
    """, (f"issue_title:{keywords} OR issue_body:{keywords}", blueprint_id))

    return [_build_snippet(row) for row in cursor.fetchall()]
```

**Semantic**: Find runs with similar TASKS (via Issue text), then extract their successful outputs as experience. NOT "find similar prompts" (which would match templates, not tasks).

### 3.8 Variables Whitelist

```python
VARIABLES_WHITELIST = frozenset({
    "issue_number", "issue_title", "issue_labels",
    "repo_full", "owner", "repo",
})

def _safe_variables_json(variables: dict[str, str]) -> str:
    """Serialize only whitelisted variable keys. Prevents sensitive data leakage."""
    return json.dumps({k: v for k, v in variables.items() if k in VARIABLES_WHITELIST})
```

Excluded: `issue_body` (may contain large text), `target_repo` (local path), any future token/secret fields.

### 3.9 Context Rendering

Rendering is a separate function from the structured `LearningContext`:

```python
def format_learning_context(ctx: LearningContext, *, max_chars: int = 1200) -> str:
    """Render structured context into plain-text prompt injection.

    Hard limits:
    - Stats: max 1 line
    - Failure patterns: max 2 entries
    - Similar snippets: max 2 entries, each truncated to 300 chars
    - Total output: hard-truncated to max_chars

    Output is plain ASCII text. No emoji, no unicode symbols.
    """
    sections: list[str] = []

    if ctx.success_rate is not None:
        pct = f"{ctx.success_rate:.0%}"
        sections.append(
            f"[History] This Blueprint: {pct} success rate ({ctx.total_runs} runs)"
        )

    for fp in ctx.common_failures[:2]:
        sections.append(
            f"[Warning] {fp.block_id} common failure: {fp.reason} ({fp.count}x)"
        )

    for sn in ctx.similar_snippets[:2]:
        truncated = sn.output_summary[:300]
        sections.append(
            f"[Reference] Similar issue '{sn.issue_title}': {truncated}"
        )

    for w in ctx.risk_warnings[:2]:
        sections.append(f"[Risk] {w}")

    result = "\n".join(sections)
    return result[:max_chars]
```

### 3.10 Integration into `cli.py`

**Advisor call** — in `cmd_run()`, after classify(), before create_run():

```python
# cmd_run() — pre-run context injection
from kevin.learning import advise
from kevin.learning.advisor import format_learning_context

ctx = advise(config.knowledge_db, intent.blueprint_id, issue.title, issue.body)
variables["learning_context"] = format_learning_context(ctx)
```

**Harvester call** — in `_execute_blocks_async()`, after complete_run():

```python
# _execute_blocks_async() — post-run knowledge capture
# This is inside the shared execution path, NOT in cmd_run/cmd_resume/cmd_run_block.
# All three commands flow through _execute_blocks_async() → all runs get harvested.
state_mgr.complete_run(run, final_status)

try:
    from kevin.learning import harvest_run
    harvest_run(config.knowledge_db, config.state_dir, run.run_id)
except Exception:
    pass  # Learning never blocks main execution path (constraint C1)
```

### 3.11 Prompt Template Integration

Blueprint YAML can optionally reference `{{learning_context}}`:

```yaml
prompt_template: |
  You are implementing a coding task.

  {{learning_context}}

  ## Issue #{{issue_number}}: {{issue_title}}
  ...
```

If `{{learning_context}}` is absent from the template, the variable exists but is not rendered. `prompt_template.py`'s `render()` silently skips unknown variables. **Full backward compatibility**.

### 3.12 Knowledge DB Location

```python
# kevin/config.py — new property
@property
def knowledge_db(self) -> Path:
    return self.target_repo / ".kevin" / "knowledge.db"
```

### 3.13 Elapsed Seconds Prerequisite

`elapsed_seconds` in `run_history` and `block_history` requires timestamps.

- `RunState.created_at` / `completed_at` already exist → `run_history.elapsed_seconds` computable
- `BlockState.started_at` / `completed_at` are defined in the dataclass but NOT currently populated in `_execute_blocks()`

**Prerequisite fix** (2-line change in `cli.py`):

```python
bs = BlockState(block_id=block.block_id, status="running", runner=block.runner)
bs.started_at = _now()  # ← add this

# ... after block completes ...
bs.completed_at = _now()  # ← add this
```

This is a bug fix for existing functionality (timestamps always should have been set), not an architectural change.

---

## 4. Implementation Constraints

These constraints are non-negotiable for v1.1 implementation.

### C1: Advisor must silently degrade

`advise()` must return an empty `LearningContext` (all fields zero/empty) when:
- `knowledge.db` does not exist
- SQLite tables do not exist
- SQLite connection fails
- FTS5 is unavailable
- Any query throws an exception

Learning NEVER blocks or fails the main `kevin run` execution path.

### C2: Harvester must only process final run state

`harvest_run()` is called AFTER `complete_run()`. It must not be called during execution. The caller (`cmd_run()`) ensures this ordering. `harvest_run()` itself must also verify `run.status in ("completed", "failed")` and skip otherwise.

### C3: Final attempt selection must parse explicitly

Do NOT select the final attempt log by lexicographic file name sort. Parse the attempt number:
- `B2.log` → attempt 0
- `B2.attempt-1.log` → attempt 1
- `B2.attempt-10.log` → attempt 10

`B2.attempt-10.log` must sort AFTER `B2.attempt-2.log`. String sort would get this wrong.

### C4: Elapsed seconds source

- `run_history.elapsed_seconds` — computed from `RunState.created_at` and `RunState.completed_at`
- `block_history.elapsed_seconds` — computed from `BlockState.started_at` and `BlockState.completed_at`
- Prerequisite: populate `BlockState.started_at` / `completed_at` in `_execute_blocks_async()` (see Section 3.13)
- If timestamps are missing or unparseable, store `NULL`

### C5: format_learning_context() outputs plain ASCII

No emoji, no unicode symbols (no `⚠️`). First version uses plain-text markers: `[History]`, `[Warning]`, `[Reference]`, `[Risk]`. This avoids encoding issues in prompt environments.

### C6: FTS idempotency via delete-then-insert

When harvesting a `(run_id, block_id)` pair that already exists in `block_logs_fts`:
1. `DELETE FROM block_logs_fts WHERE run_id = ? AND block_id = ?`
2. `INSERT INTO block_logs_fts (...) VALUES (...)`

This prevents duplicate FTS rows on re-harvest. The two operations are wrapped in a single transaction.

---

## 5. File Change Summary

### New Files

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `kevin/scheduler.py` | ~80 | Wave computation with cwd conflict resolution |
| `kevin/learning/__init__.py` | ~10 | Public exports |
| `kevin/learning/db.py` | ~100 | SQLite schema, connection, CRUD |
| `kevin/learning/harvester.py` | ~150 | Post-run knowledge extraction |
| `kevin/learning/advisor.py` | ~120 | Pre-run context query + rendering |
| `kevin/utils.py` | ~30 | Shared `resolve_cwd`, `extract_keywords` |

### Modified Files

| File | Change | Lines (est.) |
|------|--------|-------------|
| `kevin/cli.py` | `_execute_blocks` → async wave dispatch; advisor/harvester calls in `cmd_run()` | ~60 |
| `kevin/agent_runner.py` | Add `run_block_async()`; extract `_resolve_cwd` to `utils.py` | ~20 |
| `kevin/config.py` | Add `knowledge_db` property | ~5 |

### Unchanged Files

| File | Reason |
|------|--------|
| `kevin/state.py` | State updates remain in event loop thread — no concurrency risk |
| `kevin/blueprint_loader.py` | Topo sort and Block dataclass already sufficient |
| `kevin/prompt_template.py` | Unknown variables already silently preserved |
| `kevin/github_client.py` | No changes needed |
| `kevin/intent.py` | No changes needed |
| All Blueprint YAML files | Parallelism derived from existing `dependencies` field |

**Total new code**: ~490 lines
**Total modified code**: ~85 lines

---

## 6. Test Plan

### 6.1 Scheduler Tests (`test_scheduler.py`)

| Test | Description |
|------|-------------|
| `test_linear_chain_produces_one_block_per_wave` | B1→B2→B3 → 3 waves, 1 block each |
| `test_diamond_graph_produces_parallel_wave` | B1→(B2,B3)→B4 → wave 2 has 2 blocks |
| `test_cwd_conflict_splits_sub_wave` | B2(cwd=/app), B3(cwd=/app) in same level → split to 2.1, 2.2 |
| `test_different_cwd_allows_parallel` | B2(cwd=/app), B3(cwd=/infra) → same sub-wave |
| `test_cwd_resolution_uses_variables` | `{{target_repo}}` resolved before comparison |
| `test_no_dependencies_all_in_wave_1` | [B1, B2, B3] no deps → single wave (with cwd check) |
| `test_wave_label_format` | Verify `Wave 1.1`, `Wave 3.2` label format |

### 6.2 Async Execution Tests (`test_async_execution.py`)

| Test | Description |
|------|-------------|
| `test_parallel_blocks_run_concurrently` | Two shell blocks with different cwd — elapsed time < sum of individual times |
| `test_serial_fallback_for_linear_blueprint` | B1→B2→B3 — behavior identical to current serial execution |
| `test_wave_failure_finishes_current_wave` | One block fails in wave — other blocks in same wave still complete |
| `test_wave_failure_stops_subsequent_waves` | After wave failure, next wave is NOT scheduled |
| `test_state_updates_after_parallel_blocks` | All BlockStates correctly written after parallel execution |
| `test_dry_run_with_parallel_blocks` | Dry run works with wave scheduler |

### 6.3 Learning DB Tests (`test_learning_db.py`)

| Test | Description |
|------|-------------|
| `test_schema_creation_on_first_connect` | Tables + FTS created automatically |
| `test_harvest_run_inserts_records` | run_history + block_history populated |
| `test_harvest_run_idempotent` | Same run_id harvested twice — no duplicates |
| `test_fts_idempotent_delete_then_insert` | Re-harvest same block — FTS has exactly 1 row |
| `test_harvest_all_skips_broken_runs` | Unparseable run directory counted in `failed_parse` |
| `test_variables_whitelist` | Only safe fields serialized to `variables_json` |

### 6.4 Harvester Tests (`test_harvester.py`)

| Test | Description |
|------|-------------|
| `test_final_attempt_selection` | B2.log + B2.attempt-1.log + B2.attempt-10.log → selects attempt-10 |
| `test_final_attempt_no_retries` | Only B2.log exists → selects it (attempt 0) |
| `test_elapsed_seconds_computed` | Timestamps → correct elapsed_seconds |
| `test_elapsed_seconds_null_on_missing_timestamp` | Missing completed_at → NULL |
| `test_only_completed_runs_harvested` | Running status → skipped |

### 6.5 Advisor Tests (`test_advisor.py`)

| Test | Description |
|------|-------------|
| `test_advise_empty_db_returns_empty_context` | No data → all fields empty, no error |
| `test_advise_no_db_file_returns_empty_context` | knowledge.db doesn't exist → silent degradation |
| `test_blueprint_stats_correct` | 3 completed + 1 failed → 75% success rate |
| `test_common_failures_grouped` | Multiple B2 failures with same pattern → aggregated |
| `test_similar_search_uses_issue_text_not_prompt` | FTS matches on issue_title, not template text |
| `test_format_plain_ascii` | Output contains no emoji, no unicode symbols |
| `test_format_max_chars_enforced` | Output truncated to max_chars |
| `test_format_empty_context_returns_empty_string` | No data → empty string (not "No data available") |

---

> **Spec End**
>
> This document is frozen. Implementation proceeds via a separate plan.
> Related: [Gap Analysis](../../kevin-gap-analysis.md) | [EDA Deep Dive](../../eda-event-bus-deep-dive.md)

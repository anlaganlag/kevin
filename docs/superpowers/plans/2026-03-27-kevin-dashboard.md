# Kevin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit dashboard that reads Kevin's `.kevin/runs/` state files and `blueprints/` YAMLs to visualize run status, block pipelines, and blueprint structure.

**Architecture:** Thin read-only Streamlit app with a `data_loader` module that reuses Kevin's existing `state.py` and `blueprint_loader.py`. Three pages (run list, run detail, blueprint viewer) as separate component files. A seed script generates sample data for demos without real Kevin runs.

**Tech Stack:** Python 3.11+, Streamlit, PyYAML (existing), streamlit-mermaid, Plotly

---

## File Structure

```
kevin/dashboard/
├── __init__.py            # Package marker
├── app.py                 # Streamlit entry point + sidebar navigation
├── data_loader.py         # Read-only data access (reuses kevin.state, kevin.blueprint_loader)
├── seed.py                # Generate sample .kevin/runs/ data for demo
├── components/
│   ├── __init__.py        # Package marker
│   ├── run_list.py        # Page 1: Run list with metric cards + table
│   ├── run_detail.py      # Page 2: Run detail with Mermaid pipeline + Gantt + logs
│   └── blueprint_view.py  # Page 3: Blueprint viewer with dependency graph
└── requirements.txt       # Dashboard-specific dependencies
```

---

### Task 1: Project Scaffolding + Dependencies

**Files:**
- Create: `kevin/dashboard/__init__.py`
- Create: `kevin/dashboard/components/__init__.py`
- Create: `kevin/dashboard/requirements.txt`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p kevin/dashboard/components
```

- [ ] **Step 2: Create `kevin/dashboard/__init__.py`**

```python
"""Kevin Dashboard — Streamlit visualization for Kevin runs."""
```

- [ ] **Step 3: Create `kevin/dashboard/components/__init__.py`**

```python
"""Dashboard page components."""
```

- [ ] **Step 4: Create `kevin/dashboard/requirements.txt`**

```
streamlit>=1.30.0
pyyaml>=6.0
streamlit-mermaid>=0.2.0
plotly>=5.18.0
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r kevin/dashboard/requirements.txt
```

- [ ] **Step 6: Commit**

```bash
git add kevin/dashboard/__init__.py kevin/dashboard/components/__init__.py kevin/dashboard/requirements.txt
git commit -m "chore: scaffold kevin dashboard package"
```

---

### Task 2: Data Loader

**Files:**
- Create: `kevin/dashboard/data_loader.py`
- Test: `kevin/tests/test_data_loader.py`

The data loader wraps Kevin's existing `StateManager` and `blueprint_loader` with dashboard-friendly frozen dataclasses.

- [ ] **Step 1: Write failing tests for `list_runs`**

```python
"""Tests for kevin.dashboard.data_loader."""

from pathlib import Path

import pytest
import yaml

from kevin.dashboard.data_loader import (
    BlockInfo,
    BlueprintInfo,
    RunSummary,
    list_blueprints,
    list_runs,
    load_block_log,
    load_blueprint,
    load_run,
)


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    """Create a minimal .kevin/runs/ structure."""
    run_id = "20260327-120000-abc123"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)

    run_data = {
        "run_id": run_id,
        "blueprint_id": "bp_coding_task.1.0.0",
        "issue_number": 42,
        "repo": "owner/repo",
        "status": "completed",
        "created_at": "2026-03-27T12:00:00+00:00",
        "completed_at": "2026-03-27T12:05:00+00:00",
        "variables": {"issue_title": "Add feature X"},
        "blocks": {
            "B1": {
                "block_id": "B1",
                "status": "passed",
                "runner": "claude_cli",
                "started_at": "2026-03-27T12:00:10+00:00",
                "completed_at": "2026-03-27T12:01:00+00:00",
                "exit_code": 0,
                "output_summary": "Analysis done",
                "validator_results": [{"type": "file_exists", "passed": True}],
                "retries": 0,
                "error": "",
            },
            "B2": {
                "block_id": "B2",
                "status": "passed",
                "runner": "claude_cli",
                "started_at": "2026-03-27T12:01:05+00:00",
                "completed_at": "2026-03-27T12:04:00+00:00",
                "exit_code": 0,
                "output_summary": "Implemented",
                "validator_results": [{"type": "git_diff_check", "passed": True}],
                "retries": 1,
                "error": "",
            },
        },
    }
    with (run_dir / "run.yaml").open("w") as f:
        yaml.safe_dump(run_data, f)

    # Block log
    logs_dir = run_dir / "logs"
    logs_dir.mkdir()
    (logs_dir / "B1.log").write_text("=== PROMPT ===\nAnalyze\n\n=== STDOUT ===\nDone")

    return tmp_path


class TestListRuns:
    def test_should_return_run_summaries(self, state_dir: Path) -> None:
        runs = list_runs(state_dir)
        assert len(runs) == 1
        run = runs[0]
        assert run.run_id == "20260327-120000-abc123"
        assert run.blueprint_id == "bp_coding_task.1.0.0"
        assert run.issue_number == 42
        assert run.status == "completed"
        assert run.blocks_total == 2
        assert run.blocks_passed == 2

    def test_should_return_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        runs = list_runs(tmp_path / "nonexistent")
        assert runs == []


class TestLoadRun:
    def test_should_return_run_with_blocks(self, state_dir: Path) -> None:
        detail = load_run(state_dir, "20260327-120000-abc123")
        assert detail.run_id == "20260327-120000-abc123"
        assert len(detail.blocks) == 2
        b1 = detail.blocks[0]
        assert b1.block_id == "B1"
        assert b1.status == "passed"
        assert b1.runner == "claude_cli"
        assert b1.exit_code == 0

    def test_should_sort_blocks_by_id(self, state_dir: Path) -> None:
        detail = load_run(state_dir, "20260327-120000-abc123")
        ids = [b.block_id for b in detail.blocks]
        assert ids == sorted(ids)


class TestLoadBlockLog:
    def test_should_return_log_content(self, state_dir: Path) -> None:
        log = load_block_log(state_dir, "20260327-120000-abc123", "B1")
        assert "=== PROMPT ===" in log
        assert "Analyze" in log

    def test_should_return_empty_for_missing_log(self, state_dir: Path) -> None:
        log = load_block_log(state_dir, "20260327-120000-abc123", "B99")
        assert log == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest kevin/tests/test_data_loader.py -v
```

Expected: `ModuleNotFoundError: No module named 'kevin.dashboard.data_loader'`

- [ ] **Step 3: Implement `data_loader.py`**

```python
"""Read-only data access for the Kevin Dashboard.

Reads .kevin/runs/ state files and blueprints/ YAML without writing anything.
Reuses kevin.state and kevin.blueprint_loader internally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from kevin import blueprint_loader as bl


@dataclass(frozen=True)
class RunSummary:
    """Lightweight summary for the run list view."""

    run_id: str
    blueprint_id: str
    issue_number: int
    repo: str
    status: str
    blocks_passed: int
    blocks_total: int
    started_at: str
    elapsed_seconds: float | None


@dataclass(frozen=True)
class BlockInfo:
    """Block execution detail for the run detail view."""

    block_id: str
    name: str
    status: str
    runner: str
    exit_code: int | None
    retries: int
    started_at: str
    completed_at: str
    validator_results: list[dict[str, Any]]
    error: str


@dataclass(frozen=True)
class RunDetail:
    """Full run data including all blocks."""

    run_id: str
    blueprint_id: str
    issue_number: int
    repo: str
    status: str
    created_at: str
    completed_at: str
    variables: dict[str, str]
    blocks: list[BlockInfo]


@dataclass(frozen=True)
class BlueprintInfo:
    """Blueprint metadata + block list for the blueprint viewer."""

    blueprint_id: str
    blueprint_name: str
    version: str
    tags: list[str]
    block_count: int
    blocks: list[BlueprintBlockInfo]
    raw: dict[str, Any]


@dataclass(frozen=True)
class BlueprintBlockInfo:
    """Block definition within a blueprint."""

    block_id: str
    name: str
    runner: str
    dependencies: list[str]
    timeout: int
    max_retries: int
    validators: list[str]


# ---------------------------------------------------------------------------
# Run data
# ---------------------------------------------------------------------------


def list_runs(state_dir: Path) -> list[RunSummary]:
    """List all runs as summaries, sorted newest-first."""
    if not state_dir.exists():
        return []

    summaries: list[RunSummary] = []
    for run_dir in sorted(state_dir.iterdir(), reverse=True):
        run_file = run_dir / "run.yaml"
        if not run_dir.is_dir() or not run_file.exists():
            continue
        try:
            with run_file.open() as f:
                data = yaml.safe_load(f)
            blocks = data.get("blocks", {})
            passed = sum(1 for b in blocks.values() if b.get("status") == "passed")
            elapsed = _compute_elapsed(data.get("created_at", ""), data.get("completed_at", ""))
            summaries.append(
                RunSummary(
                    run_id=data.get("run_id", run_dir.name),
                    blueprint_id=data.get("blueprint_id", ""),
                    issue_number=int(data.get("issue_number", 0)),
                    repo=data.get("repo", ""),
                    status=data.get("status", "unknown"),
                    blocks_passed=passed,
                    blocks_total=len(blocks),
                    started_at=data.get("created_at", ""),
                    elapsed_seconds=elapsed,
                )
            )
        except Exception:
            continue
    return summaries


def load_run(state_dir: Path, run_id: str) -> RunDetail:
    """Load full run detail including all blocks."""
    run_file = state_dir / run_id / "run.yaml"
    with run_file.open() as f:
        data = yaml.safe_load(f)

    blocks_raw = data.get("blocks", {})
    blocks = sorted(
        [
            BlockInfo(
                block_id=b.get("block_id", bid),
                name=b.get("name", bid),
                status=b.get("status", "unknown"),
                runner=b.get("runner", ""),
                exit_code=b.get("exit_code"),
                retries=int(b.get("retries", 0)),
                started_at=b.get("started_at", ""),
                completed_at=b.get("completed_at", ""),
                validator_results=b.get("validator_results", []),
                error=b.get("error", ""),
            )
            for bid, b in blocks_raw.items()
        ],
        key=lambda x: x.block_id,
    )

    return RunDetail(
        run_id=data.get("run_id", run_id),
        blueprint_id=data.get("blueprint_id", ""),
        issue_number=int(data.get("issue_number", 0)),
        repo=data.get("repo", ""),
        status=data.get("status", "unknown"),
        created_at=data.get("created_at", ""),
        completed_at=data.get("completed_at", ""),
        variables=data.get("variables", {}),
        blocks=blocks,
    )


def load_block_log(state_dir: Path, run_id: str, block_id: str) -> str:
    """Load raw log content for a specific block."""
    log_path = state_dir / run_id / "logs" / f"{block_id}.log"
    if not log_path.exists():
        return ""
    return log_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Blueprint data
# ---------------------------------------------------------------------------


def list_blueprints(blueprints_dir: Path) -> list[BlueprintInfo]:
    """List all blueprints in the directory."""
    if not blueprints_dir.exists():
        return []

    results: list[BlueprintInfo] = []
    for bp_file in sorted(blueprints_dir.glob("bp_*.yaml")):
        try:
            bp = bl.load(bp_file)
            metadata = bp.raw.get("metadata", {})
            blocks = [
                BlueprintBlockInfo(
                    block_id=b.block_id,
                    name=b.name,
                    runner=b.runner,
                    dependencies=list(b.dependencies),
                    timeout=b.timeout,
                    max_retries=b.max_retries,
                    validators=[v.type for v in b.validators],
                )
                for b in bp.blocks
            ]
            results.append(
                BlueprintInfo(
                    blueprint_id=bp.blueprint_id,
                    blueprint_name=bp.blueprint_name,
                    version=bp.version,
                    tags=metadata.get("tags", []),
                    block_count=len(bp.blocks),
                    blocks=blocks,
                    raw=bp.raw,
                )
            )
        except Exception:
            continue
    return results


def load_blueprint(blueprints_dir: Path, blueprint_id: str) -> BlueprintInfo:
    """Load a single blueprint by ID."""
    bp_path = bl.find_blueprint(blueprints_dir, blueprint_id)
    bp = bl.load(bp_path)
    metadata = bp.raw.get("metadata", {})
    blocks = [
        BlueprintBlockInfo(
            block_id=b.block_id,
            name=b.name,
            runner=b.runner,
            dependencies=list(b.dependencies),
            timeout=b.timeout,
            max_retries=b.max_retries,
            validators=[v.type for v in b.validators],
        )
        for b in bp.blocks
    ]
    return BlueprintInfo(
        blueprint_id=bp.blueprint_id,
        blueprint_name=bp.blueprint_name,
        version=bp.version,
        tags=metadata.get("tags", []),
        block_count=len(bp.blocks),
        blocks=blocks,
        raw=bp.raw,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_elapsed(started: str, completed: str) -> float | None:
    """Compute elapsed seconds between two ISO timestamps."""
    if not started or not completed:
        return None
    try:
        t_start = datetime.fromisoformat(started)
        t_end = datetime.fromisoformat(completed)
        return (t_end - t_start).total_seconds()
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest kevin/tests/test_data_loader.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Add blueprint tests**

Add to `kevin/tests/test_data_loader.py`:

```python
@pytest.fixture()
def blueprints_dir() -> Path:
    """Use the real blueprints directory."""
    bp_dir = Path(__file__).resolve().parent.parent.parent / "blueprints"
    if not bp_dir.exists():
        pytest.skip("blueprints/ directory not found")
    return bp_dir


class TestListBlueprints:
    def test_should_return_blueprints(self, blueprints_dir: Path) -> None:
        bps = list_blueprints(blueprints_dir)
        assert len(bps) > 0
        bp = bps[0]
        assert bp.blueprint_id != ""
        assert bp.block_count > 0

    def test_should_return_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        bps = list_blueprints(tmp_path / "nonexistent")
        assert bps == []
```

- [ ] **Step 6: Run all tests**

```bash
pytest kevin/tests/test_data_loader.py -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add kevin/dashboard/data_loader.py kevin/tests/test_data_loader.py
git commit -m "feat: add kevin dashboard data loader with tests"
```

---

### Task 3: Seed Script

**Files:**
- Create: `kevin/dashboard/seed.py`

Generates 3 sample runs in `.kevin/runs/` so the dashboard has data to display without running Kevin for real.

- [ ] **Step 1: Implement `seed.py`**

```python
"""Generate sample Kevin run data for dashboard demos.

Usage:
    python -m kevin.dashboard.seed --target-repo .
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kevin.state import BlockState, RunState, StateManager


def _now_offset(minutes: int = 0, seconds: int = 0) -> str:
    base = datetime(2026, 3, 27, 10, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(minutes=minutes, seconds=seconds)).isoformat()


def seed(target_repo: Path) -> None:
    """Generate 3 sample runs."""
    state_dir = target_repo / ".kevin" / "runs"
    mgr = StateManager(state_dir)

    # --- Run 1: Completed successfully ---
    run1 = RunState(
        run_id="20260327-100000-demo01",
        blueprint_id="bp_coding_task.1.0.0",
        issue_number=42,
        repo="centific-cn/demo-app",
        status="completed",
        created_at=_now_offset(0),
        completed_at=_now_offset(5),
        variables={"issue_title": "Add user avatar upload", "issue_number": "42"},
    )
    run1.blocks = {
        "B1": BlockState(
            block_id="B1", status="passed", runner="claude_cli",
            started_at=_now_offset(0, 10), completed_at=_now_offset(1),
            exit_code=0, output_summary="Analysis complete",
            validator_results=[{"type": "file_exists", "passed": True}],
        ),
        "B2": BlockState(
            block_id="B2", status="passed", runner="claude_cli",
            started_at=_now_offset(1, 5), completed_at=_now_offset(4),
            exit_code=0, output_summary="Implementation done",
            validator_results=[
                {"type": "git_diff_check", "passed": True},
                {"type": "command", "passed": True},
            ],
        ),
        "B3": BlockState(
            block_id="B3", status="passed", runner="shell",
            started_at=_now_offset(4, 5), completed_at=_now_offset(5),
            exit_code=0, output_summary="PR #101 created",
            validator_results=[{"type": "command", "passed": True}],
        ),
    }
    _write_run(mgr, run1)
    _write_logs(mgr, run1.run_id, {
        "B1": ("Analyze issue #42: Add user avatar upload", "Created .kevin/analysis.md\nBranch kevin/issue-42 created", ""),
        "B2": ("Implement per .kevin/analysis.md", "Tests written: 4 passed\nCode committed: feat: Add user avatar upload (resolves #42)", ""),
        "B3": ("", "PR #101 created: https://github.com/centific-cn/demo-app/pull/101", ""),
    })

    # --- Run 2: Failed at B2 ---
    run2 = RunState(
        run_id="20260327-110000-demo02",
        blueprint_id="bp_backend_coding_tdd_automation.1.0.0",
        issue_number=55,
        repo="centific-cn/demo-app",
        status="failed",
        created_at=_now_offset(60),
        completed_at=_now_offset(68),
        variables={"issue_title": "Fix payment timeout", "issue_number": "55"},
    )
    run2.blocks = {
        "B1": BlockState(
            block_id="B1", status="passed", runner="claude_cli",
            started_at=_now_offset(60, 10), completed_at=_now_offset(61),
            exit_code=0, output_summary="Analysis complete",
            validator_results=[{"type": "file_exists", "passed": True}],
        ),
        "B2": BlockState(
            block_id="B2", status="failed", runner="claude_cli",
            started_at=_now_offset(61, 5), completed_at=_now_offset(68),
            exit_code=1, output_summary="Tests failed",
            validator_results=[{"type": "git_diff_check", "passed": False}],
            retries=2, error="pytest returned exit code 1: 2 tests failed",
        ),
    }
    _write_run(mgr, run2)
    _write_logs(mgr, run2.run_id, {
        "B1": ("Analyze issue #55", "Analysis written to .kevin/analysis.md", ""),
        "B2": ("Implement fix", "", "FAILED: test_payment_timeout - AssertionError\nFAILED: test_retry_logic - TimeoutError"),
    })

    # --- Run 3: Running (B1 done, B2 in progress) ---
    run3 = RunState(
        run_id="20260327-120000-demo03",
        blueprint_id="bp_coding_task.1.0.0",
        issue_number=63,
        repo="centific-cn/demo-app",
        status="running",
        created_at=_now_offset(120),
        variables={"issue_title": "Add dark mode toggle", "issue_number": "63"},
    )
    run3.blocks = {
        "B1": BlockState(
            block_id="B1", status="passed", runner="claude_cli",
            started_at=_now_offset(120, 10), completed_at=_now_offset(121),
            exit_code=0, output_summary="Analysis complete",
            validator_results=[{"type": "file_exists", "passed": True}],
        ),
        "B2": BlockState(
            block_id="B2", status="running", runner="claude_cli",
            started_at=_now_offset(121, 5),
        ),
        "B3": BlockState(block_id="B3", status="pending", runner="shell"),
    }
    _write_run(mgr, run3)
    _write_logs(mgr, run3.run_id, {
        "B1": ("Analyze issue #63", "Dark mode requirements identified", ""),
    })

    print(f"Seeded 3 demo runs in {state_dir}")


def _write_run(mgr: StateManager, run: RunState) -> None:
    """Persist a run and all its blocks."""
    run_dir = mgr._state_dir / run.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    mgr._save_run(run)
    for block_state in run.blocks.values():
        mgr._save_block(run.run_id, block_state)


def _write_logs(
    mgr: StateManager,
    run_id: str,
    logs: dict[str, tuple[str, str, str]],
) -> None:
    """Write prompt/stdout/stderr logs for each block."""
    for block_id, (prompt, stdout, stderr) in logs.items():
        mgr.save_block_logs(run_id, block_id, prompt=prompt, stdout=stdout, stderr=stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Seed Kevin demo data")
    parser.add_argument("--target-repo", default=".", help="Target repo path")
    args = parser.parse_args(argv)
    seed(Path(args.target_repo).resolve())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test seed script runs**

```bash
python -m kevin.dashboard.seed --target-repo /tmp/kevin-demo-test
ls /tmp/kevin-demo-test/.kevin/runs/
```

Expected: 3 directories listed (20260327-100000-demo01, 20260327-110000-demo02, 20260327-120000-demo03)

- [ ] **Step 3: Commit**

```bash
git add kevin/dashboard/seed.py
git commit -m "feat: add seed script for demo run data"
```

---

### Task 4: Streamlit App Entry Point

**Files:**
- Create: `kevin/dashboard/app.py`

- [ ] **Step 1: Implement `app.py`**

```python
"""Kevin Dashboard — Streamlit entry point.

Usage:
    streamlit run kevin/dashboard/app.py -- --kevin-root . --blueprints-dir blueprints
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import streamlit as st


def parse_args() -> argparse.Namespace:
    """Parse CLI args passed after `--`."""
    parser = argparse.ArgumentParser(description="Kevin Dashboard")
    parser.add_argument("--kevin-root", default=".", help="Project root with .kevin/runs/")
    parser.add_argument("--blueprints-dir", default="blueprints", help="Blueprints directory")
    # Streamlit passes extra args; ignore them
    args, _ = parser.parse_known_args(sys.argv[1:])
    return args


def main() -> None:
    args = parse_args()
    kevin_root = Path(args.kevin_root).resolve()
    blueprints_dir = Path(args.blueprints_dir).resolve()
    state_dir = kevin_root / ".kevin" / "runs"

    st.set_page_config(
        page_title="Kevin Dashboard",
        page_icon=":robot_face:",
        layout="wide",
    )

    # Store paths in session state for components
    st.session_state["state_dir"] = state_dir
    st.session_state["blueprints_dir"] = blueprints_dir

    st.sidebar.title("Kevin Dashboard")
    page = st.sidebar.radio(
        "Navigation",
        ["Run List", "Run Detail", "Blueprints"],
        label_visibility="collapsed",
    )

    if not state_dir.exists():
        st.sidebar.warning(
            f"No runs found at `{state_dir}`.\n\n"
            "Run `python -m kevin.dashboard.seed` to generate demo data."
        )

    if page == "Run List":
        from kevin.dashboard.components.run_list import render
        render(state_dir)
    elif page == "Run Detail":
        from kevin.dashboard.components.run_detail import render
        render(state_dir)
    elif page == "Blueprints":
        from kevin.dashboard.components.blueprint_view import render
        render(blueprints_dir)


if __name__ == "__main__":
    main()


main()
```

- [ ] **Step 2: Commit**

```bash
git add kevin/dashboard/app.py
git commit -m "feat: add streamlit app entry point with navigation"
```

---

### Task 5: Page 1 — Run List

**Files:**
- Create: `kevin/dashboard/components/run_list.py`

- [ ] **Step 1: Implement run list page**

```python
"""Page 1: Run list with summary metrics and clickable table."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from kevin.dashboard.data_loader import list_runs


STATUS_ICONS = {
    "completed": ":white_check_mark:",
    "failed": ":x:",
    "running": ":arrows_counterclockwise:",
    "pending": ":hourglass_flowing_sand:",
}


def render(state_dir: Path) -> None:
    st.header("Kevin Runs")

    runs = list_runs(state_dir)
    if not runs:
        st.info("No runs found. Run `python -m kevin.dashboard.seed` to generate demo data.")
        return

    # Metric cards
    total = len(runs)
    passed = sum(1 for r in runs if r.status == "completed")
    failed = sum(1 for r in runs if r.status == "failed")
    running = sum(1 for r in runs if r.status == "running")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Runs", total)
    col2.metric("Completed", passed)
    col3.metric("Failed", failed)
    col4.metric("Running", running)

    st.divider()

    # Run table
    for run in runs:
        status_icon = STATUS_ICONS.get(run.status, ":question:")
        elapsed = f"{run.elapsed_seconds:.0f}s" if run.elapsed_seconds is not None else "—"
        progress = f"{run.blocks_passed}/{run.blocks_total}"

        col_id, col_bp, col_issue, col_status, col_progress, col_time, col_elapsed = st.columns(
            [2, 3, 1, 1, 1, 2, 1]
        )
        col_id.code(run.run_id, language=None)
        col_bp.write(run.blueprint_id)
        col_issue.write(f"#{run.issue_number}")
        col_status.write(status_icon)
        col_progress.write(progress)
        col_time.write(run.started_at[:19] if run.started_at else "—")
        col_elapsed.write(elapsed)

        if col_id.button("View", key=f"view_{run.run_id}"):
            st.session_state["selected_run_id"] = run.run_id
            st.session_state["_page"] = "Run Detail"
            st.rerun()
```

- [ ] **Step 2: Commit**

```bash
git add kevin/dashboard/components/run_list.py
git commit -m "feat: add run list page with metrics and table"
```

---

### Task 6: Page 2 — Run Detail

**Files:**
- Create: `kevin/dashboard/components/run_detail.py`

- [ ] **Step 1: Implement run detail page**

```python
"""Page 2: Run detail with Mermaid pipeline, Gantt chart, and logs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import plotly.figure_factory as ff
import streamlit as st
from streamlit_mermaid import st_mermaid

from kevin.dashboard.data_loader import BlockInfo, load_block_log, load_run, list_runs


STATUS_COLORS = {
    "passed": "#28a745",
    "failed": "#dc3545",
    "running": "#007bff",
    "pending": "#6c757d",
}

STATUS_MERMAID_CLASS = {
    "passed": "passed",
    "failed": "failed",
    "running": "running",
    "pending": "pending",
}


def render(state_dir: Path) -> None:
    st.header("Run Detail")

    # Run selector
    runs = list_runs(state_dir)
    if not runs:
        st.info("No runs found.")
        return

    run_ids = [r.run_id for r in runs]
    default_idx = 0
    if "selected_run_id" in st.session_state and st.session_state["selected_run_id"] in run_ids:
        default_idx = run_ids.index(st.session_state["selected_run_id"])

    selected_id = st.selectbox("Select Run", run_ids, index=default_idx)
    if not selected_id:
        return

    detail = load_run(state_dir, selected_id)

    # Metadata
    meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
    meta_col1.metric("Blueprint", detail.blueprint_id)
    meta_col2.metric("Issue", f"#{detail.issue_number}")
    meta_col3.metric("Repo", detail.repo)
    meta_col4.metric("Status", detail.status)

    st.divider()

    # Mermaid pipeline
    st.subheader("Block Pipeline")
    mermaid_code = _build_mermaid(detail.blocks)
    st_mermaid(mermaid_code, height=200)

    # Gantt chart
    gantt_data = _build_gantt_data(detail.blocks)
    if gantt_data:
        st.subheader("Execution Timeline")
        fig = ff.create_gantt(
            gantt_data,
            colors={s: c for s, c in STATUS_COLORS.items()},
            index_col="Status",
            show_colorbar=True,
            showgrid_x=True,
            showgrid_y=True,
        )
        fig.update_layout(height=250, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

    # Block details
    st.subheader("Block Details")
    for block in detail.blocks:
        status_emoji = {"passed": "✅", "failed": "❌", "running": "🔄", "pending": "⏳"}.get(
            block.status, "❓"
        )
        with st.expander(f"{status_emoji} {block.block_id}: {block.name} — {block.status}"):
            info_col1, info_col2, info_col3, info_col4 = st.columns(4)
            info_col1.write(f"**Runner:** `{block.runner}`")
            info_col2.write(f"**Exit Code:** `{block.exit_code}`")
            info_col3.write(f"**Retries:** {block.retries}")
            info_col4.write(f"**Error:** {block.error or '—'}")

            if block.validator_results:
                st.write("**Validators:**")
                for v in block.validator_results:
                    v_icon = "✅" if v.get("passed") else "❌"
                    st.write(f"  {v_icon} `{v.get('type', 'unknown')}`")

            # Logs
            log_content = load_block_log(state_dir, selected_id, block.block_id)
            if log_content:
                st.code(log_content, language="text")


def _build_mermaid(blocks: list[BlockInfo]) -> str:
    """Build a Mermaid flowchart from blocks."""
    lines = ["graph LR"]
    for block in blocks:
        cls = STATUS_MERMAID_CLASS.get(block.status, "pending")
        label = f"{block.block_id}: {block.name}"
        lines.append(f'    {block.block_id}["{label}"]:::{cls}')

    # Edges: sequential chain based on order
    for i in range(len(blocks) - 1):
        lines.append(f"    {blocks[i].block_id} --> {blocks[i + 1].block_id}")

    # Class definitions
    lines.append("    classDef passed fill:#28a745,stroke:#1e7e34,color:white")
    lines.append("    classDef failed fill:#dc3545,stroke:#bd2130,color:white")
    lines.append("    classDef running fill:#007bff,stroke:#0069d9,color:white")
    lines.append("    classDef pending fill:#6c757d,stroke:#5a6268,color:white")
    return "\n".join(lines)


def _build_gantt_data(blocks: list[BlockInfo]) -> list[dict]:
    """Build Plotly Gantt chart data from blocks."""
    data = []
    for block in blocks:
        if not block.started_at:
            continue
        start = block.started_at
        finish = block.completed_at if block.completed_at else datetime.now().isoformat()
        data.append({
            "Task": f"{block.block_id}: {block.name}",
            "Start": start,
            "Finish": finish,
            "Status": block.status,
        })
    return data
```

- [ ] **Step 2: Commit**

```bash
git add kevin/dashboard/components/run_detail.py
git commit -m "feat: add run detail page with mermaid pipeline and gantt chart"
```

---

### Task 7: Page 3 — Blueprint Viewer

**Files:**
- Create: `kevin/dashboard/components/blueprint_view.py`

- [ ] **Step 1: Implement blueprint viewer page**

```python
"""Page 3: Blueprint viewer with dependency graph and block table."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit_mermaid import st_mermaid

from kevin.dashboard.data_loader import BlueprintInfo, list_blueprints


def render(blueprints_dir: Path) -> None:
    st.header("Blueprints")

    blueprints = list_blueprints(blueprints_dir)
    if not blueprints:
        st.info(f"No blueprints found in `{blueprints_dir}`.")
        return

    # Blueprint selector
    bp_names = [f"{bp.blueprint_id} ({bp.blueprint_name})" for bp in blueprints]
    selected_idx = st.selectbox(
        "Select Blueprint",
        range(len(bp_names)),
        format_func=lambda i: bp_names[i],
    )

    bp = blueprints[selected_idx]

    # Metadata
    meta_col1, meta_col2, meta_col3 = st.columns(3)
    meta_col1.metric("Version", bp.version)
    meta_col2.metric("Blocks", bp.block_count)
    meta_col3.write(f"**Tags:** {', '.join(bp.tags)}")

    st.divider()

    # Dependency graph
    st.subheader("Block Dependency Graph")
    mermaid_code = _build_dependency_graph(bp)
    st_mermaid(mermaid_code, height=250)

    # Block table
    st.subheader("Block Definitions")
    table_data = []
    for block in bp.blocks:
        table_data.append({
            "Block ID": block.block_id,
            "Name": block.name,
            "Runner": block.runner,
            "Dependencies": ", ".join(block.dependencies) if block.dependencies else "—",
            "Timeout": f"{block.timeout}s",
            "Max Retries": block.max_retries,
            "Validators": ", ".join(block.validators) if block.validators else "—",
        })

    st.dataframe(table_data, use_container_width=True, hide_index=True)


def _build_dependency_graph(bp: BlueprintInfo) -> str:
    """Build a Mermaid flowchart from blueprint block dependencies."""
    lines = ["graph LR"]
    for block in bp.blocks:
        label = f"{block.block_id}: {block.name}"
        lines.append(f'    {block.block_id}["{label}"]')

    for block in bp.blocks:
        if block.dependencies:
            for dep in block.dependencies:
                lines.append(f"    {dep} --> {block.block_id}")
        elif len(bp.blocks) > 1:
            # No explicit deps — find position and chain to previous
            idx = next(i for i, b in enumerate(bp.blocks) if b.block_id == block.block_id)
            if idx > 0:
                prev = bp.blocks[idx - 1]
                if not any(block.block_id in b.dependencies for b in bp.blocks if b.block_id != block.block_id):
                    # Only add implicit edge if no other block depends on us via explicit deps
                    pass  # Let explicit deps handle it

    # Style
    lines.append("    classDef default fill:#4a90d9,stroke:#357abd,color:white")
    return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add kevin/dashboard/components/blueprint_view.py
git commit -m "feat: add blueprint viewer with dependency graph"
```

---

### Task 8: Seed Data + Smoke Test

**Files:**
- All files from previous tasks

- [ ] **Step 1: Generate seed data in project root**

```bash
python -m kevin.dashboard.seed --target-repo .
```

Expected: `Seeded 3 demo runs in .kevin/runs`

- [ ] **Step 2: Verify seed data files**

```bash
ls .kevin/runs/
```

Expected: 3 run directories

- [ ] **Step 3: Launch dashboard and verify**

```bash
streamlit run kevin/dashboard/app.py -- --kevin-root . --blueprints-dir blueprints
```

Manual verification:
- [ ] Run List page shows 3 runs with correct metrics (1 completed, 1 failed, 1 running)
- [ ] Run Detail page shows Mermaid pipeline + Gantt chart + expandable logs
- [ ] Blueprints page lists all bp_*.yaml files with dependency graphs

- [ ] **Step 4: Add `.kevin/` to `.gitignore`**

Append to `.gitignore`:

```
# Kevin run state (generated)
.kevin/
```

- [ ] **Step 5: Final commit**

```bash
git add .gitignore
git commit -m "chore: add .kevin/ to gitignore"
```

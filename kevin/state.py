"""File-based run state persistence.

Each Kevin run gets a directory: .kevin/runs/{run_id}/
  run.yaml      — overall run metadata
  B1.yaml       — per-block execution state
  B2.yaml       — ...
"""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml


@dataclass
class BlockState:
    """Mutable state for a single block execution."""

    block_id: str
    status: str = "pending"     # pending | running | passed | failed | skipped
    runner: str = ""
    started_at: str = ""
    completed_at: str = ""
    exit_code: int | None = None
    output_summary: str = ""
    validator_results: list[dict[str, Any]] = field(default_factory=list)
    retries: int = 0
    error: str = ""


@dataclass
class RunState:
    """Top-level state for a Kevin run."""

    run_id: str
    blueprint_id: str
    issue_number: int
    repo: str
    status: str = "pending"     # pending | running | completed | failed
    created_at: str = ""
    completed_at: str = ""
    blocks: dict[str, BlockState] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)

    # E3: Task completion tracking
    verification_summary: dict[str, Any] = field(default_factory=dict)
    completion_status: str = ""  # "" | "all_passed" | "validators_failed" | "worker_failed"
    pr_number: int | None = None
    issue_closed: bool = False


class StateManager:
    """Read/write run state to .kevin/runs/{run_id}/."""

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir

    def create_run(
        self,
        blueprint_id: str,
        issue_number: int,
        repo: str,
        variables: dict[str, str] | None = None,
        blueprint_path: Path | None = None,
    ) -> RunState:
        """Create a new run and persist initial state.

        If blueprint_path is provided, a snapshot of the YAML is saved into the
        run directory so that historical runs are always reproducible.
        """
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]
        run = RunState(
            run_id=run_id,
            blueprint_id=blueprint_id,
            issue_number=issue_number,
            repo=repo,
            status="running",
            created_at=_now(),
            variables=variables or {},
        )
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        self._save_run(run)

        # P0 #8: Immutable blueprint snapshot
        if blueprint_path and blueprint_path.exists():
            shutil.copy2(blueprint_path, run_dir / "blueprint_snapshot.yaml")

        return run

    def load_run(self, run_id: str) -> RunState:
        """Load an existing run from disk."""
        run_file = self._run_dir(run_id) / "run.yaml"
        with run_file.open() as f:
            data = yaml.safe_load(f)
        run = RunState(**{k: v for k, v in data.items() if k != "blocks"})
        run.blocks = {
            bid: BlockState(**bdata)
            for bid, bdata in data.get("blocks", {}).items()
        }
        return run

    def update_block(self, run: RunState, block_state: BlockState) -> None:
        """Update a block's state and persist."""
        run.blocks[block_state.block_id] = block_state
        self._save_run(run)
        self._save_block(run.run_id, block_state)

    def complete_run(self, run: RunState, status: str = "completed") -> None:
        """Mark the run as completed/failed and persist."""
        run.status = status
        run.completed_at = _now()
        self._save_run(run)

    def save_block_logs(
        self,
        run_id: str,
        block_id: str,
        *,
        prompt: str = "",
        stdout: str = "",
        stderr: str = "",
    ) -> Path:
        """Save full execution logs for a block (prompt + stdout + stderr).

        Returns the path to the log file.
        """
        logs_dir = self._run_dir(run_id) / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / f"{block_id}.log"
        sections = []
        if prompt:
            sections.append(f"=== PROMPT ===\n{prompt}")
        if stdout:
            sections.append(f"=== STDOUT ===\n{stdout}")
        if stderr:
            sections.append(f"=== STDERR ===\n{stderr}")
        log_path.write_text("\n\n".join(sections), encoding="utf-8")
        return log_path

    def save_executor_logs(
        self,
        run_id: str,
        *,
        prompt: str = "",
        stdout: str = "",
        stderr: str = "",
    ) -> Path:
        """Save full execution logs for agentic mode (single file).

        Unlike save_block_logs which creates per-block files, this saves
        a single executor.log for the entire agentic run.
        """
        logs_dir = self._run_dir(run_id) / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "executor.log"
        sections = []
        if prompt:
            sections.append(f"=== COMPILED PROMPT ===\n{prompt}")
        if stdout:
            sections.append(f"=== STDOUT ===\n{stdout}")
        if stderr:
            sections.append(f"=== STDERR ===\n{stderr}")
        log_path.write_text("\n\n".join(sections), encoding="utf-8")
        return log_path

    def list_runs(self) -> list[str]:
        """Return all run IDs sorted by creation time."""
        if not self._state_dir.exists():
            return []
        return sorted(
            d.name for d in self._state_dir.iterdir()
            if d.is_dir() and (d / "run.yaml").exists()
        )

    # -- Internal --

    def _run_dir(self, run_id: str) -> Path:
        return self._state_dir / run_id

    def _save_run(self, run: RunState) -> None:
        run_dir = self._run_dir(run.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        data = asdict(run)
        with (run_dir / "run.yaml").open("w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)

    def _save_block(self, run_id: str, block_state: BlockState) -> None:
        block_file = self._run_dir(run_id) / f"{block_state.block_id}.yaml"
        with block_file.open("w") as f:
            yaml.safe_dump(asdict(block_state), f, default_flow_style=False, allow_unicode=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

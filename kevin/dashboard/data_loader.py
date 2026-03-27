"""Dashboard data loader — read-only access layer for Kevin run state and blueprints.

Wraps StateManager and blueprint_loader internals, exposing frozen dataclasses
suitable for Streamlit dashboard consumption.

All functions are READ-ONLY. No file writes occur in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from kevin.blueprint_loader import Blueprint
from kevin.blueprint_loader import find_blueprint
from kevin.blueprint_loader import load as _load_blueprint_file


# ---------------------------------------------------------------------------
# Frozen Dashboard Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunSummary:
    """Lightweight summary of a single Kevin run, suitable for list views."""

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
    """Execution detail for a single block within a run."""

    block_id: str
    name: str
    status: str
    runner: str
    exit_code: int | None
    retries: int
    started_at: str
    completed_at: str
    validator_results: tuple[dict[str, Any], ...]
    error: str


@dataclass(frozen=True)
class RunDetail:
    """Full detail of a single Kevin run including all block states."""

    run_id: str
    blueprint_id: str
    issue_number: int
    repo: str
    status: str
    created_at: str
    completed_at: str
    variables: dict[str, str]
    blocks: tuple[BlockInfo, ...]


@dataclass(frozen=True)
class BlueprintBlockInfo:
    """Metadata for a single block within a Blueprint definition."""

    block_id: str
    name: str
    runner: str
    dependencies: tuple[str, ...]
    timeout: int
    max_retries: int
    validators: tuple[str, ...]


@dataclass(frozen=True)
class BlueprintInfo:
    """Summary of a Blueprint definition."""

    blueprint_id: str
    blueprint_name: str
    version: str
    tags: tuple[str, ...]
    block_count: int
    blocks: tuple[BlueprintBlockInfo, ...]
    raw: dict[str, Any]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_runs(state_dir: Path) -> list[RunSummary]:
    """Return all run summaries sorted newest-first by run_id.

    Reads YAML directly for fault tolerance — skips unparseable or incomplete
    run directories without raising.
    """
    if not state_dir.exists():
        return []

    summaries: list[RunSummary] = []
    for run_dir in sorted(state_dir.iterdir(), reverse=True):
        run_file = run_dir / "run.yaml"
        if not (run_dir.is_dir() and run_file.exists()):
            continue
        try:
            summary = _load_run_summary(run_file)
            summaries.append(summary)
        except Exception:  # noqa: BLE001 — fault-tolerant by design
            continue

    return summaries


def load_run(state_dir: Path, run_id: str) -> RunDetail:
    """Load full run detail for a specific run_id.

    Raises:
        FileNotFoundError: When the run directory or run.yaml does not exist.
    """
    run_file = state_dir / run_id / "run.yaml"
    if not run_file.exists():
        raise FileNotFoundError(f"Run '{run_id}' not found in {state_dir}")

    with run_file.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    raw_blocks: dict[str, dict[str, Any]] = data.get("blocks", {})
    block_infos = sorted(
        (_parse_block_info(block_id, block_data) for block_id, block_data in raw_blocks.items()),
        key=lambda b: b.block_id,
    )

    return RunDetail(
        run_id=data.get("run_id", ""),
        blueprint_id=data.get("blueprint_id", ""),
        issue_number=int(data.get("issue_number", 0)),
        repo=data.get("repo", ""),
        status=data.get("status", ""),
        created_at=data.get("created_at", ""),
        completed_at=data.get("completed_at", ""),
        variables=dict(data.get("variables", {})),
        blocks=tuple(block_infos),
    )


def load_block_log(state_dir: Path, run_id: str, block_id: str) -> str:
    """Return the full log content for a block execution.

    Returns an empty string if the log file does not exist.
    """
    log_path = state_dir / run_id / "logs" / f"{block_id}.log"
    if not log_path.exists():
        return ""
    return log_path.read_text(encoding="utf-8")


def list_blueprints(blueprints_dir: Path) -> list[BlueprintInfo]:
    """Return BlueprintInfo for all valid YAML files in blueprints_dir.

    Skips subdirectories, non-YAML files, and unparseable files.
    Returns an empty list when the directory does not exist.
    """
    if not blueprints_dir.exists():
        return []

    infos: list[BlueprintInfo] = []
    for yaml_file in sorted(blueprints_dir.glob("*.yaml")):
        if not yaml_file.is_file():
            continue
        try:
            blueprint = _load_blueprint_file(yaml_file)
            infos.append(_blueprint_to_info(blueprint))
        except Exception:  # noqa: BLE001 — fault-tolerant by design
            continue

    return infos


def load_blueprint(blueprints_dir: Path, blueprint_id: str) -> BlueprintInfo:
    """Load a single Blueprint by ID.

    Raises:
        FileNotFoundError: When no matching blueprint file is found.
    """
    blueprint_path = find_blueprint(blueprints_dir, blueprint_id)
    blueprint = _load_blueprint_file(blueprint_path)
    return _blueprint_to_info(blueprint)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_run_summary(run_file: Path) -> RunSummary:
    """Parse a run.yaml file into a RunSummary."""
    with run_file.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    raw_blocks: dict[str, dict[str, Any]] = data.get("blocks", {})
    blocks_passed = sum(
        1 for b in raw_blocks.values() if b.get("status") == "passed"
    )
    blocks_total = len(raw_blocks)

    created_at = data.get("created_at", "")
    completed_at = data.get("completed_at", "")
    elapsed = _compute_elapsed(created_at, completed_at)

    return RunSummary(
        run_id=data.get("run_id", ""),
        blueprint_id=data.get("blueprint_id", ""),
        issue_number=int(data.get("issue_number", 0)),
        repo=data.get("repo", ""),
        status=data.get("status", ""),
        blocks_passed=blocks_passed,
        blocks_total=blocks_total,
        started_at=created_at,
        elapsed_seconds=elapsed,
    )


def _parse_block_info(block_id: str, data: dict[str, Any]) -> BlockInfo:
    """Convert a raw block dict from run.yaml into a BlockInfo."""
    raw_validators = data.get("validator_results", [])
    # Ensure each entry is a plain dict (YAML may deserialize as dict already)
    validator_results = tuple(
        dict(v) if isinstance(v, dict) else {"raw": str(v)} for v in raw_validators
    )
    return BlockInfo(
        block_id=data.get("block_id", block_id),
        name=data.get("name", ""),
        status=data.get("status", ""),
        runner=data.get("runner", ""),
        exit_code=data.get("exit_code"),
        retries=int(data.get("retries", 0)),
        started_at=data.get("started_at", ""),
        completed_at=data.get("completed_at", ""),
        validator_results=validator_results,
        error=data.get("error", ""),
    )


def _blueprint_to_info(blueprint: Blueprint) -> BlueprintInfo:
    """Convert a Blueprint into a BlueprintInfo."""
    raw_metadata = blueprint.raw.get("metadata", {})
    tags = tuple(raw_metadata.get("tags", []))

    blocks = tuple(
        BlueprintBlockInfo(
            block_id=block.block_id,
            name=block.name,
            runner=block.runner,
            dependencies=tuple(block.dependencies),
            timeout=block.timeout,
            max_retries=block.max_retries,
            validators=tuple(v.type for v in block.validators),
        )
        for block in blueprint.blocks
    )

    return BlueprintInfo(
        blueprint_id=blueprint.blueprint_id,
        blueprint_name=blueprint.blueprint_name,
        version=blueprint.version,
        tags=tags,
        block_count=len(blocks),
        blocks=blocks,
        raw=blueprint.raw,
    )


def _compute_elapsed(started_at: str, completed_at: str) -> float | None:
    """Compute elapsed seconds between two ISO 8601 timestamps.

    Returns None if either timestamp is empty or unparseable.
    """
    if not started_at or not completed_at:
        return None
    try:
        start = _parse_iso(started_at)
        end = _parse_iso(completed_at)
        return (end - start).total_seconds()
    except (ValueError, TypeError):
        return None


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string, normalising timezone handling."""
    # Python 3.11+ handles 'Z' natively; for 3.10 compatibility strip it
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)

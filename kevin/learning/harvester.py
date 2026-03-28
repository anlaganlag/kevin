"""Post-run knowledge extraction — reads .kevin/runs/ and writes to SQLite."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

from kevin.learning.db import (
    connect, delete_fts, ensure_schema, safe_variables_json,
    upsert_block, upsert_fts, upsert_run,
)


@dataclass(frozen=True)
class HarvestResult:
    harvested: int
    skipped_existing: int
    failed_parse: int


def harvest_run(db_path: Path, state_dir: Path, run_id: str) -> None:
    """Extract knowledge from a single run into SQLite.

    Idempotent. Skips runs not in 'completed' or 'failed' status (constraint C2).
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
    existing = {row[0] for row in conn.execute("SELECT run_id FROM run_history").fetchall()}
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
                logger.debug("Failed to harvest run %s", run_id, exc_info=True)
                failed_parse += 1
    finally:
        conn.close()

    return HarvestResult(harvested=harvested, skipped_existing=skipped, failed_parse=failed_parse)


def _harvest_run_data(conn: Any, data: dict[str, Any], run_dir: Path) -> None:
    run_id = data.get("run_id", "")
    blueprint_id = data.get("blueprint_id", "")
    variables = data.get("variables", {})
    issue_title = variables.get("issue_title", "")
    issue_body = variables.get("issue_body", "")
    blocks_data: dict[str, dict] = data.get("blocks", {})

    elapsed = _compute_elapsed(data.get("created_at", ""), data.get("completed_at", ""))

    failed_block_id = None
    failure_reason = None
    for bid, bdata in blocks_data.items():
        if bdata.get("status") == "failed":
            failed_block_id = bid
            failure_reason = (bdata.get("error", "") or "")[:500]
            break

    passed_blocks = sum(1 for b in blocks_data.values() if b.get("status") == "passed")

    upsert_run(conn, run_id=run_id, blueprint_id=blueprint_id,
               issue_number=data.get("issue_number"), issue_title=issue_title,
               repo=data.get("repo"), status=data.get("status", ""),
               total_blocks=len(blocks_data), passed_blocks=passed_blocks,
               failed_block_id=failed_block_id, failure_reason=failure_reason,
               elapsed_seconds=elapsed, created_at=data.get("created_at"),
               variables_json=safe_variables_json(variables))

    # Load block names from blueprint snapshot (BlockState doesn't persist name)
    block_names: dict[str, str] = {}
    snapshot_path = run_dir / "blueprint_snapshot.yaml"
    if snapshot_path.exists():
        try:
            with snapshot_path.open(encoding="utf-8") as f:
                bp_data = yaml.safe_load(f)
            bp_root = bp_data.get("blueprint", bp_data)
            raw_blocks = (
                bp_root.get("workflow", {})
                .get("ralph_loop", {})
                .get("step_3", {})
                .get("dependency_graph", {})
                .get("blocks", [])
            )
            for rb in raw_blocks:
                block_names[rb.get("block_id", "")] = rb.get("name", "")
        except Exception:
            logger.debug("Failed to load blueprint snapshot in %s", run_dir, exc_info=True)

    logs_dir = run_dir / "logs"
    for bid, bdata in blocks_data.items():
        block_elapsed = _compute_elapsed(bdata.get("started_at", ""), bdata.get("completed_at", ""))
        upsert_block(conn, run_id=run_id, block_id=bid, blueprint_id=blueprint_id,
                     block_name=block_names.get(bid, ""), runner=bdata.get("runner", ""),
                     status=bdata.get("status", ""), exit_code=bdata.get("exit_code"),
                     retries=int(bdata.get("retries", 0)), elapsed_seconds=block_elapsed,
                     error=(bdata.get("error") or "")[:500] or None,
                     validator_json=json.dumps(bdata.get("validator_results", [])))

        if logs_dir.exists():
            log_file = _find_final_log(logs_dir, bid)
            if log_file:
                prompt, output = _parse_log_file(log_file)
                delete_fts(conn, run_id=run_id, block_id=bid)
                upsert_fts(conn, run_id=run_id, block_id=bid, blueprint_id=blueprint_id,
                           status=bdata.get("status", ""), issue_title=issue_title,
                           issue_body=issue_body, prompt=prompt[:2000],
                           output_summary=(bdata.get("output_summary", "") or output)[:500])


def _find_final_log(logs_dir: Path, block_id: str) -> Path | None:
    """Find the final attempt log. Parses attempt numbers explicitly (constraint C3)."""
    max_attempt = -1
    best = None
    for f in logs_dir.glob(f"{block_id}*.log"):
        attempt = _parse_attempt_number(f.name, block_id)
        if attempt > max_attempt:
            max_attempt = attempt
            best = f
    return best


def _parse_attempt_number(filename: str, block_id: str) -> int:
    """Return attempt number from filename.

    'B2.log' -> 0, 'B2.attempt-1.log' -> 1, 'B2.attempt-10.log' -> 10.
    Returns -1 for unrecognized patterns.
    """
    if filename == f"{block_id}.log":
        return 0
    match = re.search(rf"{re.escape(block_id)}\.attempt-(\d+)\.log$", filename)
    if match:
        return int(match.group(1))
    return -1


def _parse_log_file(log_path: Path) -> tuple[str, str]:
    """Extract prompt and stdout sections from a structured log file."""
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
    """Compute elapsed seconds between two ISO 8601 timestamps. Returns None on failure."""
    if not started_at or not completed_at:
        return None
    try:
        start = _parse_iso(started_at)
        end = _parse_iso(completed_at)
        return (end - start).total_seconds()
    except (ValueError, TypeError):
        return None


def _parse_iso(ts: str) -> datetime:
    """Parse ISO 8601 timestamp, normalizing Z suffix to +00:00."""
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)

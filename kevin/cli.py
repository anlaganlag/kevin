#!/usr/bin/env python3
"""Kevin Planning Agent — CLI entry point.

Usage:
    python kevin/kevin.py run --issue 1 --repo owner/repo [--target-repo ./path]
    python kevin/kevin.py run-block --block B2 --run-id <id>
    python kevin/kevin.py resume --run-id <id>
    python kevin/kevin.py list-runs
    python kevin/kevin.py dry-run --issue 1 --repo owner/repo
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from kevin import __version__
from kevin.agent_runner import run_block
from kevin.blueprint_loader import Block, find_blueprint, load
from kevin.config import KevinConfig, build_config
from kevin.github_client import Issue, add_labels, fetch_issue, post_comment, remove_labels
from kevin.intent import classify
from kevin.state import BlockState, RunState, StateManager


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kevin",
        description=f"Kevin Planning Agent v{__version__}",
    )
    parser.add_argument("--version", action="version", version=f"kevin {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    p_run = sub.add_parser("run", help="Run a full Blueprint for a GitHub Issue")
    p_run.add_argument("--issue", type=int, required=True, help="GitHub Issue number")
    p_run.add_argument("--repo", required=True, help="GitHub repo (owner/repo)")
    p_run.add_argument("--target-repo", default="", help="Local path to target repo")
    p_run.add_argument("--blueprint", default="", help="Blueprint ID override (skips label classification)")
    p_run.add_argument("--agent-id", default="", help="Agent identity posted in AgentCompletedEvent signal")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--verbose", action="store_true")

    # --- run-block ---
    p_block = sub.add_parser("run-block", help="Run a single block from an existing run")
    p_block.add_argument("--block", required=True, help="Block ID (e.g. B2)")
    p_block.add_argument("--run-id", required=True, help="Run ID to resume from")
    p_block.add_argument("--target-repo", default="", help="Local path to target repo")
    p_block.add_argument("--verbose", action="store_true")

    # --- resume ---
    p_resume = sub.add_parser("resume", help="Resume a failed/interrupted run")
    p_resume.add_argument("--run-id", required=True, help="Run ID to resume")
    p_resume.add_argument("--target-repo", default="", help="Local path to target repo")
    p_resume.add_argument("--verbose", action="store_true")

    # --- list-runs ---
    sub.add_parser("list-runs", help="List all Kevin runs")

    # --- dry-run (alias) ---
    p_dry = sub.add_parser("dry-run", help="Dry-run a Blueprint (alias for run --dry-run)")
    p_dry.add_argument("--issue", type=int, required=True)
    p_dry.add_argument("--repo", required=True)
    p_dry.add_argument("--target-repo", default="")
    p_dry.add_argument("--verbose", action="store_true")

    # --- debug ---
    p_debug = sub.add_parser("debug", help="Replay a failed block's prompt in interactive Claude CLI")
    p_debug.add_argument("--run-id", required=True, help="Run ID to debug")
    p_debug.add_argument("--block", required=True, help="Block ID to replay (e.g. B2)")
    p_debug.add_argument("--target-repo", default="", help="Local path to target repo")

    args = parser.parse_args(argv)

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "dry-run":
        args.dry_run = True
        return cmd_run(args)
    elif args.command == "run-block":
        return cmd_run_block(args)
    elif args.command == "resume":
        return cmd_resume(args)
    elif args.command == "list-runs":
        return cmd_list_runs(args)
    elif args.command == "debug":
        return cmd_debug(args)
    return 1


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    """Full run: fetch issue → classify → load blueprint → execute blocks."""
    agent_id = getattr(args, "agent_id", "").strip()
    exit_code = 1
    repo = args.repo
    issue_number = args.issue
    resolved_blueprint_id = getattr(args, "blueprint", "").strip()

    try:
        exit_code = _cmd_run_inner(args)
    finally:
        # Always signal completion when agent_id is set — even on early failure.
        # This ensures the Planning Agent state machine always advances (or fails cleanly).
        config = build_config(
            repo=repo,
            target_repo=getattr(args, "target_repo", ""),
            dry_run=getattr(args, "dry_run", False),
        )
        if not config.dry_run and agent_id:
            _post_agent_completed_event(
                repo, issue_number, agent_id,
                success=(exit_code == 0),
                blueprint_id=resolved_blueprint_id,
            )

    return exit_code


def _cmd_run_inner(args: argparse.Namespace) -> int:
    """Inner implementation of cmd_run — all early returns live here."""
    config = build_config(
        repo=args.repo,
        target_repo=args.target_repo,
        dry_run=getattr(args, "dry_run", False),
        verbose=args.verbose,
    )

    # 1. Fetch issue
    _log(config, f"Fetching issue #{args.issue} from {args.repo}...")
    issue = fetch_issue(args.repo, args.issue)
    _log(config, f"  Title: {issue.title}")
    _log(config, f"  Labels: {issue.labels}")

    # 2. Resolve blueprint — explicit override takes priority over label classification
    blueprint_override = getattr(args, "blueprint", "").strip()
    if blueprint_override:
        blueprint_id = blueprint_override
        _log(config, f"  Blueprint override: {blueprint_id}")
    else:
        intent = classify(issue.labels, config.intent_map)
        if intent is None:
            _err(f"Cannot classify issue #{args.issue}. Labels: {issue.labels}")
            _err("Ensure the issue has 'kevin' label + a task type label (coding-task, code-review, etc.)")
            return 1
        blueprint_id = intent.blueprint_id
        _log(config, f"  Intent: {blueprint_id} (matched: {intent.matched_label})")

    # 3. Load blueprint
    bp_path = find_blueprint(config.blueprints_dir, blueprint_id)
    blueprint = load(bp_path)
    _log(config, f"  Blueprint: {blueprint.blueprint_name} ({len(blueprint.blocks)} blocks)")

    # 4. Build variables
    variables = _build_variables(config, issue)

    # 5. Create run state
    state_mgr = StateManager(config.state_dir)
    run = state_mgr.create_run(
        blueprint_id=blueprint.blueprint_id,
        issue_number=issue.number,
        repo=config.repo_full_name,
        variables=variables,
        blueprint_path=bp_path,
    )
    _log(config, f"  Run ID: {run.run_id}")

    # 6. Post start comment
    if not config.dry_run:
        post_comment(
            config.repo_full_name,
            issue.number,
            f"Kevin started `{blueprint.blueprint_id}` (run: `{run.run_id}`)\n\n"
            f"Blocks: {' → '.join(b.block_id for b in blueprint.blocks)}",
        )

    # 7. Execute blocks
    return _execute_blocks(config, state_mgr, run, blueprint.blocks, variables, issue=issue)


def cmd_run_block(args: argparse.Namespace) -> int:
    """Run a single block from an existing run."""
    config = build_config(target_repo=args.target_repo, verbose=args.verbose)
    state_mgr = StateManager(config.state_dir)

    run = state_mgr.load_run(args.run_id)
    blueprint = _load_blueprint_for_run(config, args.run_id, run.blueprint_id)

    block = next((b for b in blueprint.blocks if b.block_id == args.block), None)
    if block is None:
        _err(f"Block {args.block} not found in {run.blueprint_id}")
        return 1

    return _execute_blocks(config, state_mgr, run, [block], run.variables)


def cmd_resume(args: argparse.Namespace) -> int:
    """Resume a run from the first non-completed block."""
    config = build_config(target_repo=args.target_repo, verbose=args.verbose)
    state_mgr = StateManager(config.state_dir)

    run = state_mgr.load_run(args.run_id)
    blueprint = _load_blueprint_for_run(config, args.run_id, run.blueprint_id)

    # Filter to blocks that haven't passed
    remaining = [
        b for b in blueprint.blocks
        if run.blocks.get(b.block_id, BlockState(block_id=b.block_id)).status != "passed"
    ]

    if not remaining:
        _log(config, "All blocks already completed.")
        return 0

    _log(config, f"Resuming run {run.run_id}: {len(remaining)} blocks remaining")
    run.status = "running"
    return _execute_blocks(config, state_mgr, run, remaining, run.variables)


def cmd_list_runs(args: argparse.Namespace) -> int:
    """List all Kevin runs."""
    config = build_config()
    state_mgr = StateManager(config.state_dir)

    runs = state_mgr.list_runs()
    if not runs:
        print("No runs found.")
        return 0

    for run_id in runs:
        run = state_mgr.load_run(run_id)
        passed = sum(1 for b in run.blocks.values() if b.status == "passed")
        total = len(run.blocks)
        print(f"  {run_id}  [{run.status}]  {run.blueprint_id}  issue#{run.issue_number}  {passed}/{total} blocks")

    return 0


def cmd_debug(args: argparse.Namespace) -> int:
    """Replay a failed block's prompt in interactive Claude CLI.

    Reads the saved log from a previous run, extracts the rendered prompt,
    and launches `claude` (interactive, no -p) with the prompt pre-loaded
    so the developer can take over from where the agent failed.
    """
    import subprocess

    config = build_config(target_repo=args.target_repo)
    state_mgr = StateManager(config.state_dir)
    run = state_mgr.load_run(args.run_id)

    # Find the log file (prefer latest attempt)
    logs_dir = config.state_dir / args.run_id / "logs"
    if not logs_dir.exists():
        _err(f"No logs found for run {args.run_id}")
        return 1

    # Find the most recent attempt log for this block
    candidates = sorted(logs_dir.glob(f"{args.block}*.log"), reverse=True)
    if not candidates:
        _err(f"No log found for block {args.block} in run {args.run_id}")
        return 1

    log_content = candidates[0].read_text(encoding="utf-8")

    # Extract prompt section
    prompt = ""
    if "=== PROMPT ===" in log_content:
        parts = log_content.split("=== PROMPT ===\n", 1)
        if len(parts) > 1:
            # Everything until next section or end
            prompt_section = parts[1]
            for marker in ("=== STDOUT ===", "=== STDERR ==="):
                if marker in prompt_section:
                    prompt_section = prompt_section.split(marker)[0]
            prompt = prompt_section.strip()

    if not prompt:
        _err(f"No prompt found in {candidates[0]}")
        return 1

    # Resolve cwd from block config
    blueprint = _load_blueprint_for_run(config, args.run_id, run.blueprint_id)
    block = next((b for b in blueprint.blocks if b.block_id == args.block), None)
    cwd = str(config.target_repo)
    if block and block.runner_config.get("cwd"):
        from kevin.prompt_template import render
        cwd = render(block.runner_config["cwd"], run.variables)

    print(f"Replaying block {args.block} from run {args.run_id}")
    print(f"Log: {candidates[0]}")
    print(f"CWD: {cwd}")
    print(f"Prompt length: {len(prompt)} chars")
    print("-" * 60)

    # Launch interactive Claude CLI with the prompt
    return subprocess.call(["claude", "-p", prompt, "--cwd", cwd])


# ---------------------------------------------------------------------------
# Blueprint loading helper
# ---------------------------------------------------------------------------

def _load_blueprint_for_run(config: KevinConfig, run_id: str, blueprint_id: str) -> "Blueprint":
    """Load a Blueprint, preferring the immutable snapshot from the run directory."""
    from kevin.blueprint_loader import Blueprint

    snapshot = config.state_dir / run_id / "blueprint_snapshot.yaml"
    bp_path = snapshot if snapshot.exists() else find_blueprint(config.blueprints_dir, blueprint_id)
    return load(bp_path)


# ---------------------------------------------------------------------------
# Core execution loop
# ---------------------------------------------------------------------------

def _execute_blocks(
    config: KevinConfig,
    state_mgr: StateManager,
    run: RunState,
    blocks: list[Block],
    variables: dict[str, str],
    *,
    issue: Issue | None = None,
) -> int:
    """Execute a list of blocks sequentially with retry logic."""
    all_passed = True

    for block in blocks:
        _log(config, f"\n{'='*60}")
        _log(config, f"Block {block.block_id}: {block.name} (runner: {block.runner})")
        _log(config, f"{'='*60}")

        # Update state: running
        bs = BlockState(
            block_id=block.block_id,
            status="running",
            runner=block.runner,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        state_mgr.update_block(run, bs)

        # Notify Teams: block started (real-time progress)
        if not config.dry_run:
            _notify_teams(config, run, blocks, issue, "running")

        # Retry loop
        success = False
        for attempt in range(block.max_retries + 1):
            if attempt > 0:
                _log(config, f"  Retry {attempt}/{block.max_retries}...")

            result = run_block(block, variables, dry_run=config.dry_run, is_retry=attempt > 0)

            # Save full execution logs (rendered prompt, not template)
            # Include attempt number to preserve logs across retries
            log_id = f"{block.block_id}.attempt-{attempt}" if attempt > 0 else block.block_id
            state_mgr.save_block_logs(
                run.run_id,
                log_id,
                prompt=result.prompt or block.prompt_template,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
            )

            bs.retries = attempt
            bs.exit_code = result.exit_code
            bs.output_summary = result.stdout[:500] if result.stdout else ""
            bs.validator_results = result.validator_results or []

            if result.success:
                bs.status = "passed"
                bs.completed_at = datetime.now(timezone.utc).isoformat()
                state_mgr.update_block(run, bs)
                _log(config, f"  PASSED")
                success = True
                break
            else:
                _log(config, f"  FAILED: {result.stderr[:200]}")
                bs.error = result.stderr[:500]

        if not success:
            bs.status = "failed"
            bs.completed_at = datetime.now(timezone.utc).isoformat()
            state_mgr.update_block(run, bs)
            _err(f"Block {block.block_id} failed after {block.max_retries + 1} attempts")
            all_passed = False
            break  # Stop pipeline on failure

    # Finalize run
    final_status = "completed" if all_passed else "failed"
    state_mgr.complete_run(run, final_status)

    # Build error summary from failed block (if any)
    error_summary = ""
    if not all_passed:
        for bs in run.blocks.values():
            if bs.status == "failed" and bs.error:
                error_summary = f"[{bs.block_id}] {bs.error[:300]}"
                break

    # Post completion comment + update labels
    if not config.dry_run:
        _post_completion_comment(config, run, blocks)
        _notify_teams(config, run, blocks, issue, final_status, error=error_summary)
        try:
            remove_labels(run.repo, run.issue_number, ["kevin"])
            if all_passed:
                add_labels(run.repo, run.issue_number, ["kevin-completed"])
        except Exception:
            pass

    _log(config, f"\nRun {run.run_id}: {final_status}")
    return 0 if all_passed else 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_variables(config: KevinConfig, issue: Issue) -> dict[str, str]:
    """Build the variable dictionary for template rendering."""
    variables = {
        "issue_number": str(issue.number),
        "issue_title": issue.title,
        "issue_body": issue.body,
        "issue_labels": ", ".join(issue.labels),
        "target_repo": str(config.target_repo),
        "owner": config.repo_owner,
        "repo": config.repo_name,
        "repo_full": config.repo_full_name,
    }

    # Extract pr_number from issue body (e.g. "PR #30", "#30", "pull/30")
    import re
    pr_match = re.search(r"(?:PR\s*#|pull/|pull request\s*#?)(\d+)", issue.body, re.IGNORECASE)
    if pr_match:
        variables["pr_number"] = pr_match.group(1)

    return variables


def _post_completion_comment(
    config: KevinConfig, run: RunState, blocks: list[Block] | None = None,
) -> None:
    """Post a summary comment on the issue."""
    # Build block_id → name lookup
    name_map: dict[str, str] = {}
    if blocks:
        name_map = {b.block_id: b.name for b in blocks}

    lines = [f"Kevin run `{run.run_id}` — **{run.status}**\n"]
    lines.append("| Block | Name | Status |")
    lines.append("|-------|------|--------|")
    for bid, bs in run.blocks.items():
        icon = ":white_check_mark:" if bs.status == "passed" else ":x:"
        name = name_map.get(bid, "")
        lines.append(f"| {bid} | {name} | {icon} {bs.status} |")

    try:
        post_comment(run.repo, run.issue_number, "\n".join(lines))
    except Exception:
        pass  # TODO: FIX — don't fail the run for a comment failure


def _post_agent_completed_event(
    repo: str,
    issue_number: int,
    agent_id: str,
    *,
    success: bool,
    blueprint_id: str = "",
) -> None:
    """Post a fenced EDA JSON comment that the EDA router normalises into
    AgentCompletedEvent and routes back to the Planning Agent.

    The comment must come from github-actions[bot] — satisfied automatically
    when running inside a GitHub Actions workflow.
    """
    import json

    payload: dict[str, str] = {
        "event_type": "AgentCompletedEvent",
        "agent_id": agent_id,
        "status": "success" if success else "failure",
    }
    if blueprint_id:
        payload["blueprint_id"] = blueprint_id

    body = f"```eda\n{json.dumps(payload)}\n```"
    try:
        post_comment(repo, issue_number, body)
    except Exception:
        pass  # non-fatal — Planning Agent will timeout and human can restart


def _extract_pr_number(run: RunState) -> int | None:
    """Extract PR number from B3 output_summary (gh pr create URL)."""
    import re

    b3 = run.blocks.get("B3")
    if not b3 or not b3.output_summary:
        return None
    match = re.search(r"github\.com/[^/]+/[^/]+/pull/(\d+)", b3.output_summary)
    return int(match.group(1)) if match else None


def _notify_teams(
    config: KevinConfig,
    run: RunState,
    blocks: list[Block],
    issue: Issue | None,
    status: str,
    *,
    error: str = "",
) -> None:
    """Push run status to Teams Bot (if TEAMS_BOT_URL is set).

    Called at three points:
      1. Before each block starts (status="running") — real-time progress
      2. After all blocks pass (status="completed")
      3. On failure (status="failed", error=<summary>)
    """
    import json
    import os
    from urllib.request import Request, urlopen

    teams_url = os.getenv("TEAMS_BOT_URL", "")
    if not teams_url:
        return

    block_list = []
    for b in blocks:
        bs = run.blocks.get(b.block_id)
        duration: float | None = None
        if bs and bs.started_at and bs.completed_at:
            started = datetime.fromisoformat(bs.started_at)
            completed = datetime.fromisoformat(bs.completed_at)
            duration = (completed - started).total_seconds()
        block_list.append({
            "block_id": b.block_id,
            "name": b.name,
            "status": bs.status if bs else "pending",
            "duration_seconds": duration,
        })

    # Map status to event type
    event = "block_update" if status == "running" else f"run_{status}"

    # Build GitHub Actions logs URL if available
    github_run_id = os.getenv("GITHUB_RUN_ID", "")
    github_server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    github_repo = os.getenv("GITHUB_REPOSITORY", "")
    logs_url = (
        f"{github_server}/{github_repo}/actions/runs/{github_run_id}"
        if github_run_id and github_repo
        else ""
    )

    payload: dict[str, object] = {
        "event": event,
        "run_id": run.run_id,
        "issue_number": run.issue_number,
        "issue_title": issue.title if issue else "",
        "repo": run.repo,
        "blueprint_id": run.blueprint_id,
        "status": status,
        "blocks": block_list,
    }

    if error:
        payload["error"] = error[:500]
    if logs_url:
        payload["logs_url"] = logs_url

    # Include PR info on completion events
    if status in ("completed", "failed"):
        pr_number = _extract_pr_number(run)
        if pr_number:
            payload["pr_number"] = pr_number
            payload["pr_url"] = f"https://github.com/{run.repo}/pull/{pr_number}"

    try:
        data = json.dumps(payload).encode()
        req = Request(
            f"{teams_url}/api/notify",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urlopen(req, timeout=10)
    except Exception as e:
        _log(config, f"  [WARN] Teams notify failed: {e}")


def _log(config: KevinConfig, msg: str) -> None:
    if config.verbose or config.dry_run:
        print(msg, file=sys.stderr)


def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())

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
from pathlib import Path

from kevin import __version__
from kevin.agent_runner import run_block
from kevin.blueprint_loader import Block, find_blueprint, load
from kevin.config import KevinConfig, build_config
from kevin.github_client import Issue, add_labels, fetch_issue, post_comment
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
    return 1


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    """Full run: fetch issue → classify → load blueprint → execute blocks."""
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

    # 2. Classify intent
    intent = classify(issue.labels, config.intent_map)
    if intent is None:
        _err(f"Cannot classify issue #{args.issue}. Labels: {issue.labels}")
        _err("Ensure the issue has 'kevin' label + a task type label (coding-task, code-review, etc.)")
        return 1

    _log(config, f"  Intent: {intent.blueprint_id} (matched: {intent.matched_label})")

    # 3. Load blueprint
    bp_path = find_blueprint(config.blueprints_dir, intent.blueprint_id)
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
    return _execute_blocks(config, state_mgr, run, blueprint.blocks, variables)


def cmd_run_block(args: argparse.Namespace) -> int:
    """Run a single block from an existing run."""
    config = build_config(target_repo=args.target_repo, verbose=args.verbose)
    state_mgr = StateManager(config.state_dir)

    run = state_mgr.load_run(args.run_id)
    bp_path = find_blueprint(config.blueprints_dir, run.blueprint_id)
    blueprint = load(bp_path)

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
    bp_path = find_blueprint(config.blueprints_dir, run.blueprint_id)
    blueprint = load(bp_path)

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


# ---------------------------------------------------------------------------
# Core execution loop
# ---------------------------------------------------------------------------

def _execute_blocks(
    config: KevinConfig,
    state_mgr: StateManager,
    run: RunState,
    blocks: list[Block],
    variables: dict[str, str],
) -> int:
    """Execute a list of blocks sequentially with retry logic."""
    all_passed = True

    for block in blocks:
        _log(config, f"\n{'='*60}")
        _log(config, f"Block {block.block_id}: {block.name} (runner: {block.runner})")
        _log(config, f"{'='*60}")

        # Update state: running
        bs = BlockState(block_id=block.block_id, status="running", runner=block.runner)
        state_mgr.update_block(run, bs)

        # Retry loop
        success = False
        for attempt in range(block.max_retries + 1):
            if attempt > 0:
                _log(config, f"  Retry {attempt}/{block.max_retries}...")

            result = run_block(block, variables, dry_run=config.dry_run)

            # Save full execution logs (rendered prompt, not template)
            state_mgr.save_block_logs(
                run.run_id,
                block.block_id,
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
                state_mgr.update_block(run, bs)
                _log(config, f"  PASSED")
                success = True
                break
            else:
                _log(config, f"  FAILED: {result.stderr[:200]}")
                bs.error = result.stderr[:500]

        if not success:
            bs.status = "failed"
            state_mgr.update_block(run, bs)
            _err(f"Block {block.block_id} failed after {block.max_retries + 1} attempts")
            all_passed = False
            break  # Stop pipeline on failure

    # Finalize run
    final_status = "completed" if all_passed else "failed"
    state_mgr.complete_run(run, final_status)

    # Post completion comment
    if not config.dry_run:
        _post_completion_comment(config, run)

    _log(config, f"\nRun {run.run_id}: {final_status}")
    return 0 if all_passed else 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_variables(config: KevinConfig, issue: Issue) -> dict[str, str]:
    """Build the variable dictionary for template rendering."""
    return {
        "issue_number": str(issue.number),
        "issue_title": issue.title,
        "issue_body": issue.body,
        "issue_labels": ", ".join(issue.labels),
        "target_repo": str(config.target_repo),
        "owner": config.repo_owner,
        "repo": config.repo_name,
        "repo_full": config.repo_full_name,
    }


def _post_completion_comment(config: KevinConfig, run: RunState) -> None:
    """Post a summary comment on the issue."""
    lines = [f"Kevin run `{run.run_id}` — **{run.status}**\n"]
    lines.append("| Block | Status |")
    lines.append("|-------|--------|")
    for bid, bs in run.blocks.items():
        icon = ":white_check_mark:" if bs.status == "passed" else ":x:"
        lines.append(f"| {bid} | {icon} {bs.status} |")

    try:
        post_comment(run.repo, run.issue_number, "\n".join(lines))
    except Exception:
        pass  # TODO: FIX — don't fail the run for a comment failure


def _log(config: KevinConfig, msg: str) -> None:
    if config.verbose or config.dry_run:
        print(msg, file=sys.stderr)


def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())

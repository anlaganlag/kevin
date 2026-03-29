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
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from kevin import __version__
from kevin.agent_runner import BlockResult, run_block, run_block_async
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
    p_run.add_argument("--issue", type=int, default=0, help="GitHub Issue number")
    p_run.add_argument("--repo", default="", help="GitHub repo (owner/repo)")
    p_run.add_argument("--target-repo", default="", help="Local path to target repo")
    p_run.add_argument("--blueprint", default="", help="Blueprint ID override (skips label classification)")
    p_run.add_argument("--agent-id", default="", help="Agent identity posted in AgentCompletedEvent signal")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--verbose", action="store_true")
    # Executor mode args
    p_run.add_argument("--run-id", default="", help="Executor run ID (enables executor mode)")
    p_run.add_argument("--instruction", default="", help="Task instruction (executor mode)")
    p_run.add_argument("--context", default="{}", help="JSON context (executor mode)")
    p_run.add_argument("--callback-url", default="", help="Callback URL (executor mode)")
    p_run.add_argument("--callback-secret", default="", help="HMAC secret for callback (executor mode)")

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

    # --- harvest ---
    p_harvest = sub.add_parser("harvest", help="Backfill knowledge.db from all historical runs")
    p_harvest.add_argument("--target-repo", default="", help="Local path to target repo")

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
    elif args.command == "harvest":
        return cmd_harvest(args)
    return 1


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    """Full run: either issue mode or executor mode."""
    run_id = getattr(args, "run_id", "").strip()
    instruction = getattr(args, "instruction", "").strip()

    if run_id and instruction:
        return _cmd_run_executor(args)

    if instruction and not run_id:
        print("error: --instruction requires --run-id", file=sys.stderr)
        return 1

    # Issue mode: require --issue and --repo
    if not getattr(args, "issue", 0) or not getattr(args, "repo", ""):
        print(
            "error: --issue and --repo are required "
            "(or use --run-id + --instruction for executor mode)",
            file=sys.stderr,
        )
        return 1

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


def _cmd_run_executor(args: argparse.Namespace) -> int:
    """Executor-as-a-Service mode: blueprint + instruction + context from CLI args."""
    import json as _json

    from kevin.callback import CallbackClient

    cfg = build_config(
        repo=getattr(args, "repo", "") or "",
        target_repo=getattr(args, "target_repo", ""),
        dry_run=getattr(args, "dry_run", False),
        verbose=getattr(args, "verbose", False),
    )

    callback = CallbackClient(
        callback_url=getattr(args, "callback_url", ""),
        callback_secret=getattr(args, "callback_secret", ""),
    )

    # Validate inputs before reporting "running"
    blueprint_id = getattr(args, "blueprint", "").strip()
    if not blueprint_id:
        callback.report_status(
            run_id=args.run_id,
            status="failed",
            error_code="BLUEPRINT_NOT_FOUND",
            error_message="No --blueprint specified",
        )
        return 1

    try:
        bp_path = find_blueprint(cfg.blueprints_dir, blueprint_id)
        bp = load(bp_path)
    except FileNotFoundError:
        callback.report_status(
            run_id=args.run_id,
            status="failed",
            error_code="BLUEPRINT_NOT_FOUND",
            error_message=f"Blueprint not found: {blueprint_id}",
        )
        return 1

    # Parse context JSON
    raw_context = getattr(args, "context", "{}") or "{}"
    try:
        ctx: dict = _json.loads(raw_context)
    except _json.JSONDecodeError as exc:
        callback.report_status(
            run_id=args.run_id,
            status="failed",
            error_code="INVALID_CONTEXT",
            error_message=f"Malformed --context JSON: {exc}",
        )
        return 1

    # Report: running (after input validation passes)
    callback.report_status(run_id=args.run_id, status="running")
    repo_full = ctx.get("repo", cfg.repo_full_name)
    owner = repo_full.split("/")[0] if "/" in repo_full else cfg.repo_owner
    repo_name = repo_full.split("/")[-1] if "/" in repo_full else cfg.repo_name

    variables: dict[str, str] = {
        "instruction": args.instruction,
        "target_repo": str(cfg.target_repo),
        "repo_full": repo_full,
        "owner": owner,
        "repo": repo_name,
        "ref": ctx.get("ref", "main"),
        "run_id": args.run_id,
        # Compat: map instruction to issue fields so existing prompt templates work
        "issue_number": str(ctx.get("issue_number", "0")),
        "issue_title": args.instruction,
        "issue_body": args.instruction,
        "issue_labels": "",
        "learning_context": "",
    }
    # Pass through all context fields as template variables (e.g. pr_number, issue_number)
    for k, v in ctx.items():
        if k not in variables:
            variables[k] = str(v)

    # Create local run state
    state_mgr = StateManager(cfg.state_dir)
    run = state_mgr.create_run(
        blueprint_id=bp.blueprint_id,
        issue_number=int(variables.get("issue_number", "0")),
        repo=repo_full,
        variables=variables,
        blueprint_path=bp_path,
    )

    _log(cfg, f"Executor mode: run_id={args.run_id}, blueprint={bp.blueprint_id}")
    _log(cfg, f"  Local run: {run.run_id}")
    _log(cfg, f"  Blocks: {' → '.join(b.block_id for b in bp.blocks)}")

    # Execute blocks (reuse existing execution engine)
    exit_code = _execute_blocks(cfg, state_mgr, run, bp.blocks, variables)

    # Reload run to get latest block states
    run = state_mgr.load_run(run.run_id)
    block_results: list[dict[str, str]] = []
    for bid, bs in run.blocks.items():
        entry: dict[str, str] = {"block_id": bid, "status": bs.status}
        if bs.error:
            entry["error"] = bs.error
        block_results.append(entry)

    if exit_code == 0:
        callback.report_status(
            run_id=args.run_id,
            status="completed",
            result={
                "summary": f"Blueprint {bp.blueprint_id} completed",
                "blocks": block_results,
            },
        )
    else:
        failed_block = next((b for b in block_results if b["status"] == "failed"), None)
        callback.report_status(
            run_id=args.run_id,
            status="failed",
            error_code="BLOCK_FAILED",
            error_message=(
                f"Block {failed_block['block_id']} failed"
                if failed_block
                else "Unknown failure"
            ),
            result={"blocks": block_results},
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
            supported = ", ".join(config.intent_map.keys())
            from kevin.config import DEFAULT_LABEL_ALIASES
            alias_list = ", ".join(DEFAULT_LABEL_ALIASES.keys())
            error_msg = (
                f"Cannot classify issue #{args.issue}. "
                f"Labels: {issue.labels}. "
                f"Supported: {supported}. Aliases: {alias_list}. "
                "Add a supported label and re-trigger."
            )
            _err(f"Cannot classify issue #{args.issue}.")
            _err(f"  Labels found: {issue.labels}")
            _err(f"  Supported task-type labels: {supported}")
            _err(f"  Auto-mapped aliases: {alias_list}")
            _err("Add one of the above labels to the issue and re-trigger.")
            _notify_teams_early_failure(
                issue_number=args.issue,
                issue_title=issue.title,
                repo=args.repo,
                error=error_msg,
            )
            return 1
        blueprint_id = intent.blueprint_id
        confidence_tag = f" [{intent.confidence}]" if intent.confidence != "exact" else ""
        _log(config, f"  Intent: {blueprint_id} (matched: {intent.matched_label}{confidence_tag})")

    # 3. Load blueprint
    bp_path = find_blueprint(config.blueprints_dir, blueprint_id)
    blueprint = load(bp_path)
    _log(config, f"  Blueprint: {blueprint.blueprint_name} ({len(blueprint.blocks)} blocks)")

    # 4. Build variables
    variables = _build_variables(config, issue)

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
            variables["learning_context"] = ""
            _log(config, "  Learning: no historical data available")
    except Exception:
        variables["learning_context"] = ""
        _log(config, "  Learning: advisor unavailable (silent degradation)")

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


def cmd_harvest(args: argparse.Namespace) -> int:
    """Backfill knowledge.db from all historical runs in .kevin/runs/."""
    config = build_config(target_repo=args.target_repo)
    from kevin.learning.harvester import harvest_all
    result = harvest_all(config.knowledge_db, config.state_dir)
    print(f"Harvested: {result.harvested}  Skipped: {result.skipped_existing}  Failed: {result.failed_parse}")
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

def _now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _execute_blocks(
    config: KevinConfig,
    state_mgr: StateManager,
    run: RunState,
    blocks: list[Block],
    variables: dict[str, str],
    *,
    issue: Issue | None = None,
) -> int:
    """Execute blocks using the wave scheduler (sync wrapper)."""
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
    """Execute blocks grouped into waves with parallel dispatch."""
    from kevin.scheduler import compute_waves

    waves = compute_waves(blocks, variables)
    all_passed = True

    async def _run_single(block: Block) -> tuple[Block, bool]:
        """Run a single block with retry logic."""
        success = False
        bs = BlockState(block_id=block.block_id, status="running", runner=block.runner)
        bs.started_at = _now()
        state_mgr.update_block(run, bs)

        # Notify Teams: block started (real-time progress)
        if not config.dry_run:
            _notify_teams(config, run, blocks, issue, "running")

        result: BlockResult | None = None
        for attempt in range(block.max_retries + 1):
            if attempt > 0:
                _log(config, f"  {block.block_id}: Retry {attempt}/{block.max_retries}...")

            result = await run_block_async(
                block, variables,
                dry_run=config.dry_run,
                is_retry=attempt > 0,
                previous_result=result if attempt > 0 else None,
            )

            # Save logs
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

    # Execute wave by wave
    for wave in waves:
        block_ids = [b.block_id for b in wave.blocks]
        parallel_tag = " (parallel)" if len(wave.blocks) > 1 else ""
        _log(config, f"\n--- {wave.label}: [{', '.join(block_ids)}]{parallel_tag} ---")

        for block in wave.blocks:
            _log(config, f"  Block {block.block_id}: {block.name} (runner: {block.runner})")

        raw_results = await asyncio.gather(
            *[_run_single(b) for b in wave.blocks],
            return_exceptions=True,
        )

        # Normalize: exceptions become failures for the corresponding block
        wave_failed = False
        for i, raw in enumerate(raw_results):
            if isinstance(raw, BaseException):
                # Unexpected exception — record as block failure
                block = wave.blocks[i]
                bs = run.blocks.get(block.block_id, BlockState(block_id=block.block_id))
                bs.status = "failed"
                bs.completed_at = _now()
                bs.error = f"Unexpected error: {raw}"[:500]
                state_mgr.update_block(run, bs)
                _err(f"Block {block.block_id} raised exception: {raw}")
                wave_failed = True
            else:
                _, ok = raw
                if not ok:
                    wave_failed = True

        if wave_failed:
            all_passed = False
            break  # Stop subsequent waves

    # Finalize run
    final_status = "completed" if all_passed else "failed"
    state_mgr.complete_run(run, final_status)

    # Harvest learning (C1: silent degradation — knowledge_db doesn't exist yet)
    try:
        from kevin.learning import harvest_run
        harvest_run(config.knowledge_db, config.state_dir, run.run_id)
    except Exception:
        pass  # Learning never blocks main execution path

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


def _find_pr_for_issue(repo: str, issue_number: int) -> int | None:
    """Search for an open PR that closes the given issue.

    Agents must include 'Closes #N' in their PR body for this to work.
    Returns the PR number, or None if not found.
    """
    import subprocess
    import json as _json

    try:
        result = subprocess.run(
            [
                "gh", "pr", "list",
                "--repo", repo,
                "--state", "open",
                "--search", f"closes:#{issue_number}",
                "--json", "number",
                "--limit", "1",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        prs = _json.loads(result.stdout or "[]")
        return prs[0]["number"] if prs else None
    except Exception:
        return None


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

    If the agent opened a PR with 'Closes #N' in the body, the PR number is
    included so the Planning Agent can auto-merge non-HITL PRs.
    """
    import json

    payload: dict = {
        "event_type": "AgentCompletedEvent",
        "agent_id": agent_id,
        "status": "success" if success else "failure",
    }
    if blueprint_id:
        payload["blueprint_id"] = blueprint_id
    if success:
        pr_number = _find_pr_for_issue(repo, issue_number)
        if pr_number:
            payload["pr_number"] = pr_number

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
        headers = _teams_headers(data)
        req = Request(f"{teams_url}/api/notify", data=data, headers=headers)
        urlopen(req, timeout=10)
    except Exception as e:
        _log(config, f"  [WARN] Teams notify failed: {e}")


def _teams_headers(body: bytes) -> dict[str, str]:
    """Build headers for Teams Bot /api/notify, including HMAC signature if secret is set."""
    import hashlib
    import hmac as hmac_mod
    import os

    headers: dict[str, str] = {"Content-Type": "application/json"}
    secret = os.getenv("TEAMS_BOT_SECRET", "")
    if secret:
        sig = hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Bot-Signature"] = sig
    return headers


def _notify_teams_early_failure(
    *,
    issue_number: int,
    issue_title: str,
    repo: str,
    error: str,
) -> None:
    """Lightweight Teams notification for pre-run failures (e.g. classification error).

    Unlike _notify_teams(), this has no dependency on RunState or blocks —
    it fires before any run is created.
    """
    import json
    import os
    from urllib.request import Request, urlopen

    teams_url = os.getenv("TEAMS_BOT_URL", "")
    if not teams_url:
        return

    github_run_id = os.getenv("GITHUB_RUN_ID", "")
    github_server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    github_repo = os.getenv("GITHUB_REPOSITORY", "")
    logs_url = (
        f"{github_server}/{github_repo}/actions/runs/{github_run_id}"
        if github_run_id and github_repo
        else ""
    )

    payload: dict[str, object] = {
        "event": "run_failed",
        "run_id": f"gh-{github_run_id}" if github_run_id else "unknown",
        "issue_number": issue_number,
        "issue_title": issue_title,
        "repo": repo,
        "status": "failed",
        "error": error[:500],
        "blocks": [],
    }
    if logs_url:
        payload["logs_url"] = logs_url

    try:
        data = json.dumps(payload).encode()
        headers = _teams_headers(data)
        req = Request(f"{teams_url}/api/notify", data=data, headers=headers)
        urlopen(req, timeout=10)
    except Exception:
        pass  # Non-fatal — workflow step 9 is the backup


def _log(config: KevinConfig, msg: str) -> None:
    if config.verbose or config.dry_run:
        print(msg, file=sys.stderr)


def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())

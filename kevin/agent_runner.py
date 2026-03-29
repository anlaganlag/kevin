"""Execute Blueprint blocks via pluggable runners + validators.

Runners:
  - claude_cli: invoke `claude -p <prompt> --cwd <dir>`
  - shell: run a shell command
  - api_call: HTTP request (urllib, no extra deps)

Validators (run after block execution):
  - git_diff_check: ensure git has uncommitted/new changes
  - command: run a shell command, expect exit 0
  - file_exists: check a file/glob exists
"""

from __future__ import annotations

import glob as glob_mod
import selectors
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

# Seconds of silence before the heartbeat watchdog kills a subprocess.
# Claude CLI can think for a while (extended thinking), so this needs to be generous.
HEARTBEAT_TIMEOUT_SECONDS = 600

from kevin.blueprint_loader import Block, Validator
from kevin.prompt_template import render
from kevin.utils import resolve_cwd


@dataclass
class BlockResult:
    """Result of executing a single block."""

    block_id: str
    success: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    prompt: str = ""
    validator_results: list[dict[str, Any]] | None = None


# ---------------------------------------------------------------------------
# Runner dispatch
# ---------------------------------------------------------------------------

def run_block(
    block: Block,
    variables: dict[str, str],
    *,
    dry_run: bool = False,
    is_retry: bool = False,
    previous_result: BlockResult | None = None,
) -> BlockResult:
    """Execute a block using the appropriate runner, then validate.

    Args:
        is_retry: If True, run pre_check before execution to reset workspace.
                  First attempt skips pre_check to preserve prior block outputs.
        previous_result: Result from the previous failed attempt. When provided
                         and runner is claude_cli, error context is appended to
                         the prompt so the agent can adapt its strategy.
    """
    runner = block.runner or "claude_cli"

    if dry_run:
        return BlockResult(
            block_id=block.block_id,
            success=True,
            stdout=f"[dry-run] Would execute {runner} block {block.block_id}",
        )

    # Only run pre_check on retries to reset workspace to a clean state.
    # First attempt preserves prior block outputs (e.g. analysis.md from B1).
    if is_retry:
        pre_check_result = _run_pre_check(block, variables)
        if pre_check_result is not None:
            return pre_check_result

    runner_fn = RUNNERS.get(runner)
    if runner_fn is None:
        return BlockResult(
            block_id=block.block_id,
            success=False,
            stderr=f"Unknown runner: {runner}",
        )

    # Adaptive retry: inject previous failure context for claude_cli runner
    if previous_result is not None and runner == "claude_cli":
        retry_vars = {**variables}
        retry_vars["_previous_error"] = _build_retry_context(previous_result)
        result = runner_fn(block, retry_vars)
    else:
        result = runner_fn(block, variables)

    # Run validators if block execution succeeded
    if result.success and block.validators:
        cwd = _resolve_cwd(block.runner_config, variables)
        v_results = _run_validators(block.validators, variables, cwd)
        result.validator_results = v_results
        if any(not v["passed"] for v in v_results):
            result.success = False
            failed = [v for v in v_results if not v["passed"]]
            result.stderr += f"\nValidator failures: {failed}"

    return result


# ---------------------------------------------------------------------------
# Runner implementations
# ---------------------------------------------------------------------------

def _build_retry_context(previous_result: BlockResult) -> str:
    """Build a concise error summary from a failed BlockResult for adaptive retry."""
    parts: list[str] = []
    if previous_result.exit_code is not None:
        parts.append(f"Exit code: {previous_result.exit_code}")
    if previous_result.stderr:
        parts.append(f"Error:\n{previous_result.stderr[-500:]}")
    if previous_result.validator_results:
        failed = [v for v in previous_result.validator_results if not v.get("passed")]
        if failed:
            parts.append(f"Validator failures: {failed}")
    return "\n".join(parts)


def _run_claude_cli(block: Block, variables: dict[str, str]) -> BlockResult:
    """Execute a block via `claude -p <prompt> --cwd <dir>`.

    Supports runner_config.context_filter: a list of gitignore-style patterns
    to exclude from Claude CLI's context (e.g. ["node_modules", "dist", "*.min.js"]).
    When provided, a temporary .claudeignore file is written to the cwd before
    execution and cleaned up afterward.
    """
    prompt = render(block.prompt_template, variables)

    # Adaptive retry: append previous failure context so the agent can adjust
    retry_ctx = variables.get("_previous_error", "")
    if retry_ctx:
        prompt += (
            "\n\n⚠️ PREVIOUS ATTEMPT FAILED — analyse the error and use a different strategy:\n"
            + retry_ctx
        )
    cwd = _resolve_cwd(block.runner_config, variables)
    model = block.runner_config.get("model", "")
    context_filter: list[str] = block.runner_config.get("context_filter", [])

    cmd = [
        "claude", "-p", prompt,
        "--verbose",
        "--allowedTools", "Read,Write,Edit,Bash,Glob,Grep",
    ]
    if model:
        cmd.extend(["--model", model])
    # cwd is passed to subprocess.run, not as a CLI flag

    # Write temporary .claudeignore for context budget management
    claudeignore_path = cwd / ".claudeignore"
    created_claudeignore = False
    if context_filter and not claudeignore_path.exists():
        claudeignore_path.write_text(
            "# Auto-generated by Kevin (context budget management)\n"
            + "\n".join(context_filter)
            + "\n",
            encoding="utf-8",
        )
        created_claudeignore = True

    try:
        result = _subprocess_run(block.block_id, cmd, cwd=cwd, timeout=block.timeout)
        result.prompt = prompt
        return result
    finally:
        if created_claudeignore and claudeignore_path.exists():
            claudeignore_path.unlink()


def _run_shell(block: Block, variables: dict[str, str]) -> BlockResult:
    """Execute a shell command from runner_config.command."""
    command = block.runner_config.get("command", "")
    if not command:
        return BlockResult(
            block_id=block.block_id,
            success=False,
            stderr="shell runner requires runner_config.command",
        )

    command = render(command, variables)
    cwd = _resolve_cwd(block.runner_config, variables)

    return _subprocess_run(
        block.block_id,
        ["bash", "-c", command],
        cwd=cwd,
        timeout=block.timeout,
    )


def _run_api_call(block: Block, variables: dict[str, str]) -> BlockResult:
    """Execute an HTTP API call (no extra deps — uses urllib)."""
    config = block.runner_config
    method = config.get("method", "GET")
    url = render(config.get("url", ""), variables)
    headers = {k: render(str(v), variables) for k, v in config.get("headers", {}).items()}
    body = config.get("body")

    if not url:
        return BlockResult(
            block_id=block.block_id,
            success=False,
            stderr="api_call runner requires runner_config.url",
        )

    try:
        import json
        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, headers=headers, method=method)
        with urlopen(req, timeout=block.timeout) as resp:
            resp_body = resp.read().decode()
            return BlockResult(
                block_id=block.block_id,
                success=resp.status < 400,
                exit_code=resp.status,
                stdout=resp_body,
            )
    except Exception as exc:
        return BlockResult(
            block_id=block.block_id,
            success=False,
            stderr=str(exc),
        )


RUNNERS = {
    "claude_cli": _run_claude_cli,
    "shell": _run_shell,
    "api_call": _run_api_call,
}


# ---------------------------------------------------------------------------
# Pre-check (idempotency reset)
# ---------------------------------------------------------------------------

def _run_pre_check(block: Block, variables: dict[str, str]) -> BlockResult | None:
    """Run a block's pre_check command if defined.

    Returns None on success (or if no pre_check), BlockResult on failure.
    The pre_check is a shell command that resets the workspace to a clean state
    before (re-)executing the block — critical for resume/retry idempotency.
    """
    if not block.pre_check:
        return None

    command = render(block.pre_check, variables)
    cwd = _resolve_cwd(block.runner_config, variables)

    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=30,
    )

    if result.returncode != 0:
        return BlockResult(
            block_id=block.block_id,
            success=False,
            exit_code=result.returncode,
            stderr=f"pre_check failed: {result.stderr}",
        )

    return None


# ---------------------------------------------------------------------------
# Validator implementations
# ---------------------------------------------------------------------------

def _run_validators(
    validators: list[Validator],
    variables: dict[str, str],
    cwd: Path,
) -> list[dict[str, Any]]:
    """Run all validators and return results."""
    results: list[dict[str, Any]] = []
    for v in validators:
        fn = VALIDATORS.get(v.type)
        if fn is None:
            results.append({"type": v.type, "passed": False, "error": f"Unknown validator: {v.type}"})
            continue
        results.append(fn(v, variables, cwd))
    return results


def _validate_git_diff(v: Validator, variables: dict[str, str], cwd: Path) -> dict[str, Any]:
    """Check that the current branch has file changes vs main.

    Checks three sources (any non-zero count passes):
    1. Uncommitted changes (git status --porcelain)
    2. Committed changes vs main (git diff main...HEAD --name-only)
    3. Committed changes vs HEAD~ (git diff HEAD~1 --name-only) for single-commit branches
    """
    min_files = v.params.get("min_files_changed", 1)

    # Check 1: uncommitted changes
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=str(cwd), timeout=10,
    )
    uncommitted = len([l for l in status.stdout.strip().split("\n") if l.strip()])

    # Check 2: committed diff vs main
    diff_vs_main = subprocess.run(
        ["git", "diff", "main...HEAD", "--name-only"],
        capture_output=True, text=True, cwd=str(cwd), timeout=10,
    )
    committed_vs_main = len([l for l in diff_vs_main.stdout.strip().split("\n") if l.strip()])

    # Check 3: diff vs previous commit (fallback if main is the same commit)
    diff_vs_prev = subprocess.run(
        ["git", "diff", "HEAD~1", "--name-only"],
        capture_output=True, text=True, cwd=str(cwd), timeout=10,
    )
    committed_vs_prev = len([l for l in diff_vs_prev.stdout.strip().split("\n") if l.strip()])

    changed_files = max(uncommitted, committed_vs_main, committed_vs_prev)
    passed = changed_files >= min_files
    return {
        "type": "git_diff_check",
        "passed": passed,
        "files_changed": changed_files,
        "uncommitted": uncommitted,
        "committed_vs_main": committed_vs_main,
        "expected_min": min_files,
    }


def _validate_command(v: Validator, variables: dict[str, str], cwd: Path) -> dict[str, Any]:
    """Run a shell command and check exit code == 0."""
    command = render(v.params.get("run", ""), variables)
    timeout = v.params.get("timeout", 60)
    if not command:
        return {"type": "command", "passed": False, "error": "No command specified"}

    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True, text=True, cwd=str(cwd), timeout=timeout,
    )
    return {
        "type": "command",
        "passed": result.returncode == 0,
        "command": command,
        "exit_code": result.returncode,
        "stderr": result.stderr[:500] if result.stderr else "",
    }


def _validate_file_exists(v: Validator, variables: dict[str, str], cwd: Path) -> dict[str, Any]:
    """Check that a file or glob pattern matches at least one file."""
    pattern = render(v.params.get("path", ""), variables)
    if not pattern:
        return {"type": "file_exists", "passed": False, "error": "No path specified"}

    # Try as literal path first
    full_path = cwd / pattern
    if full_path.exists():
        return {"type": "file_exists", "passed": True, "path": str(full_path)}

    # Try as glob
    matches = glob_mod.glob(str(cwd / pattern))
    return {
        "type": "file_exists",
        "passed": len(matches) > 0,
        "pattern": pattern,
        "matches": len(matches),
    }


VALIDATORS = {
    "git_diff_check": _validate_git_diff,
    "command": _validate_command,
    "file_exists": _validate_file_exists,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_cwd(runner_config: dict[str, Any], variables: dict[str, str]) -> Path:
    """Resolve the working directory from runner_config or default to cwd."""
    return resolve_cwd(runner_config, variables)


def _subprocess_run(
    block_id: str,
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> BlockResult:
    """Run a subprocess with non-blocking I/O and heartbeat watchdog.

    Uses selectors to monitor both stdout and stderr without blocking.
    If no output on either stream for HEARTBEAT_TIMEOUT_SECONDS, the process
    is killed (prevents "fake death" in CI environments like GHA).
    """
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(cwd),
        )
    except FileNotFoundError as exc:
        return BlockResult(
            block_id=block_id,
            success=False,
            stderr=f"Command not found: {exc}",
        )

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    start_time = time.monotonic()
    last_output_time = start_time
    heartbeat_limit = min(HEARTBEAT_TIMEOUT_SECONDS, timeout)

    # Register both stdout and stderr for non-blocking reads
    sel = selectors.DefaultSelector()
    try:
        if proc.stdout:
            sel.register(proc.stdout, selectors.EVENT_READ, "stdout")
        if proc.stderr:
            sel.register(proc.stderr, selectors.EVENT_READ, "stderr")

        while sel.get_map():
            elapsed = time.monotonic() - start_time
            if elapsed > timeout:
                proc.kill()
                proc.wait()
                return BlockResult(
                    block_id=block_id,
                    success=False,
                    stdout="".join(stdout_chunks),
                    stderr=f"Timeout after {timeout}s\n{''.join(stderr_chunks)}",
                )

            silence = time.monotonic() - last_output_time
            if silence > heartbeat_limit:
                proc.kill()
                proc.wait()
                return BlockResult(
                    block_id=block_id,
                    success=False,
                    stdout="".join(stdout_chunks),
                    stderr=f"Heartbeat timeout: no output for {heartbeat_limit}s\n{''.join(stderr_chunks)}",
                )

            # Wait up to 1s for data on either stream
            ready = sel.select(timeout=1.0)
            for key, _ in ready:
                chunk = key.fileobj.read1(8192) if hasattr(key.fileobj, "read1") else key.fileobj.readline()
                if chunk:
                    if key.data == "stdout":
                        stdout_chunks.append(chunk)
                    else:
                        stderr_chunks.append(chunk)
                    last_output_time = time.monotonic()
                else:
                    # EOF on this stream
                    sel.unregister(key.fileobj)

        proc.wait()
        return BlockResult(
            block_id=block_id,
            success=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout="".join(stdout_chunks),
            stderr="".join(stderr_chunks),
        )

    except Exception as exc:
        proc.kill()
        proc.wait()
        return BlockResult(
            block_id=block_id,
            success=False,
            stderr=f"Unexpected error: {exc}",
        )
    finally:
        sel.close()


# ---------------------------------------------------------------------------
# Async wrapper
# ---------------------------------------------------------------------------

async def run_block_async(
    block: Block,
    variables: dict[str, str],
    *,
    dry_run: bool = False,
    is_retry: bool = False,
    previous_result: BlockResult | None = None,
) -> BlockResult:
    """Async wrapper — runs synchronous run_block in a thread pool.

    run_block() internals (subprocess, heartbeat, validators) are unchanged.
    Only the scheduling layer is async. Uses asyncio.to_thread (Python 3.11+).
    """
    import asyncio
    return await asyncio.to_thread(
        run_block, block, variables,
        dry_run=dry_run, is_retry=is_retry, previous_result=previous_result,
    )

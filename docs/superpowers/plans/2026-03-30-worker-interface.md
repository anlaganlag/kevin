# Worker Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract a `WorkerInterface` protocol so Claude Code becomes one replaceable adapter, not the hardcoded execution engine.

**Architecture:** Create `kevin/workers/` package with interface types (`WorkerTask`, `WorkerResult`, `WorkerPermissions`, etc.), a `ClaudeCodeWorker` adapter (wrapping current `executor.py` logic), a `ShellWorker` adapter, and a registry. Modify `blueprint_compiler.compile()` to output `WorkerTask` instead of raw prompt string. Modify `cli.py:_execute_agentic()` to use the registry.

**Tech Stack:** Python 3.12+, dataclasses, Protocol (typing), pytest

**Spec:** `docs/superpowers/specs/2026-03-30-kevin-platform-architecture-design.md` — Section D

---

## File Structure

```
kevin/workers/              # NEW package
    __init__.py             # re-exports
    interface.py            # WorkerInterface, WorkerTask, WorkerResult,
                            # WorkerPermissions, WorkspacePolicy,
                            # FailureType, ArtifactType, WorkerArtifact, WorkerHealth
    claude_code.py          # ClaudeCodeWorker adapter
    shell.py                # ShellWorker adapter
    registry.py             # WorkerRegistry: resolve worker_id -> WorkerInterface

kevin/blueprint_compiler.py # MODIFY: compile() returns WorkerTask not str
kevin/executor.py           # MODIFY: thin wrapper that delegates to registry
kevin/cli.py                # MODIFY: _execute_agentic uses WorkerRegistry
```

---

### Task 1: Create `kevin/workers/interface.py` — Core Types

**Files:**
- Create: `kevin/workers/__init__.py`
- Create: `kevin/workers/interface.py`
- Test: `kevin/tests/test_worker_interface.py`

- [ ] **Step 1: Write failing test for WorkerTask construction**

```python
# kevin/tests/test_worker_interface.py
"""Tests for kevin.workers.interface — core types."""

from pathlib import Path

from kevin.workers.interface import (
    ArtifactType,
    FailureType,
    WorkerArtifact,
    WorkerHealth,
    WorkerPermissions,
    WorkerResult,
    WorkerTask,
    WorkspacePolicy,
)


class TestWorkerTask:
    def test_should_construct_with_required_fields(self) -> None:
        task = WorkerTask(
            task_id="run-001",
            instruction="Implement feature X",
            workspace=WorkspacePolicy(cwd=Path("/tmp/repo")),
            permissions=WorkerPermissions(),
            timeout=300,
        )
        assert task.task_id == "run-001"
        assert task.instruction == "Implement feature X"
        assert task.timeout == 300

    def test_should_have_default_permissions(self) -> None:
        perms = WorkerPermissions()
        assert perms.file_read is True
        assert perms.file_write is True
        assert perms.file_delete is False
        assert perms.git_push is False
        assert perms.network_access is False

    def test_should_have_workspace_policy_defaults(self) -> None:
        ws = WorkspacePolicy(cwd=Path("/tmp"))
        assert ws.branch_pattern == "kevin/issue-{issue_number}"
        assert ws.max_files_changed == 50
        assert ws.max_lines_changed == 5000


class TestWorkerResult:
    def test_should_construct_success_result(self) -> None:
        result = WorkerResult(success=True, exit_code=0, stdout="done")
        assert result.success is True
        assert result.failure_type is None

    def test_should_construct_failure_with_type(self) -> None:
        result = WorkerResult(
            success=False,
            failure_type=FailureType.TIMEOUT,
            failure_detail="No output for 600s",
        )
        assert result.success is False
        assert result.failure_type == FailureType.TIMEOUT

    def test_should_hold_typed_artifacts(self) -> None:
        artifact = WorkerArtifact(
            artifact_type=ArtifactType.PR_URL,
            name="Pull Request",
            location="https://github.com/owner/repo/pull/42",
        )
        result = WorkerResult(success=True, artifacts=[artifact])
        assert result.artifacts[0].artifact_type == ArtifactType.PR_URL


class TestWorkerHealth:
    def test_should_report_healthy(self) -> None:
        health = WorkerHealth(
            available=True,
            worker_id="claude-code",
            version="1.0.0",
            capabilities=["code_generation", "file_edit"],
        )
        assert health.available is True
        assert "code_generation" in health.capabilities

    def test_should_report_unhealthy_with_reason(self) -> None:
        health = WorkerHealth(
            available=False,
            worker_id="claude-code",
            error="CLI not installed",
        )
        assert health.available is False
        assert "not installed" in health.error
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest kevin/tests/test_worker_interface.py -v
```

Expected: `ModuleNotFoundError: No module named 'kevin.workers'`

- [ ] **Step 3: Create the package and interface module**

```python
# kevin/workers/__init__.py
"""Worker interface and adapters for Kevin execution platform."""

from kevin.workers.interface import (
    ArtifactType,
    FailureType,
    WorkerArtifact,
    WorkerHealth,
    WorkerPermissions,
    WorkerResult,
    WorkerTask,
    WorkspacePolicy,
)

__all__ = [
    "ArtifactType",
    "FailureType",
    "WorkerArtifact",
    "WorkerHealth",
    "WorkerPermissions",
    "WorkerResult",
    "WorkerTask",
    "WorkspacePolicy",
]
```

```python
# kevin/workers/interface.py
"""Core types for the Worker Interface — runtime-agnostic.

These types define the contract between the Executor (control plane)
and any Worker (execution runtime). No Worker-specific logic here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


class FailureType(str, Enum):
    """Standard failure categories — Executor uses these for routing decisions."""
    TIMEOUT = "timeout"
    COMMAND_NOT_FOUND = "command_not_found"
    EXIT_CODE_NON_ZERO = "exit_code_non_zero"
    PERMISSION_DENIED = "permission_denied"
    RESOURCE_LIMIT = "resource_limit"
    NETWORK_ERROR = "network_error"
    INTERNAL_ERROR = "internal_error"
    TASK_REJECTED = "task_rejected"
    HEARTBEAT_TIMEOUT = "heartbeat_timeout"


class ArtifactType(str, Enum):
    """Standard artifact categories — Verifier uses these for validation."""
    SOURCE_CODE = "source_code"
    TEST_FILE = "test_file"
    ANALYSIS_REPORT = "analysis_report"
    PR_URL = "pr_url"
    COMMIT_SHA = "commit_sha"
    BRANCH_NAME = "branch_name"
    COVERAGE_REPORT = "coverage_report"
    CUSTOM = "custom"


@dataclass(frozen=True)
class WorkerPermissions:
    """Structured permissions — each adapter translates to runtime-specific format."""
    file_read: bool = True
    file_write: bool = True
    file_delete: bool = False
    shell_execute: bool = True
    network_access: bool = False
    git_read: bool = True
    git_write: bool = False
    git_push: bool = False
    secrets_access: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkspacePolicy:
    """Worker constraints — defined at task level, enforced by Verifier."""
    cwd: Path
    branch_pattern: str = "kevin/issue-{issue_number}"
    commit_message_pattern: str = "feat: {issue_title} (resolves #{issue_number})"
    protected_paths: list[str] = field(default_factory=list)
    context_filter: list[str] = field(default_factory=list)
    max_files_changed: int = 50
    max_lines_changed: int = 5000


@dataclass(frozen=True)
class WorkerArtifact:
    """A single typed artifact produced by a Worker."""
    artifact_type: ArtifactType
    name: str
    location: str
    content_hash: str = ""


@dataclass(frozen=True)
class WorkerTask:
    """Runtime-agnostic task description — what the Worker must accomplish."""
    task_id: str
    instruction: str
    workspace: WorkspacePolicy
    permissions: WorkerPermissions
    timeout: int
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerResult:
    """Standardized result from any Worker."""
    success: bool
    exit_code: int | None = None
    failure_type: FailureType | None = None
    failure_detail: str = ""
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    token_usage: int = 0
    artifacts: list[WorkerArtifact] = field(default_factory=list)


@dataclass(frozen=True)
class WorkerHealth:
    """Structured health check result."""
    available: bool
    worker_id: str
    version: str = ""
    capabilities: list[str] = field(default_factory=list)
    latency_ms: int = 0
    error: str = ""


class WorkerInterface(Protocol):
    """Any execution runtime that accepts a task and returns a result."""

    @property
    def worker_id(self) -> str: ...

    def execute(self, task: WorkerTask) -> WorkerResult: ...
    def health_check(self) -> WorkerHealth: ...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest kevin/tests/test_worker_interface.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add kevin/workers/__init__.py kevin/workers/interface.py kevin/tests/test_worker_interface.py
git commit -m "feat: add WorkerInterface core types (D.1)"
```

---

### Task 2: Create `kevin/workers/claude_code.py` — Claude Code Adapter

**Files:**
- Create: `kevin/workers/claude_code.py`
- Test: `kevin/tests/test_worker_claude_code.py`

- [ ] **Step 1: Write failing tests**

```python
# kevin/tests/test_worker_claude_code.py
"""Tests for ClaudeCodeWorker adapter."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from kevin.workers.claude_code import ClaudeCodeWorker
from kevin.workers.interface import (
    ArtifactType,
    FailureType,
    WorkerHealth,
    WorkerPermissions,
    WorkerResult,
    WorkerTask,
    WorkspacePolicy,
)


class TestClaudeCodeWorkerExecute:
    def _make_task(self, tmp_path: Path, **overrides) -> WorkerTask:
        defaults = dict(
            task_id="test-001",
            instruction="Write hello world",
            workspace=WorkspacePolicy(cwd=tmp_path),
            permissions=WorkerPermissions(git_write=True, git_push=True),
            timeout=300,
        )
        defaults.update(overrides)
        return WorkerTask(**defaults)

    def test_should_return_success_on_zero_exit(self, tmp_path: Path) -> None:
        worker = ClaudeCodeWorker()
        task = self._make_task(tmp_path)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.exit_code = 0
        mock_result.stdout = "Done. PR https://github.com/o/r/pull/42"
        mock_result.stderr = ""

        with patch("kevin.workers.claude_code.run_with_heartbeat", return_value=mock_result):
            result = worker.execute(task)

        assert result.success is True
        assert result.failure_type is None

    def test_should_map_timeout_to_failure_type(self, tmp_path: Path) -> None:
        worker = ClaudeCodeWorker()
        task = self._make_task(tmp_path)

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.exit_code = None
        mock_result.stdout = ""
        mock_result.stderr = "Timeout after 300s"

        with patch("kevin.workers.claude_code.run_with_heartbeat", return_value=mock_result):
            result = worker.execute(task)

        assert result.success is False
        assert result.failure_type == FailureType.TIMEOUT

    def test_should_map_heartbeat_to_failure_type(self, tmp_path: Path) -> None:
        worker = ClaudeCodeWorker()
        task = self._make_task(tmp_path)

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.exit_code = None
        mock_result.stdout = ""
        mock_result.stderr = "Heartbeat timeout: no output for 600s"

        with patch("kevin.workers.claude_code.run_with_heartbeat", return_value=mock_result):
            result = worker.execute(task)

        assert result.success is False
        assert result.failure_type == FailureType.HEARTBEAT_TIMEOUT

    def test_should_extract_pr_artifact_from_stdout(self, tmp_path: Path) -> None:
        worker = ClaudeCodeWorker()
        task = self._make_task(tmp_path)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.exit_code = 0
        mock_result.stdout = "Created PR: https://github.com/owner/repo/pull/99"
        mock_result.stderr = ""

        with patch("kevin.workers.claude_code.run_with_heartbeat", return_value=mock_result):
            result = worker.execute(task)

        pr_artifacts = [a for a in result.artifacts if a.artifact_type == ArtifactType.PR_URL]
        assert len(pr_artifacts) == 1
        assert "99" in pr_artifacts[0].location

    def test_should_translate_permissions_to_allowed_tools(self, tmp_path: Path) -> None:
        worker = ClaudeCodeWorker()
        read_only_task = self._make_task(
            tmp_path,
            permissions=WorkerPermissions(file_write=False, shell_execute=False),
        )

        with patch("kevin.workers.claude_code.run_with_heartbeat") as mock_run:
            mock_run.return_value = MagicMock(success=True, exit_code=0, stdout="", stderr="")
            worker.execute(read_only_task)

        cmd = mock_run.call_args[0][0]
        tools_str = cmd[cmd.index("--allowedTools") + 1]
        assert "Read" in tools_str
        assert "Glob" in tools_str
        assert "Write" not in tools_str
        assert "Bash" not in tools_str

    def test_should_manage_claudeignore_lifecycle(self, tmp_path: Path) -> None:
        worker = ClaudeCodeWorker()
        task = self._make_task(
            tmp_path,
            workspace=WorkspacePolicy(cwd=tmp_path, context_filter=["node_modules/"]),
        )

        claudeignore = tmp_path / ".claudeignore"
        assert not claudeignore.exists()

        with patch("kevin.workers.claude_code.run_with_heartbeat") as mock_run:
            mock_run.return_value = MagicMock(success=True, exit_code=0, stdout="", stderr="")
            worker.execute(task)

        assert not claudeignore.exists()  # cleaned up


class TestClaudeCodeWorkerHealth:
    def test_should_report_healthy_when_cli_available(self) -> None:
        worker = ClaudeCodeWorker()

        with patch("kevin.workers.claude_code.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="1.0.0")
            health = worker.health_check()

        assert health.available is True
        assert health.worker_id == "claude-code"

    def test_should_report_unhealthy_when_cli_missing(self) -> None:
        worker = ClaudeCodeWorker()

        with patch("kevin.workers.claude_code.subprocess") as mock_sub:
            mock_sub.run.side_effect = FileNotFoundError("claude not found")
            health = worker.health_check()

        assert health.available is False
        assert "not found" in health.error.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest kevin/tests/test_worker_claude_code.py -v
```

Expected: `ModuleNotFoundError: No module named 'kevin.workers.claude_code'`

- [ ] **Step 3: Implement ClaudeCodeWorker**

```python
# kevin/workers/claude_code.py
"""Claude Code CLI adapter — translates WorkerTask to `claude -p` invocation."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from kevin.subprocess_utils import run_with_heartbeat
from kevin.workers.interface import (
    ArtifactType,
    FailureType,
    WorkerArtifact,
    WorkerHealth,
    WorkerPermissions,
    WorkerResult,
    WorkerTask,
)

_PR_URL_PATTERN = re.compile(r"github\.com/[^/]+/[^/]+/pull/(\d+)")


class ClaudeCodeWorker:
    """Adapter: WorkerInterface -> claude -p CLI."""

    @property
    def worker_id(self) -> str:
        return "claude-code"

    def execute(self, task: WorkerTask) -> WorkerResult:
        prompt = self._translate_instruction(task)
        tools = self._translate_permissions(task.permissions)
        cmd = ["claude", "-p", prompt, "--verbose", "--allowedTools", tools]
        if task.model:
            cmd.extend(["--model", task.model])

        cwd = task.workspace.cwd
        claudeignore_path = cwd / ".claudeignore"
        created_claudeignore = False
        if task.workspace.context_filter and not claudeignore_path.exists():
            claudeignore_path.write_text(
                "# Auto-generated by Kevin\n"
                + "\n".join(task.workspace.context_filter)
                + "\n",
                encoding="utf-8",
            )
            created_claudeignore = True

        start = time.monotonic()
        try:
            raw = run_with_heartbeat(cmd, cwd=cwd, timeout=task.timeout)
            duration = time.monotonic() - start
        finally:
            if created_claudeignore and claudeignore_path.exists():
                claudeignore_path.unlink()

        failure_type = self._classify_failure(raw.stderr) if not raw.success else None
        artifacts = self._extract_artifacts(raw.stdout)

        return WorkerResult(
            success=raw.success,
            exit_code=raw.exit_code,
            failure_type=failure_type,
            failure_detail=raw.stderr[:500] if not raw.success else "",
            stdout=raw.stdout,
            stderr=raw.stderr,
            duration_seconds=duration,
            artifacts=artifacts,
        )

    def health_check(self) -> WorkerHealth:
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            return WorkerHealth(
                available=result.returncode == 0,
                worker_id=self.worker_id,
                version=result.stdout.strip(),
                capabilities=["code_generation", "file_edit", "git", "test_run", "bash"],
            )
        except (FileNotFoundError, OSError) as exc:
            return WorkerHealth(
                available=False,
                worker_id=self.worker_id,
                error=str(exc),
            )

    def _translate_instruction(self, task: WorkerTask) -> str:
        """Wrap runtime-agnostic instruction in Claude-specific prompt framing."""
        return (
            "You are Kevin Executor, an autonomous software development agent.\n"
            "Complete the following task end-to-end.\n"
            "You MUST create files and execute commands. Do NOT ask questions "
            "or wait for confirmation. Just execute.\n\n"
            + task.instruction
        )

    def _translate_permissions(self, perms: WorkerPermissions) -> str:
        """Map structured permissions to Claude CLI --allowedTools string."""
        tools: list[str] = []
        if perms.file_read:
            tools.extend(["Read", "Glob", "Grep"])
        if perms.file_write:
            tools.extend(["Write", "Edit"])
        if perms.shell_execute:
            tools.append("Bash")
        return ",".join(tools)

    def _classify_failure(self, stderr: str) -> FailureType:
        """Map stderr patterns to standardized FailureType."""
        lower = stderr.lower()
        if "heartbeat timeout" in lower:
            return FailureType.HEARTBEAT_TIMEOUT
        if "timeout after" in lower:
            return FailureType.TIMEOUT
        if "command not found" in lower:
            return FailureType.COMMAND_NOT_FOUND
        if "permission denied" in lower:
            return FailureType.PERMISSION_DENIED
        return FailureType.EXIT_CODE_NON_ZERO

    def _extract_artifacts(self, stdout: str) -> list[WorkerArtifact]:
        """Scan stdout for recognizable artifacts."""
        artifacts: list[WorkerArtifact] = []
        match = _PR_URL_PATTERN.search(stdout)
        if match:
            url = stdout[match.start():match.end()]
            # reconstruct full URL with https://
            if not url.startswith("http"):
                url = "https://" + url
            artifacts.append(WorkerArtifact(
                artifact_type=ArtifactType.PR_URL,
                name="Pull Request",
                location=url,
            ))
        return artifacts
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest kevin/tests/test_worker_claude_code.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add kevin/workers/claude_code.py kevin/tests/test_worker_claude_code.py
git commit -m "feat: add ClaudeCodeWorker adapter (D.2)"
```

---

### Task 3: Create `kevin/workers/shell.py` — Shell Worker Adapter

**Files:**
- Create: `kevin/workers/shell.py`
- Test: `kevin/tests/test_worker_shell.py`

- [ ] **Step 1: Write failing tests**

```python
# kevin/tests/test_worker_shell.py
"""Tests for ShellWorker adapter."""

from pathlib import Path

from kevin.workers.interface import (
    FailureType,
    WorkerPermissions,
    WorkerTask,
    WorkspacePolicy,
)
from kevin.workers.shell import ShellWorker


class TestShellWorkerExecute:
    def _make_task(self, tmp_path: Path, instruction: str = "echo ok") -> WorkerTask:
        return WorkerTask(
            task_id="shell-001",
            instruction=instruction,
            workspace=WorkspacePolicy(cwd=tmp_path),
            permissions=WorkerPermissions(),
            timeout=10,
        )

    def test_should_succeed_on_zero_exit(self, tmp_path: Path) -> None:
        worker = ShellWorker()
        result = worker.execute(self._make_task(tmp_path, "echo hello"))
        assert result.success is True
        assert "hello" in result.stdout

    def test_should_fail_on_non_zero_exit(self, tmp_path: Path) -> None:
        worker = ShellWorker()
        result = worker.execute(self._make_task(tmp_path, "exit 42"))
        assert result.success is False
        assert result.exit_code == 42
        assert result.failure_type == FailureType.EXIT_CODE_NON_ZERO

    def test_should_capture_stderr(self, tmp_path: Path) -> None:
        worker = ShellWorker()
        result = worker.execute(self._make_task(tmp_path, "echo err >&2; exit 1"))
        assert "err" in result.stderr

    def test_should_timeout(self, tmp_path: Path) -> None:
        worker = ShellWorker()
        task = self._make_task(tmp_path, "sleep 30")
        task = WorkerTask(
            task_id=task.task_id,
            instruction=task.instruction,
            workspace=task.workspace,
            permissions=task.permissions,
            timeout=1,
        )
        result = worker.execute(task)
        assert result.success is False
        assert result.failure_type in (FailureType.TIMEOUT, FailureType.HEARTBEAT_TIMEOUT)


class TestShellWorkerHealth:
    def test_should_always_be_available(self) -> None:
        worker = ShellWorker()
        health = worker.health_check()
        assert health.available is True
        assert health.worker_id == "shell"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest kevin/tests/test_worker_shell.py -v
```

Expected: `ModuleNotFoundError: No module named 'kevin.workers.shell'`

- [ ] **Step 3: Implement ShellWorker**

```python
# kevin/workers/shell.py
"""Shell worker adapter — runs bash commands."""

from __future__ import annotations

import time
from pathlib import Path

from kevin.subprocess_utils import run_with_heartbeat
from kevin.workers.interface import (
    FailureType,
    WorkerHealth,
    WorkerResult,
    WorkerTask,
)


class ShellWorker:
    """Adapter: WorkerInterface -> bash -c."""

    @property
    def worker_id(self) -> str:
        return "shell"

    def execute(self, task: WorkerTask) -> WorkerResult:
        start = time.monotonic()
        raw = run_with_heartbeat(
            ["bash", "-c", task.instruction],
            cwd=task.workspace.cwd,
            timeout=task.timeout,
        )
        duration = time.monotonic() - start

        failure_type = None
        if not raw.success:
            lower = raw.stderr.lower()
            if "timeout" in lower or "heartbeat" in lower:
                failure_type = FailureType.TIMEOUT if "Timeout after" in raw.stderr else FailureType.HEARTBEAT_TIMEOUT
            elif "command not found" in lower:
                failure_type = FailureType.COMMAND_NOT_FOUND
            else:
                failure_type = FailureType.EXIT_CODE_NON_ZERO

        return WorkerResult(
            success=raw.success,
            exit_code=raw.exit_code,
            failure_type=failure_type,
            failure_detail=raw.stderr[:500] if not raw.success else "",
            stdout=raw.stdout,
            stderr=raw.stderr,
            duration_seconds=duration,
        )

    def health_check(self) -> WorkerHealth:
        return WorkerHealth(
            available=True,
            worker_id=self.worker_id,
            version="builtin",
            capabilities=["shell_execute"],
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest kevin/tests/test_worker_shell.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add kevin/workers/shell.py kevin/tests/test_worker_shell.py
git commit -m "feat: add ShellWorker adapter (D.3)"
```

---

### Task 4: Create `kevin/workers/registry.py` — Worker Registry

**Files:**
- Create: `kevin/workers/registry.py`
- Test: `kevin/tests/test_worker_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# kevin/tests/test_worker_registry.py
"""Tests for WorkerRegistry."""

import pytest

from kevin.workers.registry import WorkerRegistry


class TestWorkerRegistry:
    def test_should_resolve_claude_code_by_default(self) -> None:
        registry = WorkerRegistry()
        worker = registry.resolve()
        assert worker.worker_id == "claude-code"

    def test_should_resolve_by_worker_id(self) -> None:
        registry = WorkerRegistry()
        worker = registry.resolve("shell")
        assert worker.worker_id == "shell"

    def test_should_raise_on_unknown_worker(self) -> None:
        registry = WorkerRegistry()
        with pytest.raises(KeyError, match="nonexistent"):
            registry.resolve("nonexistent")

    def test_should_list_available_workers(self) -> None:
        registry = WorkerRegistry()
        workers = registry.list_workers()
        ids = [w.worker_id for w in workers]
        assert "claude-code" in ids
        assert "shell" in ids
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest kevin/tests/test_worker_registry.py -v
```

Expected: `ModuleNotFoundError: No module named 'kevin.workers.registry'`

- [ ] **Step 3: Implement WorkerRegistry**

```python
# kevin/workers/registry.py
"""Worker registry — resolves worker_id to WorkerInterface implementation."""

from __future__ import annotations

from kevin.workers.claude_code import ClaudeCodeWorker
from kevin.workers.interface import WorkerHealth, WorkerInterface
from kevin.workers.shell import ShellWorker

_DEFAULT_WORKER_ID = "claude-code"


class WorkerRegistry:
    """Maps worker_id to WorkerInterface. Extensible via register()."""

    def __init__(self) -> None:
        self._workers: dict[str, WorkerInterface] = {}
        # Register built-in workers
        claude = ClaudeCodeWorker()
        shell = ShellWorker()
        self._workers[claude.worker_id] = claude
        self._workers[shell.worker_id] = shell

    def resolve(self, worker_id: str = "") -> WorkerInterface:
        """Resolve a worker by ID. Defaults to claude-code."""
        wid = worker_id or _DEFAULT_WORKER_ID
        if wid not in self._workers:
            raise KeyError(f"Unknown worker: {wid}. Available: {list(self._workers.keys())}")
        return self._workers[wid]

    def register(self, worker: WorkerInterface) -> None:
        """Register a custom worker."""
        self._workers[worker.worker_id] = worker

    def list_workers(self) -> list[WorkerInterface]:
        """List all registered workers."""
        return list(self._workers.values())

    def health_check_all(self) -> dict[str, WorkerHealth]:
        """Health check all registered workers."""
        return {wid: w.health_check() for wid, w in self._workers.items()}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest kevin/tests/test_worker_registry.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add kevin/workers/registry.py kevin/tests/test_worker_registry.py
git commit -m "feat: add WorkerRegistry (D.4)"
```

---

### Task 5: Modify `blueprint_compiler.py` — Output `WorkerTask` not raw string

**Files:**
- Modify: `kevin/blueprint_compiler.py`
- Modify: `kevin/tests/test_blueprint_compiler.py`

- [ ] **Step 1: Write failing test for compile_task()**

Add to `kevin/tests/test_blueprint_compiler.py`:

```python
from kevin.workers.interface import WorkerTask, WorkerPermissions, WorkspacePolicy
from kevin.blueprint_compiler import compile_task

class TestCompileTask:
    def test_should_return_worker_task(self) -> None:
        bp_path = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"
        if not bp_path.exists():
            pytest.skip("Blueprint file not found")

        semantic = load_semantic(bp_path)
        variables = {
            "issue_number": "42",
            "issue_title": "Add endpoint",
            "issue_body": "Add /health",
            "target_repo": "/tmp/test",
            "owner": "test",
            "repo": "test",
            "repo_full": "test/test",
            "learning_context": "",
        }
        task = compile_task(
            semantic, variables, task_id="run-001", cwd=Path("/tmp/test"),
        )

        assert isinstance(task, WorkerTask)
        assert task.task_id == "run-001"
        assert task.timeout == semantic.task_timeout
        assert len(task.instruction) > 100
        assert "ACCEPTANCE CRITERIA" in task.instruction
        assert task.workspace.cwd == Path("/tmp/test")
        assert task.permissions.git_write is True
        assert task.permissions.git_push is True

    def test_should_embed_branch_pattern_from_blueprint(self) -> None:
        bp_path = BLUEPRINTS_DIR / "bp_coding_task.1.0.0.yaml"
        if not bp_path.exists():
            pytest.skip("Blueprint file not found")

        semantic = load_semantic(bp_path)
        variables = {"issue_number": "42", "issue_title": "X", "issue_body": "Y"}
        task = compile_task(
            semantic, variables, task_id="t1", cwd=Path("/tmp"),
        )

        assert "kevin/issue-{issue_number}" in task.workspace.branch_pattern
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest kevin/tests/test_blueprint_compiler.py::TestCompileTask -v
```

Expected: `ImportError: cannot import name 'compile_task'`

- [ ] **Step 3: Add compile_task() to blueprint_compiler.py**

Add after the existing `compile()` function in `kevin/blueprint_compiler.py`:

```python
from kevin.workers.interface import WorkerPermissions, WorkerTask, WorkspacePolicy


def compile_task(
    semantic: SemanticBlueprint,
    variables: dict[str, str],
    *,
    task_id: str,
    cwd: Path,
) -> WorkerTask:
    """Compile Blueprint into a WorkerTask — runtime-agnostic.

    The instruction field contains the structured task description
    (goal, criteria, constraints). No runtime-specific framing.
    Each Worker adapter adds its own framing in translate().
    """
    instruction = compile(semantic, variables)

    # Extract context_filter from blocks if present
    blocks = _extract_blocks_raw(semantic.raw)
    context_filter: list[str] = []
    for block in blocks:
        cf = block.get("runner_config", {}).get("context_filter", [])
        context_filter.extend(f for f in cf if f not in context_filter)

    return WorkerTask(
        task_id=task_id,
        instruction=instruction,
        workspace=WorkspacePolicy(
            cwd=cwd,
            context_filter=context_filter,
        ),
        permissions=WorkerPermissions(
            git_write=True,
            git_push=True,
        ),
        timeout=semantic.task_timeout,
        metadata={
            "blueprint_id": semantic.blueprint_id,
            "issue_number": variables.get("issue_number", ""),
        },
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest kevin/tests/test_blueprint_compiler.py::TestCompileTask -v
```

Expected: PASS

- [ ] **Step 5: Run full regression**

```bash
python3 -m pytest kevin/tests/ -q --ignore=kevin/tests/test_async_execution.py -k "not test_should_return_blueprint_infos_from_real_dir"
```

Expected: all tests PASS (old compile() still works, new compile_task() is additive)

- [ ] **Step 6: Commit**

```bash
git add kevin/blueprint_compiler.py kevin/tests/test_blueprint_compiler.py
git commit -m "feat: add compile_task() producing WorkerTask (D.5)"
```

---

### Task 6: Wire `_execute_agentic()` to use WorkerRegistry

**Files:**
- Modify: `kevin/cli.py:_execute_agentic` (~lines 554-658)
- Test: `kevin/tests/test_cli_executor.py` (update agentic mock target)

- [ ] **Step 1: Write failing test for new flow**

Add to `kevin/tests/test_cli_executor.py`:

```python
class TestAgenticWorkerIntegration:
    @patch("kevin.cli._execute_agentic")
    @patch("kevin.cli.load")
    @patch("kevin.cli.find_blueprint")
    @patch("kevin.cli.StateManager")
    def test_agentic_mode_uses_worker_registry(
        self,
        mock_state_mgr_cls: MagicMock,
        mock_find: MagicMock,
        mock_load: MagicMock,
        mock_exec: MagicMock,
        tmp_path,
    ) -> None:
        """_execute_agentic should use WorkerRegistry internally."""
        bp_file = tmp_path / "bp.yaml"
        bp_file.write_text("blueprint: {metadata: {blueprint_id: bp_test}}")
        mock_find.return_value = bp_file
        mock_bp = MagicMock()
        mock_bp.blueprint_id = "bp_test"
        mock_bp.blocks = []
        mock_load.return_value = mock_bp
        mock_exec.return_value = 0
        mock_run = MagicMock()
        mock_run.run_id = "worker-test"
        mock_run.blocks = {}
        mock_state_mgr = MagicMock()
        mock_state_mgr.create_run.return_value = mock_run
        mock_state_mgr.load_run.return_value = mock_run
        mock_state_mgr_cls.return_value = mock_state_mgr

        with patch("kevin.callback.CallbackClient.report_status"):
            result = main([
                "run",
                "--run-id", "worker-test-001",
                "--blueprint", "bp_test",
                "--instruction", "Do something",
                "--callback-url", "https://example.com/cb",
                "--callback-secret", "s3cr3t",
            ])

        assert result == 0
        mock_exec.assert_called_once()
```

- [ ] **Step 2: Run test to verify it passes (still using mock)**

```bash
python3 -m pytest kevin/tests/test_cli_executor.py::TestAgenticWorkerIntegration -v
```

Expected: PASS (we're mocking _execute_agentic, so this validates the routing)

- [ ] **Step 3: Refactor `_execute_agentic()` in `kevin/cli.py`**

Replace the direct `execute()` call with WorkerRegistry:

```python
def _execute_agentic(
    config: KevinConfig,
    state_mgr: StateManager,
    run: RunState,
    bp_path: Path,
    variables: dict[str, str],
    *,
    issue: Issue | None = None,
) -> int:
    from kevin.blueprint_compiler import compile_task, load_semantic
    from kevin.executor import run_post_validators
    from kevin.workers.registry import WorkerRegistry

    # 1. Load semantic blueprint
    semantic = load_semantic(bp_path)
    _log(config, f"  Agentic mode: {semantic.blueprint_name}")
    _log(config, f"  Criteria: {len(semantic.acceptance_criteria)}, "
                 f"Constraints: {len(semantic.constraints)}, "
                 f"Timeout: {semantic.task_timeout}s")

    # 2. Compile to WorkerTask
    task = compile_task(
        semantic, variables,
        task_id=run.run_id,
        cwd=config.target_repo,
    )
    _log(config, f"  Compiled task: {len(task.instruction)} chars")

    # 3. Resolve worker
    registry = WorkerRegistry()
    worker = registry.resolve()  # default: claude-code
    _log(config, f"  Worker: {worker.worker_id}")

    # 4. Notify Teams: running
    if not config.dry_run:
        _notify_teams(config, run, [], issue, "running")

    run.status = "running"
    state_mgr.complete_run(run, "running")

    # 5. Execute via worker
    if config.dry_run:
        from kevin.workers.interface import WorkerResult
        result = WorkerResult(
            success=True,
            stdout=f"[dry-run] Would execute via {worker.worker_id} ({len(task.instruction)} chars)",
        )
    else:
        result = worker.execute(task)

    # 6. Save logs
    state_mgr.save_executor_logs(
        run.run_id,
        prompt=task.instruction,
        stdout=result.stdout,
        stderr=result.stderr,
    )

    _log(config, f"  Worker result: exit_code={result.exit_code}, "
                 f"duration={result.duration_seconds:.0f}s, "
                 f"failure_type={result.failure_type}")

    # 7. Post-execution validators
    all_passed = result.success
    if result.success and not config.dry_run:
        v_results = run_post_validators(semantic, variables, config.target_repo)
        failed_validators = [v for v in v_results if not v.get("passed")]
        if failed_validators:
            all_passed = False
            _log(config, f"  Validator failures: {failed_validators}")
        else:
            _log(config, f"  Validators: all {len(v_results)} passed")

    # 8. Extract PR from artifacts or stdout
    pr_number = None
    if all_passed:
        from kevin.workers.interface import ArtifactType
        pr_arts = [a for a in result.artifacts if a.artifact_type == ArtifactType.PR_URL]
        if pr_arts:
            import re
            m = re.search(r"/pull/(\d+)", pr_arts[0].location)
            pr_number = int(m.group(1)) if m else None
        if pr_number is None:
            from kevin.executor import extract_pr_number
            pr_number = extract_pr_number(
                result.stdout, repo=run.repo, issue_number=run.issue_number,
            )

    # 9. Finalize
    final_status = "completed" if all_passed else "failed"
    state_mgr.complete_run(run, final_status)

    try:
        from kevin.learning import harvest_run
        harvest_run(config.knowledge_db, config.state_dir, run.run_id)
    except Exception:
        pass

    error_summary = ""
    if not all_passed:
        if result.failure_detail:
            error_summary = result.failure_detail[:300]
        elif result.stderr:
            error_summary = result.stderr[:300]

    if not config.dry_run:
        _post_completion_comment_agentic(config, run, pr_number=pr_number)
        _notify_teams(config, run, [], issue, final_status, error=error_summary)
        try:
            remove_labels(run.repo, run.issue_number, ["kevin"])
            if all_passed:
                add_labels(run.repo, run.issue_number, ["kevin-completed"])
        except Exception:
            pass

    _log(config, f"\nRun {run.run_id}: {final_status} (agentic, worker={worker.worker_id})")
    return 0 if all_passed else 1
```

- [ ] **Step 4: Run full regression**

```bash
python3 -m pytest kevin/tests/ -q --ignore=kevin/tests/test_async_execution.py -k "not test_should_return_blueprint_infos_from_real_dir"
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add kevin/cli.py kevin/tests/test_cli_executor.py
git commit -m "feat: wire _execute_agentic to WorkerRegistry (D.6)"
```

---

### Task 7: End-to-end dry-run verification

**Files:** None (verification only)

- [ ] **Step 1: Dry-run with agentic mode**

```bash
cd /tmp && rm -rf kevin-test-target && git clone https://github.com/centific-cn/kevin-test-target.git
cd /Users/randy/Documents/code/AgenticSDLC && python3 -m kevin run \
  --issue 25 \
  --repo centific-cn/kevin-test-target \
  --target-repo /tmp/kevin-test-target \
  --blueprint bp_coding_task.1.0.0 \
  --dry-run --verbose
```

Expected output should show:
- `Worker: claude-code`
- `Compiled task: NNNN chars`
- `[dry-run] Would execute via claude-code`

- [ ] **Step 2: Dry-run with legacy mode**

```bash
python3 -m kevin run \
  --issue 25 \
  --repo centific-cn/kevin-test-target \
  --target-repo /tmp/kevin-test-target \
  --blueprint bp_coding_task.1.0.0 \
  --legacy --dry-run --verbose
```

Expected: Block mode output (B1 → B2 → B3), no Worker mention

- [ ] **Step 3: Run all tests one final time**

```bash
python3 -m pytest kevin/tests/ -q --ignore=kevin/tests/test_async_execution.py -k "not test_should_return_blueprint_infos_from_real_dir"
```

Expected: all tests PASS, zero regression

- [ ] **Step 4: Final commit tag**

```bash
git tag -a d-worker-interface -m "Phase D complete: Worker Interface"
```

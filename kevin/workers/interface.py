"""Core WorkerInterface types — runtime-agnostic contract between Executor and Workers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


class FailureType(str, Enum):
    """Categorizes how a worker execution failed."""

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
    """Classifies worker output artifacts."""

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
    """Declares what a worker is allowed to do in its sandbox."""

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
    """Defines workspace constraints for a worker execution."""

    cwd: Path
    branch_pattern: str = "kevin/issue-{issue_number}"
    commit_message_pattern: str = "feat: {issue_title} (resolves #{issue_number})"
    protected_paths: list[str] = field(default_factory=list)
    context_filter: list[str] = field(default_factory=list)
    max_files_changed: int = 50
    max_lines_changed: int = 5000


@dataclass(frozen=True)
class WorkerArtifact:
    """A typed output artifact produced by a worker."""

    artifact_type: ArtifactType
    name: str
    location: str
    content_hash: str = ""


@dataclass(frozen=True)
class WorkerTask:
    """Immutable task descriptor sent from Executor to Worker."""

    task_id: str
    instruction: str
    workspace: WorkspacePolicy
    permissions: WorkerPermissions
    timeout: int
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerResult:
    """Mutable result returned from Worker to Executor."""

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
    """Health check response from a worker."""

    available: bool
    worker_id: str
    version: str = ""
    capabilities: list[str] = field(default_factory=list)
    latency_ms: int = 0
    error: str = ""


class WorkerInterface(Protocol):
    """Protocol that all worker adapters must satisfy."""

    @property
    def worker_id(self) -> str: ...

    def execute(self, task: WorkerTask) -> WorkerResult: ...

    def health_check(self) -> WorkerHealth: ...

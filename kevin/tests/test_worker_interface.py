"""Tests for kevin.workers.interface — Core WorkerInterface types."""

from pathlib import Path

import pytest

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


class TestWorkerPermissions:
    def test_should_default_file_read_true(self) -> None:
        perms = WorkerPermissions()
        assert perms.file_read is True

    def test_should_default_file_write_true(self) -> None:
        perms = WorkerPermissions()
        assert perms.file_write is True

    def test_should_default_file_delete_false(self) -> None:
        perms = WorkerPermissions()
        assert perms.file_delete is False

    def test_should_default_git_push_false(self) -> None:
        perms = WorkerPermissions()
        assert perms.git_push is False

    def test_should_default_network_access_false(self) -> None:
        perms = WorkerPermissions()
        assert perms.network_access is False

    def test_should_default_shell_execute_true(self) -> None:
        perms = WorkerPermissions()
        assert perms.shell_execute is True

    def test_should_default_git_read_true(self) -> None:
        perms = WorkerPermissions()
        assert perms.git_read is True

    def test_should_default_git_write_false(self) -> None:
        perms = WorkerPermissions()
        assert perms.git_write is False

    def test_should_default_secrets_access_empty(self) -> None:
        perms = WorkerPermissions()
        assert perms.secrets_access == []

    def test_should_be_frozen(self) -> None:
        perms = WorkerPermissions()
        with pytest.raises(AttributeError):
            perms.file_read = False  # type: ignore[misc]


class TestWorkspacePolicy:
    def test_should_require_cwd(self) -> None:
        policy = WorkspacePolicy(cwd=Path("/tmp/work"))
        assert policy.cwd == Path("/tmp/work")

    def test_should_default_branch_pattern(self) -> None:
        policy = WorkspacePolicy(cwd=Path("/tmp"))
        assert policy.branch_pattern == "kevin/issue-{issue_number}"

    def test_should_default_max_files_changed_50(self) -> None:
        policy = WorkspacePolicy(cwd=Path("/tmp"))
        assert policy.max_files_changed == 50

    def test_should_default_max_lines_changed_5000(self) -> None:
        policy = WorkspacePolicy(cwd=Path("/tmp"))
        assert policy.max_lines_changed == 5000

    def test_should_default_protected_paths_empty(self) -> None:
        policy = WorkspacePolicy(cwd=Path("/tmp"))
        assert policy.protected_paths == []

    def test_should_default_context_filter_empty(self) -> None:
        policy = WorkspacePolicy(cwd=Path("/tmp"))
        assert policy.context_filter == []

    def test_should_be_frozen(self) -> None:
        policy = WorkspacePolicy(cwd=Path("/tmp"))
        with pytest.raises(AttributeError):
            policy.cwd = Path("/other")  # type: ignore[misc]


class TestWorkerTask:
    def test_should_construct_with_required_fields(self) -> None:
        workspace = WorkspacePolicy(cwd=Path("/tmp/work"))
        permissions = WorkerPermissions()
        task = WorkerTask(
            task_id="task-001",
            instruction="Implement feature X",
            workspace=workspace,
            permissions=permissions,
            timeout=300,
        )
        assert task.task_id == "task-001"
        assert task.instruction == "Implement feature X"
        assert task.workspace is workspace
        assert task.permissions is permissions
        assert task.timeout == 300

    def test_should_default_model_empty(self) -> None:
        task = WorkerTask(
            task_id="t1",
            instruction="do stuff",
            workspace=WorkspacePolicy(cwd=Path("/tmp")),
            permissions=WorkerPermissions(),
            timeout=60,
        )
        assert task.model == ""

    def test_should_default_metadata_empty(self) -> None:
        task = WorkerTask(
            task_id="t1",
            instruction="do stuff",
            workspace=WorkspacePolicy(cwd=Path("/tmp")),
            permissions=WorkerPermissions(),
            timeout=60,
        )
        assert task.metadata == {}

    def test_should_be_frozen(self) -> None:
        task = WorkerTask(
            task_id="t1",
            instruction="x",
            workspace=WorkspacePolicy(cwd=Path("/tmp")),
            permissions=WorkerPermissions(),
            timeout=60,
        )
        with pytest.raises(AttributeError):
            task.task_id = "changed"  # type: ignore[misc]


class TestWorkerResult:
    def test_should_construct_success(self) -> None:
        result = WorkerResult(success=True, exit_code=0)
        assert result.success is True
        assert result.exit_code == 0
        assert result.failure_type is None
        assert result.failure_detail == ""

    def test_should_construct_failure(self) -> None:
        result = WorkerResult(
            success=False,
            exit_code=1,
            failure_type=FailureType.EXIT_CODE_NON_ZERO,
            failure_detail="Process exited with code 1",
        )
        assert result.success is False
        assert result.failure_type == FailureType.EXIT_CODE_NON_ZERO
        assert result.failure_detail == "Process exited with code 1"

    def test_should_default_empty_artifacts(self) -> None:
        result = WorkerResult(success=True)
        assert result.artifacts == []

    def test_should_hold_typed_artifacts(self) -> None:
        artifact = WorkerArtifact(
            artifact_type=ArtifactType.SOURCE_CODE,
            name="main.py",
            location="src/main.py",
            content_hash="abc123",
        )
        result = WorkerResult(success=True, artifacts=[artifact])
        assert len(result.artifacts) == 1
        assert result.artifacts[0].artifact_type == ArtifactType.SOURCE_CODE
        assert result.artifacts[0].name == "main.py"

    def test_should_default_duration_zero(self) -> None:
        result = WorkerResult(success=True)
        assert result.duration_seconds == 0.0

    def test_should_default_token_usage_zero(self) -> None:
        result = WorkerResult(success=True)
        assert result.token_usage == 0


class TestWorkerArtifact:
    def test_should_construct_with_all_fields(self) -> None:
        artifact = WorkerArtifact(
            artifact_type=ArtifactType.PR_URL,
            name="pr",
            location="https://github.com/org/repo/pull/42",
        )
        assert artifact.artifact_type == ArtifactType.PR_URL
        assert artifact.content_hash == ""

    def test_should_be_frozen(self) -> None:
        artifact = WorkerArtifact(
            artifact_type=ArtifactType.COMMIT_SHA,
            name="sha",
            location="abc123",
        )
        with pytest.raises(AttributeError):
            artifact.name = "changed"  # type: ignore[misc]


class TestWorkerHealth:
    def test_should_construct_healthy(self) -> None:
        health = WorkerHealth(available=True, worker_id="claude-1")
        assert health.available is True
        assert health.worker_id == "claude-1"
        assert health.error == ""

    def test_should_construct_unhealthy(self) -> None:
        health = WorkerHealth(
            available=False,
            worker_id="claude-1",
            error="Connection refused",
        )
        assert health.available is False
        assert health.error == "Connection refused"

    def test_should_default_capabilities_empty(self) -> None:
        health = WorkerHealth(available=True, worker_id="w1")
        assert health.capabilities == []

    def test_should_default_latency_zero(self) -> None:
        health = WorkerHealth(available=True, worker_id="w1")
        assert health.latency_ms == 0

    def test_should_be_frozen(self) -> None:
        health = WorkerHealth(available=True, worker_id="w1")
        with pytest.raises(AttributeError):
            health.available = False  # type: ignore[misc]


class TestFailureType:
    def test_should_have_all_expected_values(self) -> None:
        expected = {
            "TIMEOUT",
            "COMMAND_NOT_FOUND",
            "EXIT_CODE_NON_ZERO",
            "PERMISSION_DENIED",
            "RESOURCE_LIMIT",
            "NETWORK_ERROR",
            "INTERNAL_ERROR",
            "TASK_REJECTED",
            "HEARTBEAT_TIMEOUT",
        }
        actual = {member.name for member in FailureType}
        assert actual == expected

    def test_should_be_string_enum(self) -> None:
        assert isinstance(FailureType.TIMEOUT, str)


class TestArtifactType:
    def test_should_have_all_expected_values(self) -> None:
        expected = {
            "SOURCE_CODE",
            "TEST_FILE",
            "ANALYSIS_REPORT",
            "PR_URL",
            "COMMIT_SHA",
            "BRANCH_NAME",
            "COVERAGE_REPORT",
            "CUSTOM",
        }
        actual = {member.name for member in ArtifactType}
        assert actual == expected

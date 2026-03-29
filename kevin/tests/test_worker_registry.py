"""Tests for WorkerRegistry (D.4)."""

from __future__ import annotations

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

    def test_should_register_custom_worker(self) -> None:
        registry = WorkerRegistry()
        from kevin.workers.interface import WorkerHealth, WorkerResult, WorkerTask

        class FakeWorker:
            @property
            def worker_id(self) -> str:
                return "fake"

            def execute(self, task: WorkerTask) -> WorkerResult:
                return WorkerResult(success=True)

            def health_check(self) -> WorkerHealth:
                return WorkerHealth(available=True, worker_id="fake")

        registry.register(FakeWorker())
        worker = registry.resolve("fake")
        assert worker.worker_id == "fake"

    def test_should_health_check_all_workers(self) -> None:
        registry = WorkerRegistry()
        results = registry.health_check_all()
        assert "claude-code" in results
        assert "shell" in results
        assert results["shell"].available is True

    def test_should_resolve_empty_string_as_default(self) -> None:
        registry = WorkerRegistry()
        worker = registry.resolve("")
        assert worker.worker_id == "claude-code"

    def test_should_list_include_custom_after_register(self) -> None:
        registry = WorkerRegistry()
        from kevin.workers.interface import WorkerHealth, WorkerResult, WorkerTask

        class CustomWorker:
            @property
            def worker_id(self) -> str:
                return "custom"

            def execute(self, task: WorkerTask) -> WorkerResult:
                return WorkerResult(success=True)

            def health_check(self) -> WorkerHealth:
                return WorkerHealth(available=True, worker_id="custom")

        registry.register(CustomWorker())
        ids = [w.worker_id for w in registry.list_workers()]
        assert "custom" in ids

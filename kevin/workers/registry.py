"""WorkerRegistry — resolves worker adapters by ID."""

from __future__ import annotations

from kevin.workers.claude_code import ClaudeCodeWorker
from kevin.workers.interface import WorkerHealth, WorkerInterface
from kevin.workers.shell import ShellWorker

_DEFAULT_WORKER_ID = "claude-code"


class WorkerRegistry:
    """Registry of available worker adapters with default resolution."""

    def __init__(self) -> None:
        self._workers: dict[str, WorkerInterface] = {}
        self.register(ClaudeCodeWorker())
        self.register(ShellWorker())

    def resolve(self, worker_id: str = "") -> WorkerInterface:
        """Resolve worker by ID. Default: claude-code. Raises KeyError if unknown."""
        key = worker_id or _DEFAULT_WORKER_ID
        if key not in self._workers:
            raise KeyError(f"Unknown worker: {key}")
        return self._workers[key]

    def register(self, worker: WorkerInterface) -> None:
        """Register a custom worker."""
        self._workers[worker.worker_id] = worker

    def list_workers(self) -> list[WorkerInterface]:
        """List all registered workers."""
        return list(self._workers.values())

    def health_check_all(self) -> dict[str, WorkerHealth]:
        """Health check all workers."""
        return {
            worker_id: worker.health_check()
            for worker_id, worker in self._workers.items()
        }

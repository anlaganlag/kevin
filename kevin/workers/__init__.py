"""kevin.workers — Worker interface types and adapters."""

from kevin.workers.interface import (
    ArtifactType,
    FailureType,
    WorkerArtifact,
    WorkerHealth,
    WorkerInterface,
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
    "WorkerInterface",
    "WorkerPermissions",
    "WorkerResult",
    "WorkerTask",
    "WorkspacePolicy",
]

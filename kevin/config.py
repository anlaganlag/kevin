"""Kevin configuration management.

Resolves paths, loads defaults, and provides runtime config to all modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# Default label → blueprint mapping
DEFAULT_INTENT_MAP: dict[str, str] = {
    "coding-task": "bp_coding_task.1.0.0",
    "code-review": "bp_code_review.1.0.0",
    "requirement": "bp_ba_requirement_analysis.1.0.0",
    "backend": "bp_backend_coding_tdd_automation.1.0.0",
    "frontend": "bp_frontend_feature_ui_design.1.0.0",
    "deployment": "bp_deployment_monitoring_automation.1.0.0",
    "architecture": "bp_architecture_blueprint_design.1.0.0",
    "function": "bp_function_implementation_fip_blueprint.1.0.0",
    "testing": "bp_test_feature_comprehensive_testing.1.0.0",
    "planning": "bp_planning_agent.1.0.0",
}

# Aliases: common GitHub labels → Kevin task-type labels.
# These are checked AFTER exact intent_map match fails.
DEFAULT_LABEL_ALIASES: dict[str, str] = {
    "enhancement": "coding-task",
    "bug": "coding-task",
    "feature": "coding-task",
    "documentation": "coding-task",
    "refactor": "coding-task",
    "test": "testing",
    "deploy": "deployment",
    "arch": "architecture",
    "req": "requirement",
    "fip": "function",
}

# Label that triggers Kevin
KEVIN_TRIGGER_LABEL = "kevin"


@dataclass(frozen=True)
class KevinConfig:
    """Immutable runtime configuration for a Kevin run."""

    # Paths
    kevin_root: Path          # Where kevin/ package lives (this repo)
    blueprints_dir: Path      # Where blueprint YAML files live
    target_repo: Path         # The repo Kevin operates on
    state_dir: Path           # .kevin/runs/ for state persistence

    # GitHub
    repo_owner: str = ""
    repo_name: str = ""

    # Runtime
    dry_run: bool = False
    verbose: bool = False

    # Intent mapping overrides
    intent_map: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_INTENT_MAP))

    @property
    def repo_full_name(self) -> str:
        return f"{self.repo_owner}/{self.repo_name}"

    @property
    def knowledge_db(self) -> Path:
        """Path to the SQLite knowledge database."""
        return self.target_repo / ".kevin" / "knowledge.db"


def build_config(
    *,
    repo: str = "",
    target_repo: str = "",
    dry_run: bool = False,
    verbose: bool = False,
) -> KevinConfig:
    """Build a KevinConfig from CLI arguments.

    Args:
        repo: GitHub repo in owner/repo format.
        target_repo: Local path to the target repository.
        dry_run: If True, print actions without executing.
        verbose: If True, print detailed logs.
    """
    kevin_root = Path(__file__).resolve().parent.parent
    blueprints_dir = kevin_root / "blueprints"
    target = Path(target_repo) if target_repo else Path.cwd()

    if not target.is_dir():
        raise FileNotFoundError(
            f"target_repo '{target}' does not exist or is not a directory"
        )

    state_dir = target / ".kevin" / "runs"

    owner, name = "", ""
    if "/" in repo:
        owner, name = repo.split("/", 1)

    return KevinConfig(
        kevin_root=kevin_root,
        blueprints_dir=blueprints_dir,
        target_repo=target,
        state_dir=state_dir,
        repo_owner=owner,
        repo_name=name,
        dry_run=dry_run,
        verbose=verbose,
    )

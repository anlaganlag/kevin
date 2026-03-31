"""Git worktree isolation for executor runs.

Creates a temporary worktree so the agent operates on an isolated copy,
preventing accidental modification of blueprints/, .github/, or other
protected files in the source repository.
"""

from __future__ import annotations

import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def isolated_worktree(repo: Path, run_id: str) -> Iterator[Path]:
    """Create a temporary git worktree and yield its path.

    The worktree is created as a detached HEAD from the current branch.
    On exit, the worktree is removed (even if the agent made changes).
    Changes made by the agent are available as a diff in the worktree
    branch before cleanup.

    Args:
        repo: Path to the git repository.
        run_id: Used to name the worktree branch.

    Yields:
        Path to the worktree directory.
    """
    worktree_dir = repo / ".kevin" / "worktrees" / run_id
    branch_name = f"kevin/run-{run_id}"

    try:
        subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_dir), "HEAD"],
            cwd=repo, capture_output=True, check=True,
        )
        yield worktree_dir
    finally:
        # Remove worktree (force in case of uncommitted changes)
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_dir)],
            cwd=repo, capture_output=True,
        )
        # Clean up the branch
        subprocess.run(
            ["git", "branch", "-D", branch_name],
            cwd=repo, capture_output=True,
        )
        # Remove directory if worktree remove didn't clean it
        if worktree_dir.exists():
            shutil.rmtree(worktree_dir, ignore_errors=True)


def should_isolate(config_target: Path | str, kevin_root: Path | str) -> bool:
    """Return True if the target repo is the Kevin repo itself.

    When Kevin operates on its own repo (no --target-repo), agent execution
    can modify blueprints, workflows, and other infrastructure files.
    Worktree isolation prevents this.
    """
    try:
        return Path(config_target).resolve() == Path(kevin_root).resolve()
    except (OSError, ValueError):
        return False

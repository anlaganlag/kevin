"""Tests for kevin.worktree — git worktree isolation."""

import subprocess
from pathlib import Path

import pytest

from kevin.worktree import isolated_worktree, should_isolate


class TestShouldIsolate:
    """should_isolate detects when target_repo is the Kevin repo itself."""

    def test_should_return_true_when_same_path(self, tmp_path: Path) -> None:
        assert should_isolate(tmp_path, tmp_path) is True

    def test_should_return_true_when_resolved_same(self, tmp_path: Path) -> None:
        symlink = tmp_path / "link"
        symlink.symlink_to(tmp_path)
        assert should_isolate(symlink, tmp_path) is True

    def test_should_return_false_when_different_paths(self, tmp_path: Path) -> None:
        other = tmp_path / "other"
        other.mkdir()
        assert should_isolate(other, tmp_path) is False

    def test_should_return_false_when_path_does_not_exist(self, tmp_path: Path) -> None:
        assert should_isolate(tmp_path / "nonexistent", tmp_path) is False


class TestIsolatedWorktree:
    """isolated_worktree creates and cleans up a git worktree."""

    @pytest.fixture()
    def git_repo(self, tmp_path: Path) -> Path:
        """Create a minimal git repo with one commit."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)
        (repo / "README.md").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True)
        return repo

    def test_should_create_worktree_directory(self, git_repo: Path) -> None:
        with isolated_worktree(git_repo, "test-run") as wt:
            assert wt.exists()
            assert (wt / "README.md").read_text() == "hello"

    def test_should_cleanup_after_exit(self, git_repo: Path) -> None:
        with isolated_worktree(git_repo, "test-run") as wt:
            wt_path = wt
        assert not wt_path.exists()

    def test_should_cleanup_branch_after_exit(self, git_repo: Path) -> None:
        with isolated_worktree(git_repo, "test-run"):
            pass
        result = subprocess.run(
            ["git", "branch", "--list", "kevin/run-test-run"],
            cwd=git_repo, capture_output=True, text=True,
        )
        assert result.stdout.strip() == ""

    def test_should_isolate_changes_from_source(self, git_repo: Path) -> None:
        with isolated_worktree(git_repo, "test-run") as wt:
            (wt / "new_file.txt").write_text("agent output")
        # Source repo should not have the file
        assert not (git_repo / "new_file.txt").exists()

    def test_should_cleanup_even_on_exception(self, git_repo: Path) -> None:
        wt_path = None
        with pytest.raises(RuntimeError):
            with isolated_worktree(git_repo, "test-run") as wt:
                wt_path = wt
                raise RuntimeError("agent crashed")
        assert wt_path is not None
        assert not wt_path.exists()

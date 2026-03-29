"""GitHub operations via `gh` CLI.

All GitHub interactions go through the `gh` CLI to avoid managing tokens directly.
Requires: `gh` installed and authenticated.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    """Minimal GitHub Issue representation."""

    number: int
    title: str
    body: str
    labels: list[str]


def fetch_issue(repo: str, issue_number: int) -> Issue:
    """Fetch a GitHub Issue by number.

    Args:
        repo: owner/repo format.
        issue_number: Issue number.
    """
    result = _gh(
        "issue", "view", str(issue_number),
        "--repo", repo,
        "--json", "number,title,body,labels",
    )
    data = json.loads(result)
    return Issue(
        number=data["number"],
        title=data["title"],
        body=data.get("body", ""),
        labels=[label["name"] for label in data.get("labels", [])],
    )


def post_comment(repo: str, issue_number: int, body: str) -> None:
    """Post a comment on a GitHub Issue."""
    _gh(
        "issue", "comment", str(issue_number),
        "--repo", repo,
        "--body", body,
    )


def add_labels(repo: str, issue_number: int, labels: list[str]) -> None:
    """Add labels to a GitHub Issue, creating missing labels automatically."""
    if not labels:
        return
    for label in labels:
        ensure_label_exists(repo, label)
    _gh(
        "issue", "edit", str(issue_number),
        "--repo", repo,
        *[arg for label in labels for arg in ("--add-label", label)],
    )


def ensure_label_exists(repo: str, label: str) -> None:
    """Create a label if it doesn't exist. Silently succeeds if it already exists."""
    try:
        _gh("label", "create", label, "--repo", repo, "--color", "5319e7", "--force")
    except RuntimeError:
        pass  # Label already exists or other non-critical error


def remove_labels(repo: str, issue_number: int, labels: list[str]) -> None:
    """Remove labels from a GitHub Issue."""
    if not labels:
        return
    _gh(
        "issue", "edit", str(issue_number),
        "--repo", repo,
        *[arg for label in labels for arg in ("--remove-label", label)],
    )


def _gh(*args: str) -> str:
    """Run a gh CLI command and return stdout."""
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh {' '.join(args[:3])}... failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()

"""Tests for kevin validate command."""

from __future__ import annotations

from kevin.cli import main


def test_validate_returns_zero_on_success() -> None:
    """should return 0 when all blueprints validate."""
    result = main(["validate"])
    assert result == 0


def test_validate_with_specific_blueprint() -> None:
    """should validate a single blueprint when --blueprint is given."""
    result = main(["validate", "--blueprint", "bp_coding_task.1.0.0"])
    assert result == 0


def test_validate_fails_for_unknown_blueprint() -> None:
    """should return 1 for a non-existent blueprint."""
    result = main(["validate", "--blueprint", "bp_nonexistent"])
    assert result == 1

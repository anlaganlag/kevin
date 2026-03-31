"""Tests for kevin.config module."""

from __future__ import annotations

from kevin.config import NON_EXECUTABLE_BLUEPRINTS, DEFAULT_INTENT_MAP


def test_non_executable_blueprints_exist() -> None:
    """should define at least bp_planning_agent as non-executable."""
    assert "bp_planning_agent.1.0.0" in NON_EXECUTABLE_BLUEPRINTS


def test_non_executable_not_in_default_intent_map_values() -> None:
    """should not map any intent directly to a non-executable blueprint."""
    for intent, bp_id in DEFAULT_INTENT_MAP.items():
        assert bp_id not in NON_EXECUTABLE_BLUEPRINTS, (
            f"Intent '{intent}' maps to non-executable '{bp_id}'"
        )

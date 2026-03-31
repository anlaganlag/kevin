"""Tests for kevin.config module."""

from __future__ import annotations

from kevin.config import NON_EXECUTABLE_BLUEPRINTS, DEFAULT_INTENT_MAP


def test_non_executable_blueprints_exist() -> None:
    """should define at least bp_planning_agent as non-executable."""
    assert "bp_planning_agent.1.0.0" in NON_EXECUTABLE_BLUEPRINTS


def test_non_executable_blueprints_listed_in_intent_map_are_intentional() -> None:
    """Non-executable blueprints in intent_map should only be orchestrators (planning)."""
    non_exec_intents = {
        intent: bp_id
        for intent, bp_id in DEFAULT_INTENT_MAP.items()
        if bp_id in NON_EXECUTABLE_BLUEPRINTS
    }
    # Only 'planning' should map to a non-executable blueprint
    assert set(non_exec_intents.keys()) <= {"planning"}, (
        f"Unexpected non-executable intents: {non_exec_intents}"
    )

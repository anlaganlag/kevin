"""Tests for kevin/teams_bot/cards.py — duration display, action buttons,
reject form card, and terminal state cards."""

import pytest

from kevin.teams_bot.cards import (
    build_reject_form_card,
    build_run_status_card,
    build_terminal_card,
    format_duration,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

COMPLETED_PAYLOAD = {
    "event": "run_completed",
    "run_id": "run-001",
    "issue_number": 5,
    "issue_title": "My feature",
    "repo": "org/repo",
    "blueprint_id": "bp-001",
    "status": "completed",
    "blocks": [
        {"block_id": "B1", "name": "Unit Tests", "status": "passed", "duration_seconds": 32.0},
        {"block_id": "B2", "name": "Build", "status": "passed", "duration_seconds": 133.0},
    ],
    "pr_number": 7,
    "issue_number": 6,
}

COMPLETED_NO_PR_PAYLOAD = {
    "event": "run_completed",
    "run_id": "run-002",
    "issue_number": 6,
    "issue_title": "My feature",
    "repo": "org/repo",
    "blueprint_id": "bp-001",
    "status": "completed",
    "blocks": [
        {"block_id": "B1", "name": "Unit Tests", "status": "passed", "duration_seconds": 32.0},
    ],
}

FAILED_PAYLOAD = {
    "event": "run_failed",
    "run_id": "run-003",
    "issue_number": 6,
    "issue_title": "My feature",
    "repo": "org/repo",
    "blueprint_id": "bp-001",
    "status": "failed",
    "blocks": [
        {"block_id": "B1", "name": "Unit Tests", "status": "passed", "duration_seconds": 10.0},
        {"block_id": "B2", "name": "Build", "status": "failed", "duration_seconds": None},
    ],
    "error": "Build exploded",
}

RUNNING_PAYLOAD = {
    "event": "block_update",
    "run_id": "run-004",
    "issue_number": 6,
    "issue_title": "My feature",
    "repo": "org/repo",
    "blueprint_id": "bp-001",
    "status": "running",
    "blocks": [
        {"block_id": "B1", "name": "Unit Tests", "status": "passed", "duration_seconds": 32.0},
        {"block_id": "B2", "name": "Build", "status": "running", "duration_seconds": None},
    ],
}


# ---------------------------------------------------------------------------
# TestFormatDuration
# ---------------------------------------------------------------------------


class TestFormatDuration:
    def test_should_return_seconds_when_under_60(self) -> None:
        assert format_duration(32.0) == "32s"

    def test_should_return_minutes_and_seconds_when_over_60(self) -> None:
        assert format_duration(133.0) == "2m13s"

    def test_should_return_zero_seconds_when_zero(self) -> None:
        assert format_duration(0.0) == "0s"

    def test_should_return_empty_string_when_none(self) -> None:
        assert format_duration(None) == ""


# ---------------------------------------------------------------------------
# TestBuildRunStatusCardDuration
# ---------------------------------------------------------------------------


class TestBuildRunStatusCardDuration:
    def test_should_show_duration_in_completed_block_lines(self) -> None:
        card = build_run_status_card(COMPLETED_PAYLOAD)
        blocks_text = card["body"][3]["text"]
        assert "(32s)" in blocks_text
        assert "(2m13s)" in blocks_text

    def test_should_show_duration_only_for_completed_blocks_when_running(self) -> None:
        card = build_run_status_card(RUNNING_PAYLOAD)
        blocks_text = card["body"][3]["text"]
        # B1 is passed with 32s — should appear
        assert "(32s)" in blocks_text
        # B2 is running with no duration — should NOT have parenthesized time
        lines = blocks_text.split("\n\n")
        b2_line = next(line for line in lines if "B2" in line)
        assert "(" not in b2_line


# ---------------------------------------------------------------------------
# TestBuildRunStatusCardButtons
# ---------------------------------------------------------------------------


def _get_actions(payload: dict) -> list[dict]:
    return build_run_status_card(payload)["actions"]


class TestBuildRunStatusCardButtons:
    def test_should_contain_approve_and_reject_when_completed_with_pr(self) -> None:
        actions = _get_actions(COMPLETED_PAYLOAD)
        titles = [a["title"] for a in actions]
        assert "Approve" in titles
        assert "Reject" in titles

    def test_approve_action_should_be_submit_with_correct_data(self) -> None:
        actions = _get_actions(COMPLETED_PAYLOAD)
        approve = next(a for a in actions if a.get("title") == "Approve")
        assert approve["type"] == "Action.Submit"
        assert approve["data"]["action"] == "approve"
        assert approve["data"]["pr_number"] == 7

    def test_should_contain_retry_but_not_approve_when_failed(self) -> None:
        actions = _get_actions(FAILED_PAYLOAD)
        titles = [a["title"] for a in actions]
        assert "Retry" in titles
        assert "Approve" not in titles

    def test_retry_action_should_be_submit_with_correct_data(self) -> None:
        actions = _get_actions(FAILED_PAYLOAD)
        retry = next(a for a in actions if a.get("title") == "Retry")
        assert retry["type"] == "Action.Submit"
        assert retry["data"]["action"] == "retry"
        assert retry["data"]["issue_number"] == 6

    def test_should_have_no_approve_reject_when_completed_without_pr(self) -> None:
        actions = _get_actions(COMPLETED_NO_PR_PAYLOAD)
        titles = [a["title"] for a in actions]
        assert "Approve" not in titles
        assert "Reject" not in titles

    def test_should_have_no_submit_buttons_when_running(self) -> None:
        actions = _get_actions(RUNNING_PAYLOAD)
        submit_actions = [a for a in actions if a.get("type") == "Action.Submit"]
        assert submit_actions == []


# ---------------------------------------------------------------------------
# TestBuildRejectFormCard
# ---------------------------------------------------------------------------


def _all_body_elements(card: dict) -> list[dict]:
    return card.get("body", [])


def _all_actions(card: dict) -> list[dict]:
    return card.get("actions", [])


class TestBuildRejectFormCard:
    CARD = None

    def setup_method(self) -> None:
        self.__class__.CARD = build_reject_form_card(
            run_id="run-99",
            repo="org/repo",
            pr_number=7,
            issue_number=5,
            issue_title="Add login page",
        )

    def test_should_contain_input_text_with_id_reason_and_required(self) -> None:
        card = self.__class__.CARD
        inputs = [el for el in _all_body_elements(card) if el.get("type") == "Input.Text"]
        assert len(inputs) == 1
        assert inputs[0]["id"] == "reason"
        assert inputs[0]["isRequired"] is True

    def test_should_have_confirm_reject_and_cancel_buttons(self) -> None:
        card = self.__class__.CARD
        titles = [a["title"] for a in _all_actions(card)]
        assert "Confirm Reject" in titles
        assert "Cancel" in titles

    def test_confirm_button_data_has_reject_confirm_action(self) -> None:
        card = self.__class__.CARD
        confirm = next(a for a in _all_actions(card) if a.get("title") == "Confirm Reject")
        assert confirm["type"] == "Action.Submit"
        assert confirm["data"]["action"] == "reject_confirm"
        assert confirm["data"]["run_id"] == "run-99"
        assert confirm["data"]["pr_number"] == 7
        assert confirm["data"]["issue_number"] == 5


# ---------------------------------------------------------------------------
# TestBuildTerminalCard
# ---------------------------------------------------------------------------


class TestBuildTerminalCard:
    def test_approved_title_contains_approved_and_no_submit_buttons(self) -> None:
        card = build_terminal_card(
            terminal_type="approved",
            run_id="run-99",
            repo="org/repo",
            pr_number=7,
            issue_number=5,
            issue_title="Add login page",
        )
        title_block = card["body"][0]
        assert "Approved" in title_block["text"]
        submit_actions = [a for a in _all_actions(card) if a.get("type") == "Action.Submit"]
        assert submit_actions == []

    def test_rejected_with_reason_body_contains_reason_string(self) -> None:
        card = build_terminal_card(
            terminal_type="rejected",
            run_id="run-99",
            repo="org/repo",
            pr_number=7,
            issue_number=5,
            issue_title="Add login page",
            reason="Needs more tests",
        )
        body_texts = " ".join(
            el.get("text", "") for el in _all_body_elements(card) if el.get("type") == "TextBlock"
        )
        assert "Needs more tests" in body_texts

    def test_retried_title_contains_retry(self) -> None:
        card = build_terminal_card(
            terminal_type="retried",
            run_id="run-99",
            repo="org/repo",
            pr_number=None,
            issue_number=5,
            issue_title="Add login page",
        )
        title_block = card["body"][0]
        assert "Retry" in title_block["text"]

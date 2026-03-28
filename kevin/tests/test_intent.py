"""Tests for kevin.intent — label classification logic."""

import pytest
from kevin.config import DEFAULT_INTENT_MAP
from kevin.intent import classify


class TestClassify:
    """Intent classification from issue labels."""

    def test_should_match_coding_task_when_kevin_and_coding_task_labels(self) -> None:
        result = classify(["kevin", "coding-task"], DEFAULT_INTENT_MAP)
        assert result is not None
        assert result.blueprint_id == "bp_coding_task.1.0.0"
        assert result.matched_label == "coding-task"

    def test_should_match_code_review_when_kevin_and_code_review_labels(self) -> None:
        result = classify(["kevin", "code-review"], DEFAULT_INTENT_MAP)
        assert result is not None
        assert result.blueprint_id == "bp_code_review.1.0.0"

    def test_should_reject_when_missing_kevin_label(self) -> None:
        result = classify(["coding-task"], DEFAULT_INTENT_MAP)
        assert result is None

    def test_should_reject_when_kevin_only_no_task_type(self) -> None:
        result = classify(["kevin"], DEFAULT_INTENT_MAP)
        assert result is None

    def test_should_reject_when_empty_labels(self) -> None:
        result = classify([], DEFAULT_INTENT_MAP)
        assert result is None

    def test_should_match_first_task_type_when_multiple_types(self) -> None:
        result = classify(["kevin", "coding-task", "code-review"], DEFAULT_INTENT_MAP)
        assert result is not None
        # Should match one of them (order depends on dict iteration)
        assert result.blueprint_id in ("bp_coding_task.1.0.0", "bp_code_review.1.0.0")

    # --- Alias tests ---

    def test_should_match_coding_task_when_enhancement_alias(self) -> None:
        """enhancement is a common GitHub label — should alias to coding-task."""
        result = classify(["kevin", "enhancement"], DEFAULT_INTENT_MAP)
        assert result is not None
        assert result.blueprint_id == "bp_coding_task.1.0.0"
        assert result.matched_label == "enhancement"
        assert result.confidence == "alias"

    def test_should_match_coding_task_when_bug_alias(self) -> None:
        result = classify(["kevin", "bug"], DEFAULT_INTENT_MAP)
        assert result is not None
        assert result.blueprint_id == "bp_coding_task.1.0.0"
        assert result.confidence == "alias"

    def test_should_match_coding_task_when_feature_alias(self) -> None:
        result = classify(["kevin", "feature"], DEFAULT_INTENT_MAP)
        assert result is not None
        assert result.blueprint_id == "bp_coding_task.1.0.0"
        assert result.confidence == "alias"

    def test_should_prefer_exact_match_over_alias(self) -> None:
        """Exact match takes priority even if alias is also present."""
        result = classify(["kevin", "enhancement", "code-review"], DEFAULT_INTENT_MAP)
        assert result is not None
        assert result.blueprint_id == "bp_code_review.1.0.0"
        assert result.confidence == "exact"

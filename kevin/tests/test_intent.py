"""Tests for kevin.intent — label classification logic."""

import pytest
from kevin.config import DEFAULT_INTENT_MAP, DEFAULT_LABEL_ALIASES
from kevin.intent import Intent, classify


# ---------------------------------------------------------------------------
# Fixtures — isolated maps so tests don't depend on production config
# ---------------------------------------------------------------------------

TEST_INTENT_MAP = {
    "coding-task": "bp_coding.1.0",
    "code-review": "bp_review.1.0",
    "deployment": "bp_deploy.1.0",
}

TEST_ALIASES = {
    "enhancement": "coding-task",
    "bug": "coding-task",
    "ship-it": "deployment",
}


# ---------------------------------------------------------------------------
# Intent dataclass
# ---------------------------------------------------------------------------

class TestIntent:
    """Intent dataclass behaviour."""

    def test_should_be_immutable(self) -> None:
        intent = Intent(blueprint_id="bp", matched_label="lbl", confidence="exact")
        with pytest.raises(AttributeError):
            intent.blueprint_id = "other"  # type: ignore[misc]

    def test_should_expose_all_fields(self) -> None:
        intent = Intent(blueprint_id="bp_x", matched_label="x", confidence="alias")
        assert intent.blueprint_id == "bp_x"
        assert intent.matched_label == "x"
        assert intent.confidence == "alias"


# ---------------------------------------------------------------------------
# classify() — exact match
# ---------------------------------------------------------------------------

class TestClassifyExactMatch:
    """Pass 1: direct label → blueprint lookup."""

    def test_should_match_coding_task_when_kevin_and_coding_task_labels(self) -> None:
        result = classify(["kevin", "coding-task"], TEST_INTENT_MAP)
        assert result is not None
        assert result.blueprint_id == "bp_coding.1.0"
        assert result.matched_label == "coding-task"
        assert result.confidence == "exact"

    def test_should_match_code_review_when_kevin_and_code_review_labels(self) -> None:
        result = classify(["kevin", "code-review"], TEST_INTENT_MAP)
        assert result is not None
        assert result.blueprint_id == "bp_review.1.0"
        assert result.confidence == "exact"

    def test_should_match_deployment_when_kevin_and_deployment_labels(self) -> None:
        result = classify(["kevin", "deployment"], TEST_INTENT_MAP)
        assert result is not None
        assert result.blueprint_id == "bp_deploy.1.0"
        assert result.confidence == "exact"

    def test_should_match_first_intent_map_key_when_multiple_types(self) -> None:
        result = classify(
            ["kevin", "coding-task", "code-review"],
            TEST_INTENT_MAP,
        )
        assert result is not None
        assert result.blueprint_id == "bp_coding.1.0"
        assert result.confidence == "exact"

    @pytest.mark.parametrize(
        "label,expected_bp",
        list(DEFAULT_INTENT_MAP.items()),
        ids=list(DEFAULT_INTENT_MAP.keys()),
    )
    def test_should_match_every_default_intent_map_entry(
        self, label: str, expected_bp: str
    ) -> None:
        result = classify(["kevin", label])
        assert result is not None
        assert result.blueprint_id == expected_bp
        assert result.confidence == "exact"


# ---------------------------------------------------------------------------
# classify() — alias fallback
# ---------------------------------------------------------------------------

class TestClassifyAliasFallback:
    """Pass 2: alias resolution when no exact match."""

    def test_should_resolve_enhancement_alias_to_coding_task(self) -> None:
        result = classify(
            ["kevin", "enhancement"],
            TEST_INTENT_MAP,
            TEST_ALIASES,
        )
        assert result is not None
        assert result.blueprint_id == "bp_coding.1.0"
        assert result.matched_label == "enhancement"
        assert result.confidence == "alias"

    def test_should_resolve_bug_alias_to_coding_task(self) -> None:
        result = classify(["kevin", "bug"], TEST_INTENT_MAP, TEST_ALIASES)
        assert result is not None
        assert result.blueprint_id == "bp_coding.1.0"
        assert result.confidence == "alias"

    def test_should_resolve_ship_it_alias_to_deployment(self) -> None:
        result = classify(["kevin", "ship-it"], TEST_INTENT_MAP, TEST_ALIASES)
        assert result is not None
        assert result.blueprint_id == "bp_deploy.1.0"
        assert result.matched_label == "ship-it"
        assert result.confidence == "alias"

    def test_should_prefer_exact_match_over_alias(self) -> None:
        result = classify(
            ["kevin", "enhancement", "code-review"],
            TEST_INTENT_MAP,
            TEST_ALIASES,
        )
        assert result is not None
        assert result.blueprint_id == "bp_review.1.0"
        assert result.confidence == "exact"

    def test_should_return_none_when_alias_target_not_in_map(self) -> None:
        """Alias points to a key that doesn't exist in the intent map."""
        dangling_aliases = {"orphan-label": "nonexistent-task"}
        result = classify(
            ["kevin", "orphan-label"],
            TEST_INTENT_MAP,
            dangling_aliases,
        )
        assert result is None

    @pytest.mark.parametrize(
        "alias_label,expected_bp",
        [
            (alias, DEFAULT_INTENT_MAP[target])
            for alias, target in DEFAULT_LABEL_ALIASES.items()
        ],
        ids=list(DEFAULT_LABEL_ALIASES.keys()),
    )
    def test_should_resolve_every_default_alias(
        self, alias_label: str, expected_bp: str
    ) -> None:
        result = classify(["kevin", alias_label])
        assert result is not None
        assert result.blueprint_id == expected_bp
        assert result.confidence == "alias"


# ---------------------------------------------------------------------------
# classify() — unknown / no match
# ---------------------------------------------------------------------------

class TestClassifyUnknownLabel:
    """No match → None."""

    def test_should_return_none_when_missing_kevin_label(self) -> None:
        result = classify(["coding-task"], TEST_INTENT_MAP)
        assert result is None

    def test_should_return_none_when_kevin_only_no_task_type(self) -> None:
        result = classify(["kevin"], TEST_INTENT_MAP, TEST_ALIASES)
        assert result is None

    def test_should_return_none_when_empty_labels(self) -> None:
        result = classify([], TEST_INTENT_MAP)
        assert result is None

    def test_should_return_none_when_unknown_labels_with_kevin(self) -> None:
        result = classify(
            ["kevin", "random-label", "another"],
            TEST_INTENT_MAP,
            TEST_ALIASES,
        )
        assert result is None


# ---------------------------------------------------------------------------
# classify() — default parameter behaviour
# ---------------------------------------------------------------------------

class TestClassifyDefaults:
    """Verify None params fall back to production defaults."""

    def test_should_use_default_intent_map_when_none(self) -> None:
        result = classify(["kevin", "coding-task"])
        assert result is not None
        assert result.blueprint_id == DEFAULT_INTENT_MAP["coding-task"]

    def test_should_use_default_aliases_when_none(self) -> None:
        result = classify(["kevin", "enhancement"])
        assert result is not None
        assert result.confidence == "alias"

    def test_should_accept_custom_intent_map(self) -> None:
        custom_map = {"my-task": "bp_custom.1.0"}
        result = classify(["kevin", "my-task"], custom_map)
        assert result is not None
        assert result.blueprint_id == "bp_custom.1.0"

    def test_should_accept_custom_aliases(self) -> None:
        custom_map = {"target": "bp_target.1.0"}
        custom_aliases = {"alias-x": "target"}
        result = classify(["kevin", "alias-x"], custom_map, custom_aliases)
        assert result is not None
        assert result.blueprint_id == "bp_target.1.0"
        assert result.confidence == "alias"

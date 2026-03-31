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


# ---------------------------------------------------------------------------
# RL-style exploration — edge case discovery
# ---------------------------------------------------------------------------

class TestRLExplorationEdgeCases:
    """RL-style exploration: systematically probe state-space boundaries.

    Strategy: vary label list structure (duplicates, ordering, size, types)
    to discover edge cases a basic test suite would miss.
    """

    # Edge case 1: duplicate kevin labels — should still work
    def test_should_handle_duplicate_kevin_labels(self) -> None:
        result = classify(
            ["kevin", "kevin", "coding-task"],
            TEST_INTENT_MAP,
        )
        assert result is not None
        assert result.blueprint_id == "bp_coding.1.0"
        assert result.confidence == "exact"

    # Edge case 2: duplicate task labels — first in intent_map key order wins
    def test_should_handle_duplicate_task_labels(self) -> None:
        result = classify(
            ["kevin", "coding-task", "coding-task"],
            TEST_INTENT_MAP,
        )
        assert result is not None
        assert result.blueprint_id == "bp_coding.1.0"

    # Edge case 3: very large label list — stress the set conversion + iteration
    def test_should_handle_large_label_list(self) -> None:
        labels = ["kevin"] + [f"noise-{i}" for i in range(500)] + ["deployment"]
        result = classify(labels, TEST_INTENT_MAP, TEST_ALIASES)
        assert result is not None
        assert result.blueprint_id == "bp_deploy.1.0"
        assert result.confidence == "exact"

    # Edge case 4: label that is both an alias AND an exact match key
    def test_should_prefer_exact_when_label_is_both_alias_and_key(self) -> None:
        ambiguous_map = {"overlap": "bp_direct.1.0"}
        ambiguous_aliases = {"overlap": "coding-task"}
        full_map = {**TEST_INTENT_MAP, **ambiguous_map}
        result = classify(["kevin", "overlap"], full_map, ambiguous_aliases)
        assert result is not None
        assert result.blueprint_id == "bp_direct.1.0"
        assert result.confidence == "exact"

    # Edge case 5: alias chain — alias points to another alias (should NOT resolve)
    def test_should_not_resolve_transitive_alias_chains(self) -> None:
        chain_aliases = {"level1": "level2", "level2": "coding-task"}
        result = classify(["kevin", "level1"], TEST_INTENT_MAP, chain_aliases)
        # "level1" → "level2" — but "level2" must be a key in intent_map, not another alias
        # "level2" IS NOT in TEST_INTENT_MAP, so this should be None
        assert result is None

    # Edge case 6: empty string label
    def test_should_handle_empty_string_label(self) -> None:
        result = classify(["kevin", ""], TEST_INTENT_MAP, TEST_ALIASES)
        assert result is None

    # Edge case 7: whitespace-only labels — not trimmed by classify()
    def test_should_not_match_whitespace_labels(self) -> None:
        result = classify(["kevin", " coding-task "], TEST_INTENT_MAP)
        # " coding-task " != "coding-task" — no match
        assert result is None

    # Edge case 8: case sensitivity — labels are case-sensitive
    def test_should_be_case_sensitive(self) -> None:
        result = classify(["kevin", "Coding-Task"], TEST_INTENT_MAP)
        assert result is None

    # Edge case 9: kevin label only in alias map — should not trigger
    def test_should_not_trigger_when_kevin_is_alias_value(self) -> None:
        weird_aliases = {"trigger": "kevin"}
        result = classify(["trigger"], TEST_INTENT_MAP, weird_aliases)
        assert result is None

    # Edge case 10: alias resolves to exact key but label list ordering affects result
    def test_should_respect_label_list_order_for_alias_resolution(self) -> None:
        multi_aliases = {
            "alias-a": "deployment",
            "alias-b": "coding-task",
        }
        # alias-a appears first in label list, should resolve first
        result = classify(
            ["kevin", "alias-a", "alias-b"],
            TEST_INTENT_MAP,
            multi_aliases,
        )
        assert result is not None
        assert result.blueprint_id == "bp_deploy.1.0"
        assert result.matched_label == "alias-a"
        assert result.confidence == "alias"

    # Edge case 11: empty dict intent_map — falsy, so falls back to defaults
    def test_should_fallback_to_defaults_with_empty_intent_map(self) -> None:
        result = classify(["kevin", "coding-task"], {})
        # {} is falsy → falls back to DEFAULT_INTENT_MAP
        assert result is not None
        assert result.blueprint_id == DEFAULT_INTENT_MAP["coding-task"]

    # Edge case 12: empty dict alias map — falsy, so falls back to defaults
    def test_should_fallback_to_defaults_with_empty_alias_map(self) -> None:
        result = classify(["kevin", "enhancement"], TEST_INTENT_MAP, {})
        # {} is falsy → falls back to DEFAULT_LABEL_ALIASES
        assert result is not None
        assert result.confidence == "alias"


# ---------------------------------------------------------------------------
# Adversarial / security testing
# ---------------------------------------------------------------------------

class TestAdversarialSecurity:
    """Adversarial inputs: injection attempts, type boundary probing.

    classify() operates on in-memory strings so injection risk is low,
    but we verify it doesn't crash or produce unexpected matches.
    """

    @pytest.mark.parametrize(
        "malicious_label",
        [
            "'; DROP TABLE blueprints; --",
            "<script>alert('xss')</script>",
            "{{constructor.constructor('return this')()}}",
            "../../../etc/passwd",
            "kevin\x00coding-task",           # null byte injection
            "coding-task\nX-Injected: true",  # header injection
            "a" * 10_000,                     # oversized label
        ],
        ids=[
            "sql_injection",
            "xss_payload",
            "template_injection",
            "path_traversal",
            "null_byte",
            "header_injection",
            "oversized_input",
        ],
    )
    def test_should_safely_reject_malicious_labels(self, malicious_label: str) -> None:
        result = classify(
            ["kevin", malicious_label],
            TEST_INTENT_MAP,
            TEST_ALIASES,
        )
        # None of these should match any blueprint
        assert result is None

    def test_should_handle_non_ascii_unicode_labels(self) -> None:
        result = classify(["kevin", "编码任务", "🚀"], TEST_INTENT_MAP)
        assert result is None

    def test_should_handle_labels_with_special_regex_chars(self) -> None:
        result = classify(["kevin", "coding-task.*"], TEST_INTENT_MAP)
        assert result is None

    def test_should_not_match_when_intent_map_keys_contain_injection(self) -> None:
        evil_map = {"'; DROP TABLE --": "bp_evil.1.0"}
        result = classify(["kevin", "'; DROP TABLE --"], evil_map)
        # This IS a valid exact match — the map itself is evil, but classify is correct
        assert result is not None
        assert result.blueprint_id == "bp_evil.1.0"


# ---------------------------------------------------------------------------
# Performance testing
# ---------------------------------------------------------------------------

class TestPerformance:
    """Verify classify() meets performance baselines.

    Baseline: < 1ms for typical calls, < 10ms for adversarial large inputs.
    """

    def test_should_classify_typical_call_under_1ms(self) -> None:
        import time

        labels = ["kevin", "coding-task"]
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            classify(labels, TEST_INTENT_MAP, TEST_ALIASES)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 1.0, f"avg {avg_ms:.4f}ms exceeds 1ms baseline"

    def test_should_classify_alias_path_under_1ms(self) -> None:
        import time

        labels = ["kevin", "enhancement"]
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            classify(labels, TEST_INTENT_MAP, TEST_ALIASES)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 1.0, f"avg {avg_ms:.4f}ms exceeds 1ms baseline"

    def test_should_classify_no_match_under_1ms(self) -> None:
        import time

        labels = ["kevin", "unknown-label"]
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            classify(labels, TEST_INTENT_MAP, TEST_ALIASES)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 1.0, f"avg {avg_ms:.4f}ms exceeds 1ms baseline"

    def test_should_handle_500_labels_under_10ms(self) -> None:
        import time

        labels = ["kevin"] + [f"noise-{i}" for i in range(500)] + ["deployment"]
        iterations = 100

        start = time.perf_counter()
        for _ in range(iterations):
            classify(labels, TEST_INTENT_MAP, TEST_ALIASES)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 10.0, f"avg {avg_ms:.4f}ms exceeds 10ms baseline"

    def test_should_handle_large_intent_map_under_5ms(self) -> None:
        import time

        large_map = {f"label-{i}": f"bp_{i}.1.0" for i in range(1000)}
        labels = ["kevin", "label-999"]
        iterations = 100

        start = time.perf_counter()
        for _ in range(iterations):
            classify(labels, large_map, TEST_ALIASES)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0, f"avg {avg_ms:.4f}ms exceeds 5ms baseline"

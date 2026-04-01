"""Tests for identity proof module (Issue #30)."""

import pytest

from kevin.identity_proof import (
    calculate_date_digit_sum,
    calculate_final_result,
    generate_full_proof,
    get_model_identity,
)


class TestGetModelIdentity:
    """Tests for get_model_identity()."""

    def test_should_return_dict_with_required_keys(self):
        identity = get_model_identity()
        required_keys = {
            "is_official_claude",
            "model_name",
            "model_id",
            "training_cutoff",
            "core_positioning",
        }
        assert required_keys.issubset(identity.keys())

    def test_should_declare_official_claude_opus_4_6(self):
        identity = get_model_identity()
        assert identity["is_official_claude"] is True
        assert identity["model_name"] == "Claude Opus 4.6"

    def test_should_return_correct_model_id(self):
        identity = get_model_identity()
        assert identity["model_id"] == "claude-opus-4-6"

    def test_should_return_training_cutoff(self):
        identity = get_model_identity()
        assert identity["training_cutoff"] == "2025-05"

    def test_should_return_non_empty_core_positioning(self):
        identity = get_model_identity()
        assert len(identity["core_positioning"]) > 0


class TestCalculateDateDigitSum:
    """Tests for calculate_date_digit_sum()."""

    def test_should_sum_digits_of_year_month(self):
        # 2025-05: 2+0+2+5+0+5 = 14
        assert calculate_date_digit_sum("2025-05") == 14

    def test_should_sum_digits_of_full_date(self):
        # 2025-05-15: 2+0+2+5+0+5+1+5 = 20
        assert calculate_date_digit_sum("2025-05-15") == 20

    def test_should_handle_single_digit_month(self):
        # 2024-01: 2+0+2+4+0+1 = 9
        assert calculate_date_digit_sum("2024-01") == 9

    def test_should_raise_on_empty_string(self):
        with pytest.raises(ValueError):
            calculate_date_digit_sum("")

    def test_should_ignore_non_digit_characters(self):
        # Only sums the digits: 2+0+2+5+0+5 = 14
        assert calculate_date_digit_sum("2025-05") == 14


class TestCalculateFinalResult:
    """Tests for calculate_final_result()."""

    def test_should_multiply_correctly(self):
        assert calculate_final_result(14, 6) == 84

    def test_should_handle_zero_digit_sum(self):
        assert calculate_final_result(0, 6) == 0

    def test_should_handle_zero_version(self):
        assert calculate_final_result(14, 0) == 0


class TestGenerateFullProof:
    """Tests for generate_full_proof()."""

    def test_should_contain_model_declaration(self):
        proof = generate_full_proof()
        assert "Claude Opus 4.6" in proof
        assert "claude-opus-4-6" in proof

    def test_should_contain_training_cutoff(self):
        proof = generate_full_proof()
        assert "2025" in proof

    def test_should_contain_calculation_process(self):
        proof = generate_full_proof()
        assert "14" in proof
        assert "84" in proof

    def test_should_contain_core_positioning(self):
        proof = generate_full_proof()
        # Should mention reasoning or deepest thinking capability
        assert len(proof) > 100

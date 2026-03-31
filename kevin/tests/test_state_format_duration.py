"""Tests for format_duration() in kevin/state.py."""

from kevin.state import format_duration


class TestFormatDuration:
    """format_duration"""

    def test_should_return_minutes_and_seconds_when_over_60s(self):
        assert format_duration(65.3) == "1m 5s"

    def test_should_return_hours_minutes_seconds_when_over_3600s(self):
        assert format_duration(3661) == "1h 1m 1s"

    def test_should_return_0s_when_less_than_1s(self):
        assert format_duration(0.5) == "0s"

    def test_should_return_0s_when_zero(self):
        assert format_duration(0) == "0s"

    def test_should_return_seconds_only_when_under_60(self):
        assert format_duration(59) == "59s"

    def test_should_include_zero_minutes_and_seconds_when_exact_hour(self):
        assert format_duration(3600) == "1h 0m 0s"

    def test_should_handle_multiple_hours(self):
        assert format_duration(7200) == "2h 0m 0s"

    def test_should_return_0s_when_negative(self):
        assert format_duration(-5) == "0s"

    def test_should_truncate_fractional_seconds(self):
        assert format_duration(61.9) == "1m 1s"

    def test_should_handle_large_values(self):
        assert format_duration(86400) == "24h 0m 0s"

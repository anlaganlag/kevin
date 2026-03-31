"""Unit tests for render_status_badge()."""

from __future__ import annotations

import pytest

from kevin.dashboard.components.status_badge import (
    STATUS_COLORS,
    _DEFAULT_COLOR,
    render_status_badge,
)


class TestRenderStatusBadge:
    """Tests for render_status_badge()."""

    # -- happy path: each known status --------------------------------

    @pytest.mark.parametrize(
        "status,expected_color",
        [
            ("completed", STATUS_COLORS["completed"]),
            ("failed", STATUS_COLORS["failed"]),
            ("running", STATUS_COLORS["running"]),
            ("pending", STATUS_COLORS["pending"]),
        ],
    )
    def test_should_return_correct_color_when_known_status(
        self, status: str, expected_color: str
    ) -> None:
        badge = render_status_badge(status)
        assert f"background-color:{expected_color}" in badge
        assert f">{status}<" in badge

    # -- edge cases ---------------------------------------------------

    def test_should_normalize_whitespace_and_case(self) -> None:
        badge = render_status_badge("  Running  ")
        assert f"background-color:{STATUS_COLORS['running']}" in badge
        assert ">running<" in badge

    def test_should_use_default_color_when_unknown_status(self) -> None:
        badge = render_status_badge("cancelled")
        assert f"background-color:{_DEFAULT_COLOR}" in badge
        assert ">cancelled<" in badge

    # -- HTML structure -----------------------------------------------

    def test_should_return_span_element(self) -> None:
        badge = render_status_badge("completed")
        assert badge.startswith("<span")
        assert badge.endswith("</span>")

    def test_should_include_aria_label_for_accessibility(self) -> None:
        badge = render_status_badge("failed")
        assert 'aria-label="Status: failed"' in badge

    def test_should_include_role_status(self) -> None:
        badge = render_status_badge("pending")
        assert 'role="status"' in badge

    # -- security: XSS prevention -------------------------------------

    def test_should_escape_html_in_status(self) -> None:
        badge = render_status_badge('<script>alert("xss")</script>')
        assert "<script>" not in badge
        assert "&lt;script&gt;" in badge

    # -- immutability: returns new string each call -------------------

    def test_should_return_new_string_each_call(self) -> None:
        a = render_status_badge("completed")
        b = render_status_badge("completed")
        assert a == b
        assert a is not b

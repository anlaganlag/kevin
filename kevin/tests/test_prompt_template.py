"""Tests for kevin.prompt_template — variable substitution."""

from kevin.prompt_template import render


class TestRender:
    """Template variable rendering."""

    def test_should_substitute_variables(self) -> None:
        result = render("Issue #{{issue_number}}: {{issue_title}}", {
            "issue_number": "42",
            "issue_title": "Add health endpoint",
        })
        assert result == "Issue #42: Add health endpoint"

    def test_should_leave_unknown_variables_as_is(self) -> None:
        result = render("{{known}} and {{unknown}}", {"known": "yes"})
        assert result == "yes and {{unknown}}"

    def test_should_handle_empty_template(self) -> None:
        assert render("", {"x": "y"}) == ""

    def test_should_handle_no_variables(self) -> None:
        assert render("plain text", {}) == "plain text"

    def test_should_handle_multiline(self) -> None:
        template = "line1: {{a}}\nline2: {{b}}"
        result = render(template, {"a": "x", "b": "y"})
        assert result == "line1: x\nline2: y"

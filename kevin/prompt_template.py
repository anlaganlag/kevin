"""Render {{variable}} placeholders in prompt templates and shell commands."""

from __future__ import annotations

import re

_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def render(template: str, variables: dict[str, str]) -> str:
    """Replace all {{key}} placeholders with values from *variables*.

    Unknown keys are left as-is (no crash on missing vars).
    """

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return variables.get(key, match.group(0))

    return _VAR_PATTERN.sub(_replace, template)


def extract_variables(template: str) -> list[str]:
    """Return a sorted, unique list of variable names found in *template*."""
    return sorted(set(_VAR_PATTERN.findall(template)))

"""Shared utilities used by scheduler and agent_runner."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kevin.prompt_template import render


_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "do", "does", "did", "have", "has", "had", "will", "would",
    "can", "could", "should", "may", "might", "shall",
    "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "and", "or", "not", "no", "but", "if", "then", "else",
    "this", "that", "it", "its", "as", "so",
})


def extract_keywords(text: str, max_keywords: int = 8) -> str:
    """Extract meaningful keywords from text for FTS5 search."""
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    keywords = [t for t in tokens if t not in _STOP_WORDS and len(t) > 2]
    return " ".join(keywords[:max_keywords])


def resolve_cwd(runner_config: dict[str, Any], variables: dict[str, str]) -> Path:
    """Resolve the working directory from runner_config or default to cwd.

    Shared between scheduler (cwd conflict detection) and agent_runner (execution).
    """
    cwd_raw = runner_config.get("cwd", "")
    if cwd_raw:
        return Path(render(cwd_raw, variables)).resolve()
    return Path.cwd().resolve()

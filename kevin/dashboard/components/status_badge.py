"""Streamlit-compatible HTML status badge for run/block status display."""

from __future__ import annotations

from html import escape

STATUS_COLORS: dict[str, str] = {
    "completed": "#22c55e",
    "failed": "#ef4444",
    "running": "#3b82f6",
    "pending": "#9ca3af",
}

_DEFAULT_COLOR = "#6b7280"


def render_status_badge(status: str) -> str:
    """Return an HTML badge string for the given status.

    The returned HTML is safe to pass to ``st.markdown(..., unsafe_allow_html=True)``.

    Args:
        status: One of ``completed``, ``failed``, ``running``, ``pending``.
                Unknown values render with a neutral gray badge.

    Returns:
        An HTML ``<span>`` string styled as a colored badge.
    """
    normalized = status.strip().lower()
    color = STATUS_COLORS.get(normalized, _DEFAULT_COLOR)
    safe_label = escape(normalized)

    return (
        f'<span style="'
        f"background-color:{color};"
        f"color:#fff;"
        f"padding:2px 10px;"
        f"border-radius:12px;"
        f"font-size:0.85em;"
        f"font-weight:600;"
        f"display:inline-block;"
        f"line-height:1.6;"
        f'"'
        f' role="status"'
        f' aria-label="Status: {safe_label}"'
        f">{safe_label}</span>"
    )

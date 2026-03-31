# Issue #69 Analysis: Status Badge Component

## Requirement
Add `render_status_badge(status: str)` to `kevin/dashboard/components/status_badge.py`.
Returns Streamlit-compatible HTML badge with color-coded status.

## Status Mapping
| Status    | Color   | Hex     |
|-----------|---------|---------|
| completed | Green   | #22c55e |
| failed    | Red     | #ef4444 |
| running   | Blue    | #3b82f6 |
| pending   | Gray    | #9ca3af |
| unknown   | Default | #6b7280 |

## Design Decisions
- HTML `<span>` with inline style for Streamlit `st.markdown(unsafe_allow_html=True)` compatibility
- `html.escape()` for XSS prevention on status text
- `role="status"` + `aria-label` for WCAG 2.1 AA accessibility
- Case-insensitive with whitespace trimming for robustness

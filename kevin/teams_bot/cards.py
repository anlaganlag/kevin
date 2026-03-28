"""Adaptive Card builders for Kevin Teams Bot."""

from typing import Any


def format_duration(seconds: float | None) -> str:
    """Format a duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds, or None if not available.

    Returns:
        Formatted string like "32s", "2m13s", or "" for None.
    """
    if seconds is None:
        return ""
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    if minutes:
        return f"{minutes}m{secs}s"
    return f"{secs}s"


def _status_icon(status: str) -> str:
    return {
        "passed": "\u2705",
        "completed": "\u2705",
        "running": "\ud83d\udd04",
        "failed": "\u274c",
        "pending": "\u23f3",
    }.get(status, "\u2753")


def _header_color(status: str) -> str:
    return {
        "running": "accent",
        "completed": "good",
        "passed": "good",
        "failed": "attention",
        "pending": "default",
    }.get(status, "default")


def build_run_status_card(payload: dict[str, Any]) -> dict[str, Any]:
    """Build an Adaptive Card for Kevin run status.

    Expected payload:
        event: run_started | block_update | run_completed | run_failed
        run_id: str
        issue_number: int
        issue_title: str
        repo: str
        blueprint_id: str
        status: running | completed | failed
        blocks: list[{block_id, name, status}]
        error: optional str
        pr_number: optional int
    """
    event = payload.get("event", "")
    status = payload.get("status", "running")
    blocks = payload.get("blocks", [])
    repo = payload.get("repo", "")
    issue_number = payload.get("issue_number", "")
    issue_title = payload.get("issue_title", "")
    run_id = payload.get("run_id", "")
    blueprint_id = payload.get("blueprint_id", "")
    error = payload.get("error")
    pr_number = payload.get("pr_number")
    logs_url = payload.get("logs_url")

    title_icon = _status_icon(status)
    title_map = {
        "running": "Kevin Running",
        "completed": "Kevin Completed",
        "failed": "Kevin Failed",
    }
    title = f"{title_icon} {title_map.get(status, 'Kevin Update')}"

    # Block status lines with optional duration
    block_lines = []
    for block in blocks:
        icon = _status_icon(block.get("status", "pending"))
        duration_str = format_duration(block.get("duration_seconds"))
        suffix = f" ({duration_str})" if duration_str else ""
        block_lines.append(f"{icon} **{block['block_id']}**: {block['name']}{suffix}")

    blocks_text = "\n\n".join(block_lines) if block_lines else "No blocks"

    body: list[dict[str, Any]] = [
        {
            "type": "TextBlock",
            "text": title,
            "size": "large",
            "weight": "bolder",
            "color": _header_color(status),
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Issue", "value": f"#{issue_number} {issue_title}"},
                {"title": "Repo", "value": repo},
                {"title": "Blueprint", "value": blueprint_id},
                {"title": "Run", "value": run_id},
            ],
        },
        {
            "type": "TextBlock",
            "text": "**Blocks**",
            "weight": "bolder",
            "spacing": "medium",
        },
        {
            "type": "TextBlock",
            "text": blocks_text,
            "wrap": True,
        },
    ]

    if error:
        body.append(
            {
                "type": "TextBlock",
                "text": f"\u274c **Error**: {error}",
                "color": "attention",
                "wrap": True,
                "spacing": "medium",
            }
        )

    actions: list[dict[str, Any]] = []

    # Action.Submit buttons (Approve/Reject for completed+PR, Retry for failed)
    if status == "completed" and pr_number:
        actions.append(
            {
                "type": "Action.Submit",
                "title": "Approve",
                "style": "positive",
                "data": {
                    "action": "approve",
                    "run_id": run_id,
                    "repo": repo,
                    "pr_number": pr_number,
                    "issue_number": issue_number,
                },
            }
        )
        actions.append(
            {
                "type": "Action.Submit",
                "title": "Reject",
                "style": "destructive",
                "data": {
                    "action": "reject",
                    "run_id": run_id,
                    "repo": repo,
                    "pr_number": pr_number,
                    "issue_number": issue_number,
                },
            }
        )
    elif status == "failed":
        actions.append(
            {
                "type": "Action.Submit",
                "title": "Retry",
                "data": {
                    "action": "retry",
                    "run_id": run_id,
                    "repo": repo,
                    "issue_number": issue_number,
                },
            }
        )

    # Action.OpenUrl buttons (always after Submit buttons)
    if repo and issue_number:
        actions.append(
            {
                "type": "Action.OpenUrl",
                "title": "View Issue",
                "url": f"https://github.com/{repo}/issues/{issue_number}",
            }
        )
    if pr_number and repo:
        actions.append(
            {
                "type": "Action.OpenUrl",
                "title": "View PR",
                "url": f"https://github.com/{repo}/pull/{pr_number}",
            }
        )
    if logs_url:
        actions.append(
            {
                "type": "Action.OpenUrl",
                "title": "View Logs",
                "url": logs_url,
            }
        )

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "actions": actions,
    }

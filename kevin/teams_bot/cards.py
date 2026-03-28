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


def build_reject_form_card(
    *,
    run_id: str,
    repo: str,
    pr_number: int,
    issue_number: int,
    issue_title: str,
) -> dict[str, Any]:
    """Build an Adaptive Card with a reason input form for rejecting a PR.

    Args:
        run_id: The Kevin run identifier.
        repo: GitHub repository slug (e.g. "org/repo").
        pr_number: PR number being rejected.
        issue_number: Source issue number.
        issue_title: Source issue title.

    Returns:
        Adaptive Card dict with Input.Text for reason and Confirm/Cancel submit buttons.
    """
    common_data = {
        "run_id": run_id,
        "repo": repo,
        "pr_number": pr_number,
        "issue_number": issue_number,
    }

    body: list[dict[str, Any]] = [
        {
            "type": "TextBlock",
            "text": f"⚠️ Rejecting PR #{pr_number}",
            "size": "large",
            "weight": "bolder",
            "color": "warning",
        },
        {
            "type": "TextBlock",
            "text": f"Issue: #{issue_number} {issue_title}",
            "isSubtle": True,
            "wrap": True,
        },
        {
            "type": "Input.Text",
            "id": "reason",
            "placeholder": "Enter rejection reason…",
            "isMultiline": True,
            "isRequired": True,
            "label": "Reason",
        },
    ]

    actions: list[dict[str, Any]] = [
        {
            "type": "Action.Submit",
            "title": "Confirm Reject",
            "style": "destructive",
            "data": {**common_data, "action": "reject_confirm"},
        },
        {
            "type": "Action.Submit",
            "title": "Cancel",
            "data": {**common_data, "action": "reject_cancel"},
        },
    ]

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "actions": actions,
    }


_TERMINAL_CONFIG: dict[str, dict[str, str]] = {
    "approved": {
        "title_template": "🎉 PR #{pr_number} Approved",
        "subtitle": "Auto-merge enabled, waiting for CI",
        "color": "good",
    },
    "rejected": {
        "title_template": "🚫 PR #{pr_number} Rejected",
        "color": "attention",
    },
    "retried": {
        "title_template": "🔄 Retry Triggered",
        "subtitle": "New run dispatched",
        "color": "accent",
    },
}


def build_terminal_card(
    *,
    terminal_type: str,
    run_id: str,
    repo: str,
    pr_number: int | None,
    issue_number: int,
    issue_title: str,
    reason: str = "",
) -> dict[str, Any]:
    """Build a terminal (non-interactive) Adaptive Card for HITL outcome states.

    No Action.Submit buttons are included to prevent repeat submissions.

    Args:
        terminal_type: One of "approved", "rejected", or "retried".
        run_id: The Kevin run identifier.
        repo: GitHub repository slug (e.g. "org/repo").
        pr_number: PR number, or None for retried (no PR yet).
        issue_number: Source issue number.
        issue_title: Source issue title.
        reason: Optional rejection reason (only used for "rejected" type).

    Returns:
        Adaptive Card dict with OpenUrl action buttons only.
    """
    config = _TERMINAL_CONFIG.get(terminal_type, _TERMINAL_CONFIG["retried"])

    pr_num_str = str(pr_number) if pr_number is not None else "?"
    raw_title = config["title_template"].format(pr_number=pr_num_str)  # type: ignore[index]

    if terminal_type == "rejected":
        subtitle = f"Reason: {reason}" if reason else "Rejected via Teams"
    else:
        subtitle = config.get("subtitle", "")  # type: ignore[attr-defined]

    body: list[dict[str, Any]] = [
        {
            "type": "TextBlock",
            "text": raw_title,
            "size": "large",
            "weight": "bolder",
            "color": config["color"],  # type: ignore[index]
        },
        {
            "type": "TextBlock",
            "text": f"Issue: #{issue_number} {issue_title}",
            "isSubtle": True,
            "wrap": True,
        },
    ]

    if subtitle:
        body.append(
            {
                "type": "TextBlock",
                "text": subtitle,
                "wrap": True,
                "spacing": "medium",
            }
        )

    # OpenUrl buttons only — no Action.Submit to prevent repeat clicks
    actions: list[dict[str, Any]] = [
        {
            "type": "Action.OpenUrl",
            "title": "View Issue",
            "url": f"https://github.com/{repo}/issues/{issue_number}",
        }
    ]

    if terminal_type in {"approved", "rejected"} and pr_number is not None:
        actions.append(
            {
                "type": "Action.OpenUrl",
                "title": "View PR",
                "url": f"https://github.com/{repo}/pull/{pr_number}",
            }
        )

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "actions": actions,
    }

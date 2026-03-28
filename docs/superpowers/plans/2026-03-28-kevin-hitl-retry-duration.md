# Kevin HITL Approval, Retry & Block Duration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Kevin's Teams Cards from read-only notifications to an interactive control panel — approve/reject PRs, retry failed runs, and display block execution duration.

**Architecture:** Three features layered bottom-up: (1) CLI emits `duration_seconds` + `pr_number` in notify payload, (2) `cards.py` renders duration, action buttons, and terminal states, (3) ba-toolkit bot handler processes `Action.Submit` callbacks to call GitHub API. Retry uses `repository_dispatch` instead of label toggling.

**Tech Stack:** Python 3.11+, pytest, Bot Framework SDK, Adaptive Cards 1.4, GitHub REST/GraphQL API, httpx.

**Spec:** `docs/superpowers/specs/2026-03-28-kevin-hitl-retry-duration-design.md`

---

## File Map

### AgenticSDLC repo

| File | Action | Responsibility |
|------|--------|----------------|
| `kevin/cli.py` | Modify (lines 453-489) | Add `duration_seconds`, `pr_number`, `pr_url` to notify payload |
| `kevin/teams_bot/cards.py` | Modify | Add duration display, Action.Submit buttons, reject form, terminal state cards |
| `kevin/tests/test_cards.py` | Create | Unit tests for all card states |
| `kevin/tests/test_cli_notify.py` | Create | Unit tests for payload extension + PR number extraction |
| `.github/workflows/kevin-caller-template.yaml` | Modify | Add `repository_dispatch` trigger |

### ba-toolkit repo

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/api/routes/bot.py` lines 124-179 | Modify | `build_run_status_card()` — add duration, action buttons |
| `backend/app/api/routes/bot.py` lines 391-464 | Modify | `BABot.on_message_activity()` — route Action.Submit to handler |
| `backend/app/api/routes/bot.py` (new section) | Create (inline) | `_handle_card_action()` + approve/reject/retry handlers |
| `backend/tests/test_bot_actions.py` | Create | Integration tests for card action handlers |

---

## Phase 1: Block Duration (F3)

### Task 1: CLI — Add `duration_seconds` to notify payload

**Files:**
- Create: `kevin/tests/test_cli_notify.py`
- Modify: `kevin/cli.py:429-489`

- [ ] **Step 1: Write failing test for duration calculation**

```python
# kevin/tests/test_cli_notify.py
"""Tests for _notify_teams payload construction."""

import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from kevin.state import BlockState, RunState


def _make_run(blocks: dict[str, BlockState] | None = None) -> RunState:
    return RunState(
        run_id="test-run-001",
        blueprint_id="bp_coding_task.1.0.0",
        issue_number=6,
        repo="centific-cn/kevin-test-target",
        status="running",
        blocks=blocks or {},
    )


def _make_block(
    block_id: str,
    status: str = "passed",
    started_at: str = "",
    completed_at: str = "",
) -> BlockState:
    return BlockState(
        block_id=block_id,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
    )


class TestNotifyPayloadDuration:
    """duration_seconds should be computed from started_at/completed_at."""

    def test_should_include_duration_when_block_has_timestamps(self):
        bs = _make_block(
            "B1",
            status="passed",
            started_at="2026-03-28T10:00:00+00:00",
            completed_at="2026-03-28T10:00:32+00:00",
        )
        run = _make_run({"B1": bs})

        payload = self._capture_payload(run, [self._block_def("B1", "Analysis")])

        b1 = payload["blocks"][0]
        assert b1["duration_seconds"] == pytest.approx(32.0)

    def test_should_omit_duration_when_block_has_no_completed_at(self):
        bs = _make_block("B1", status="running", started_at="2026-03-28T10:00:00+00:00")
        run = _make_run({"B1": bs})

        payload = self._capture_payload(run, [self._block_def("B1", "Analysis")])

        assert payload["blocks"][0]["duration_seconds"] is None

    def test_should_omit_duration_when_block_is_pending(self):
        run = _make_run({})

        payload = self._capture_payload(run, [self._block_def("B1", "Analysis")])

        assert payload["blocks"][0]["duration_seconds"] is None

    # -- helpers --

    @staticmethod
    def _block_def(block_id: str, name: str):
        """Minimal Block-like object with block_id and name attributes."""
        obj = MagicMock()
        obj.block_id = block_id
        obj.name = name
        return obj

    @staticmethod
    def _capture_payload(run, blocks, status="running"):
        """Call _notify_teams and capture the JSON payload sent via urlopen."""
        from kevin.cli import _notify_teams, KevinConfig

        config = KevinConfig(
            issue_number=run.issue_number,
            repo=run.repo,
            dry_run=False,
        )
        captured = {}

        def fake_urlopen(req, timeout=10):
            captured["payload"] = json.loads(req.data.decode())
            resp = MagicMock()
            resp.status = 200
            return resp

        with patch.dict("os.environ", {"TEAMS_BOT_URL": "http://fake:8000"}), \
             patch("urllib.request.urlopen", fake_urlopen):
            _notify_teams(config, run, blocks, None, status)

        return captured["payload"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/randy/Documents/code/AgenticSDLC
python -m pytest kevin/tests/test_cli_notify.py::TestNotifyPayloadDuration -x -v
```

Expected: FAIL — `duration_seconds` key not present in payload.

- [ ] **Step 3: Implement duration calculation in `_notify_teams`**

In `kevin/cli.py`, replace the block_list construction (lines 453-460):

```python
# BEFORE (lines 453-460):
    block_list = []
    for b in blocks:
        bs = run.blocks.get(b.block_id)
        block_list.append({
            "block_id": b.block_id,
            "name": b.name,
            "status": bs.status if bs else "pending",
        })

# AFTER:
    block_list = []
    for b in blocks:
        bs = run.blocks.get(b.block_id)
        duration = None
        if bs and bs.started_at and bs.completed_at:
            started = datetime.fromisoformat(bs.started_at)
            completed = datetime.fromisoformat(bs.completed_at)
            duration = (completed - started).total_seconds()
        block_list.append({
            "block_id": b.block_id,
            "name": b.name,
            "status": bs.status if bs else "pending",
            "duration_seconds": duration,
        })
```

Also add `from datetime import datetime` to the import block inside `_notify_teams` (or at module top if preferred — check existing style).

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest kevin/tests/test_cli_notify.py::TestNotifyPayloadDuration -x -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Ensure `started_at` and `completed_at` are written during block execution**

Check `_execute_blocks()` in `kevin/cli.py` (line 305). Currently `BlockState` is created without timestamps. Add them:

```python
# In _execute_blocks(), line 305, BEFORE:
        bs = BlockState(block_id=block.block_id, status="running", runner=block.runner)

# AFTER:
        bs = BlockState(
            block_id=block.block_id,
            status="running",
            runner=block.runner,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
```

And after success/failure (before `state_mgr.update_block`), set `completed_at`:

```python
# After line 336 (if result.success), BEFORE state_mgr.update_block:
                bs.completed_at = datetime.now(timezone.utc).isoformat()

# After line 344 (in the else/failed branch, after bs.error = ...):
                # Don't set completed_at here — only on final failure below
```

```python
# After line 347 (if not success, before state_mgr.update_block):
            bs.completed_at = datetime.now(timezone.utc).isoformat()
```

Ensure `from datetime import datetime, timezone` is imported at the top of `cli.py` (check if already present).

- [ ] **Step 6: Run full test suite**

```bash
python -m pytest kevin/tests/ -x -q
```

Expected: All existing tests + new tests PASS.

- [ ] **Step 7: Commit**

```bash
git add kevin/cli.py kevin/tests/test_cli_notify.py
git commit -m "feat: add duration_seconds to Teams notify payload

Compute block execution time from started_at/completed_at timestamps
and include in the notify payload for card rendering."
```

---

### Task 2: CLI — Add `pr_number` and `pr_url` to notify payload

**Files:**
- Modify: `kevin/tests/test_cli_notify.py`
- Modify: `kevin/cli.py:429-489`

- [ ] **Step 1: Write failing test for PR number extraction**

Append to `kevin/tests/test_cli_notify.py`:

```python
class TestNotifyPayloadPrNumber:
    """pr_number and pr_url should be extracted from B3 output."""

    def test_should_extract_pr_number_from_b3_output(self):
        b3 = _make_block("B3", status="passed")
        b3.output_summary = "https://github.com/centific-cn/kevin-test-target/pull/7"
        run = _make_run({"B3": b3})

        payload = self._capture_payload(run, [self._block_def("B3", "Create PR")], status="completed")

        assert payload["pr_number"] == 7
        assert payload["pr_url"] == "https://github.com/centific-cn/kevin-test-target/pull/7"

    def test_should_handle_gh_pr_create_output_format(self):
        b3 = _make_block("B3", status="passed")
        b3.output_summary = "Creating pull request...\nhttps://github.com/centific-cn/repo/pull/42\nDone"
        run = _make_run({"B3": b3})

        payload = self._capture_payload(run, [self._block_def("B3", "Create PR")], status="completed")

        assert payload["pr_number"] == 42

    def test_should_not_include_pr_number_when_no_pr_url_in_output(self):
        b3 = _make_block("B3", status="passed")
        b3.output_summary = "All checks passed"
        run = _make_run({"B3": b3})

        payload = self._capture_payload(run, [self._block_def("B3", "Create PR")], status="completed")

        assert "pr_number" not in payload
        assert "pr_url" not in payload

    def test_should_not_include_pr_number_when_status_is_running(self):
        b3 = _make_block("B3", status="passed")
        b3.output_summary = "https://github.com/centific-cn/repo/pull/7"
        run = _make_run({"B3": b3})

        payload = self._capture_payload(run, [self._block_def("B3", "Create PR")], status="running")

        assert "pr_number" not in payload

    # -- helpers (reuse from TestNotifyPayloadDuration) --

    @staticmethod
    def _block_def(block_id: str, name: str):
        obj = MagicMock()
        obj.block_id = block_id
        obj.name = name
        return obj

    @staticmethod
    def _capture_payload(run, blocks, status="completed"):
        from kevin.cli import _notify_teams, KevinConfig

        config = KevinConfig(
            issue_number=run.issue_number,
            repo=run.repo,
            dry_run=False,
        )
        captured = {}

        def fake_urlopen(req, timeout=10):
            captured["payload"] = json.loads(req.data.decode())
            resp = MagicMock()
            resp.status = 200
            return resp

        with patch.dict("os.environ", {"TEAMS_BOT_URL": "http://fake:8000"}), \
             patch("urllib.request.urlopen", fake_urlopen):
            _notify_teams(config, run, blocks, None, status)

        return captured["payload"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest kevin/tests/test_cli_notify.py::TestNotifyPayloadPrNumber -x -v
```

Expected: FAIL — `pr_number` not in payload.

- [ ] **Step 3: Implement PR number extraction**

Add helper function in `kevin/cli.py` (before `_notify_teams`):

```python
def _extract_pr_number(run: RunState) -> int | None:
    """Extract PR number from B3 output_summary (gh pr create URL)."""
    import re
    b3 = run.blocks.get("B3")
    if not b3 or not b3.output_summary:
        return None
    match = re.search(r"github\.com/[^/]+/[^/]+/pull/(\d+)", b3.output_summary)
    return int(match.group(1)) if match else None
```

Then in `_notify_teams`, after building `payload` dict (after line 489), add:

```python
    # Include PR info on completion events
    if status in ("completed", "failed"):
        pr_number = _extract_pr_number(run)
        if pr_number:
            payload["pr_number"] = pr_number
            payload["pr_url"] = f"https://github.com/{run.repo}/pull/{pr_number}"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest kevin/tests/test_cli_notify.py -x -v
```

Expected: All tests PASS (both duration and PR number).

- [ ] **Step 5: Commit**

```bash
git add kevin/cli.py kevin/tests/test_cli_notify.py
git commit -m "feat: add pr_number and pr_url to Teams notify payload

Extract PR number from B3 output using regex. Only included on
completion/failure events."
```

---

### Task 3: Cards — Duration display + action buttons

**Files:**
- Create: `kevin/tests/test_cards.py`
- Modify: `kevin/teams_bot/cards.py`

- [ ] **Step 1: Write failing tests for duration formatting**

```python
# kevin/tests/test_cards.py
"""Tests for Adaptive Card builders."""

import pytest

from kevin.teams_bot.cards import build_run_status_card, format_duration


class TestFormatDuration:
    def test_should_format_seconds(self):
        assert format_duration(32.0) == "32s"

    def test_should_format_minutes_and_seconds(self):
        assert format_duration(133.0) == "2m13s"

    def test_should_format_zero(self):
        assert format_duration(0.0) == "0s"

    def test_should_return_empty_for_none(self):
        assert format_duration(None) == ""


class TestBuildRunStatusCardDuration:
    def test_should_show_duration_for_completed_blocks(self):
        payload = {
            "status": "completed",
            "blocks": [
                {"block_id": "B1", "name": "Analysis", "status": "passed", "duration_seconds": 32.0},
                {"block_id": "B2", "name": "Build", "status": "passed", "duration_seconds": 133.0},
            ],
            "repo": "centific-cn/test",
            "issue_number": 6,
            "issue_title": "Test",
            "run_id": "run-001",
            "blueprint_id": "bp_test",
        }
        card = build_run_status_card(payload)
        blocks_text = card["body"][3]["text"]
        assert "(32s)" in blocks_text
        assert "(2m13s)" in blocks_text

    def test_should_not_show_duration_for_pending_blocks(self):
        payload = {
            "status": "running",
            "blocks": [
                {"block_id": "B1", "name": "Analysis", "status": "passed", "duration_seconds": 32.0},
                {"block_id": "B2", "name": "Build", "status": "running", "duration_seconds": None},
            ],
            "repo": "centific-cn/test",
            "issue_number": 6,
            "issue_title": "Test",
            "run_id": "run-001",
            "blueprint_id": "bp_test",
        }
        card = build_run_status_card(payload)
        blocks_text = card["body"][3]["text"]
        assert "(32s)" in blocks_text
        assert "Build" in blocks_text
        # Running block should not have duration
        lines = blocks_text.split("\n\n")
        assert "(" not in lines[1]  # B2 line
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest kevin/tests/test_cards.py::TestFormatDuration -x -v
python -m pytest kevin/tests/test_cards.py::TestBuildRunStatusCardDuration -x -v
```

Expected: FAIL — `format_duration` not found.

- [ ] **Step 3: Implement duration formatting and update card builder**

In `kevin/teams_bot/cards.py`, add `format_duration` function and update block rendering:

```python
def format_duration(seconds: float | None) -> str:
    """Format seconds into human-readable duration string."""
    if seconds is None:
        return ""
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    return f"{minutes}m{secs}s"
```

Update the block line rendering inside `build_run_status_card`:

```python
    # BEFORE:
    block_lines = []
    for block in blocks:
        icon = _status_icon(block.get("status", "pending"))
        block_lines.append(f"{icon} **{block['block_id']}**: {block['name']}")

    # AFTER:
    block_lines = []
    for block in blocks:
        icon = _status_icon(block.get("status", "pending"))
        duration = format_duration(block.get("duration_seconds"))
        suffix = f" ({duration})" if duration else ""
        block_lines.append(f"{icon} **{block['block_id']}**: {block['name']}{suffix}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest kevin/tests/test_cards.py -x -v
```

Expected: PASS.

- [ ] **Step 5: Write failing tests for action buttons**

Append to `kevin/tests/test_cards.py`:

```python
class TestBuildRunStatusCardButtons:
    def test_should_show_approve_reject_on_completed(self):
        payload = self._completed_payload()
        card = build_run_status_card(payload)
        action_titles = [a.get("title") for a in card.get("actions", [])]
        assert "Approve" in action_titles
        assert "Reject" in action_titles

    def test_should_include_submit_data_on_approve(self):
        payload = self._completed_payload()
        card = build_run_status_card(payload)
        approve = next(a for a in card["actions"] if a.get("title") == "Approve")
        assert approve["type"] == "Action.Submit"
        assert approve["data"]["action"] == "approve"
        assert approve["data"]["pr_number"] == 7
        assert approve["data"]["repo"] == "centific-cn/test"

    def test_should_show_retry_on_failed(self):
        payload = self._failed_payload()
        card = build_run_status_card(payload)
        action_titles = [a.get("title") for a in card.get("actions", [])]
        assert "Retry" in action_titles
        assert "Approve" not in action_titles

    def test_should_include_submit_data_on_retry(self):
        payload = self._failed_payload()
        card = build_run_status_card(payload)
        retry = next(a for a in card["actions"] if a.get("title") == "Retry")
        assert retry["type"] == "Action.Submit"
        assert retry["data"]["action"] == "retry"
        assert retry["data"]["issue_number"] == 6

    def test_should_not_show_approve_reject_without_pr_number(self):
        payload = self._completed_payload()
        del payload["pr_number"]
        card = build_run_status_card(payload)
        action_titles = [a.get("title") for a in card.get("actions", [])]
        assert "Approve" not in action_titles
        assert "Reject" not in action_titles

    def test_should_not_show_action_buttons_on_running(self):
        payload = {
            "status": "running",
            "blocks": [],
            "repo": "centific-cn/test",
            "issue_number": 6,
            "issue_title": "Test",
            "run_id": "run-001",
            "blueprint_id": "bp_test",
        }
        card = build_run_status_card(payload)
        submit_actions = [a for a in card.get("actions", []) if a.get("type") == "Action.Submit"]
        assert len(submit_actions) == 0

    @staticmethod
    def _completed_payload():
        return {
            "status": "completed",
            "blocks": [{"block_id": "B1", "name": "Test", "status": "passed", "duration_seconds": 10}],
            "repo": "centific-cn/test",
            "issue_number": 6,
            "issue_title": "Test",
            "run_id": "run-001",
            "blueprint_id": "bp_test",
            "pr_number": 7,
        }

    @staticmethod
    def _failed_payload():
        return {
            "status": "failed",
            "blocks": [{"block_id": "B1", "name": "Test", "status": "failed", "duration_seconds": 10}],
            "repo": "centific-cn/test",
            "issue_number": 6,
            "issue_title": "Test",
            "run_id": "run-001",
            "blueprint_id": "bp_test",
            "error": "test failed",
        }
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
python -m pytest kevin/tests/test_cards.py::TestBuildRunStatusCardButtons -x -v
```

Expected: FAIL — no Action.Submit buttons in card.

- [ ] **Step 7: Implement action buttons in `build_run_status_card`**

In `kevin/teams_bot/cards.py`, update the actions section of `build_run_status_card`:

```python
    # BEFORE (existing actions section, lines 110-134):
    actions: list[dict[str, Any]] = []
    if repo and issue_number:
        actions.append(...)
    if pr_number and repo:
        actions.append(...)
    if logs_url:
        actions.append(...)

    # AFTER:
    actions: list[dict[str, Any]] = []

    # Action.Submit buttons based on status
    if status == "completed" and pr_number:
        submit_data_base = {
            "run_id": run_id,
            "repo": repo,
            "pr_number": pr_number,
            "issue_number": issue_number,
        }
        actions.append({
            "type": "Action.Submit",
            "title": "Approve",
            "style": "positive",
            "data": {**submit_data_base, "action": "approve"},
        })
        actions.append({
            "type": "Action.Submit",
            "title": "Reject",
            "style": "destructive",
            "data": {**submit_data_base, "action": "reject"},
        })
    elif status == "failed":
        actions.append({
            "type": "Action.Submit",
            "title": "Retry",
            "data": {
                "action": "retry",
                "run_id": run_id,
                "repo": repo,
                "issue_number": issue_number,
            },
        })

    # OpenUrl buttons (always shown where applicable)
    if repo and issue_number:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "View Issue",
            "url": f"https://github.com/{repo}/issues/{issue_number}",
        })
    if pr_number and repo:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "View PR",
            "url": f"https://github.com/{repo}/pull/{pr_number}",
        })
    if logs_url:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "View Logs",
            "url": logs_url,
        })
```

- [ ] **Step 8: Run all card tests**

```bash
python -m pytest kevin/tests/test_cards.py -x -v
```

Expected: All PASS.

- [ ] **Step 9: Commit**

```bash
git add kevin/teams_bot/cards.py kevin/tests/test_cards.py
git commit -m "feat: add duration display and action buttons to Teams cards

Cards now show block execution time (e.g. '32s', '2m13s').
Completed cards show Approve/Reject buttons (Action.Submit).
Failed cards show Retry button (Action.Submit)."
```

---

### Task 4: Cards — Reject form and terminal state builders

**Files:**
- Modify: `kevin/tests/test_cards.py`
- Modify: `kevin/teams_bot/cards.py`

- [ ] **Step 1: Write failing tests for reject form and terminal states**

Append to `kevin/tests/test_cards.py`:

```python
from kevin.teams_bot.cards import (
    build_reject_form_card,
    build_terminal_card,
)


class TestBuildRejectFormCard:
    def test_should_contain_text_input(self):
        card = build_reject_form_card(
            run_id="run-001", repo="centific-cn/test",
            pr_number=7, issue_number=6, issue_title="Test",
        )
        input_blocks = [b for b in card["body"] if b.get("type") == "Input.Text"]
        assert len(input_blocks) == 1
        assert input_blocks[0]["id"] == "reason"
        assert input_blocks[0].get("isRequired") is True

    def test_should_have_confirm_and_cancel_buttons(self):
        card = build_reject_form_card(
            run_id="run-001", repo="centific-cn/test",
            pr_number=7, issue_number=6, issue_title="Test",
        )
        action_titles = [a.get("title") for a in card.get("actions", [])]
        assert "Confirm Reject" in action_titles
        assert "Cancel" in action_titles

    def test_confirm_should_carry_reject_confirm_action(self):
        card = build_reject_form_card(
            run_id="run-001", repo="centific-cn/test",
            pr_number=7, issue_number=6, issue_title="Test",
        )
        confirm = next(a for a in card["actions"] if a["title"] == "Confirm Reject")
        assert confirm["data"]["action"] == "reject_confirm"


class TestBuildTerminalCard:
    def test_approved_terminal(self):
        card = build_terminal_card(
            terminal_type="approved", run_id="run-001",
            repo="centific-cn/test", pr_number=7,
            issue_number=6, issue_title="Test",
        )
        title_block = card["body"][0]["text"]
        assert "Approved" in title_block
        # No Action.Submit buttons
        submit_actions = [a for a in card.get("actions", []) if a["type"] == "Action.Submit"]
        assert len(submit_actions) == 0

    def test_rejected_terminal_includes_reason(self):
        card = build_terminal_card(
            terminal_type="rejected", run_id="run-001",
            repo="centific-cn/test", pr_number=7,
            issue_number=6, issue_title="Test",
            reason="Edge cases not handled",
        )
        body_texts = " ".join(b.get("text", "") for b in card["body"])
        assert "Edge cases not handled" in body_texts

    def test_retried_terminal(self):
        card = build_terminal_card(
            terminal_type="retried", run_id="run-001",
            repo="centific-cn/test", pr_number=None,
            issue_number=6, issue_title="Test",
        )
        title_block = card["body"][0]["text"]
        assert "Retry" in title_block
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest kevin/tests/test_cards.py::TestBuildRejectFormCard -x -v
python -m pytest kevin/tests/test_cards.py::TestBuildTerminalCard -x -v
```

Expected: FAIL — functions not found.

- [ ] **Step 3: Implement `build_reject_form_card` and `build_terminal_card`**

Add to `kevin/teams_bot/cards.py`:

```python
def build_reject_form_card(
    *,
    run_id: str,
    repo: str,
    pr_number: int,
    issue_number: int,
    issue_title: str,
) -> dict[str, Any]:
    """Build a card with text input for rejection reason."""
    submit_data = {
        "action": "reject_confirm",
        "run_id": run_id,
        "repo": repo,
        "pr_number": pr_number,
        "issue_number": issue_number,
    }
    cancel_data = {
        "action": "reject_cancel",
        "run_id": run_id,
        "repo": repo,
        "pr_number": pr_number,
        "issue_number": issue_number,
    }
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": f"\u26a0\ufe0f Rejecting PR #{pr_number}",
                "size": "large",
                "weight": "bolder",
                "color": "warning",
            },
            {
                "type": "TextBlock",
                "text": f"Issue: #{issue_number} {issue_title}",
            },
            {
                "type": "Input.Text",
                "id": "reason",
                "label": "Rejection reason (required)",
                "isRequired": True,
                "isMultiline": True,
                "placeholder": "Describe why this PR should be rejected...",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Confirm Reject",
                "style": "destructive",
                "data": submit_data,
            },
            {
                "type": "Action.Submit",
                "title": "Cancel",
                "data": cancel_data,
            },
        ],
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
    """Build a terminal-state card (no action buttons)."""
    config = {
        "approved": {
            "title": f"\U0001f389 PR #{pr_number} Approved",
            "color": "good",
            "subtitle": "Auto-merge enabled, waiting for CI",
        },
        "rejected": {
            "title": f"\U0001f6ab PR #{pr_number} Rejected",
            "color": "attention",
            "subtitle": f"Reason: {reason}" if reason else "Rejected via Teams",
        },
        "retried": {
            "title": "\U0001f504 Retry Triggered",
            "color": "accent",
            "subtitle": "New run dispatched",
        },
    }
    cfg = config.get(terminal_type, config["retried"])

    body: list[dict[str, Any]] = [
        {
            "type": "TextBlock",
            "text": cfg["title"],
            "size": "large",
            "weight": "bolder",
            "color": cfg["color"],
        },
        {
            "type": "TextBlock",
            "text": f"Issue: #{issue_number} {issue_title}",
        },
        {
            "type": "TextBlock",
            "text": cfg["subtitle"],
            "wrap": True,
        },
    ]

    # OpenUrl actions only (no Submit)
    actions: list[dict[str, Any]] = []
    if repo and issue_number:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "View Issue",
            "url": f"https://github.com/{repo}/issues/{issue_number}",
        })
    if pr_number and repo and terminal_type != "retried":
        actions.append({
            "type": "Action.OpenUrl",
            "title": "View PR",
            "url": f"https://github.com/{repo}/pull/{pr_number}",
        })

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "actions": actions,
    }
```

- [ ] **Step 4: Run all card tests**

```bash
python -m pytest kevin/tests/test_cards.py -x -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add kevin/teams_bot/cards.py kevin/tests/test_cards.py
git commit -m "feat: add reject form and terminal state card builders

build_reject_form_card: text input for rejection reason.
build_terminal_card: approved/rejected/retried terminal states
with no Action.Submit buttons (prevents repeat clicks)."
```

---

## Phase 2: Retry (F2)

### Task 5: Workflow — Add `repository_dispatch` trigger

**Files:**
- Modify: `.github/workflows/kevin-caller-template.yaml`

- [ ] **Step 1: Update the caller workflow template**

Edit `.github/workflows/kevin-caller-template.yaml`:

```yaml
# BEFORE (lines 17-19):
on:
  issues:
    types: [labeled]

# AFTER:
on:
  issues:
    types: [labeled]
  repository_dispatch:
    types: [kevin-run]
```

```yaml
# BEFORE (lines 31-32):
  kevin:
    if: github.event.label.name == 'kevin'

# AFTER:
  kevin:
    if: >-
      (github.event_name == 'issues' && github.event.label.name == 'kevin') ||
      github.event_name == 'repository_dispatch'
```

```yaml
# BEFORE (lines 35-36):
      issue_number: ${{ github.event.issue.number }}
      issue_title: ${{ github.event.issue.title }}

# AFTER:
      issue_number: ${{ github.event.issue.number || github.event.client_payload.issue_number }}
      issue_title: ${{ github.event.issue.title || github.event.client_payload.issue_title || '' }}
```

- [ ] **Step 2: Validate YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/kevin-caller-template.yaml'))"
```

Expected: No error.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/kevin-caller-template.yaml
git commit -m "feat: add repository_dispatch trigger for retry

Allows ba-toolkit bot to trigger Kevin re-runs via GitHub API
dispatch event instead of label toggling. Supports issue_number
and issue_title via client_payload."
```

---

### Task 6: ba-toolkit — Card action handler (approve/reject/retry)

**Files:**
- Create: `backend/tests/test_bot_actions.py` (in ba-toolkit repo)
- Modify: `backend/app/api/routes/bot.py` (in ba-toolkit repo)

> **Note:** This task operates in the ba-toolkit repo at `/Users/randy/Documents/code/ba2/ba-toolkit`.

- [ ] **Step 1: Write failing tests for action routing**

```python
# ba-toolkit/backend/tests/test_bot_actions.py
"""Tests for Teams card action handlers (approve, reject, retry)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# We test the handler methods directly, mocking GitHub API calls


@pytest.fixture
def action_base_data():
    return {
        "run_id": "run-001",
        "repo": "centific-cn/kevin-test-target",
        "pr_number": 7,
        "issue_number": 6,
    }


class TestActionRouting:
    """on_message_activity should route Action.Submit to _handle_card_action."""

    @pytest.mark.asyncio
    async def test_should_route_action_submit_to_handler(self, action_base_data):
        from app.api.routes.bot import BABot

        bot = BABot()
        ctx = MagicMock()
        ctx.activity = MagicMock()
        ctx.activity.value = {**action_base_data, "action": "approve"}
        ctx.activity.text = None
        ctx.activity.entities = None
        ctx.update_activity = AsyncMock()
        ctx.send_activity = AsyncMock()

        with patch.object(bot, "_handle_card_action", new_callable=AsyncMock) as mock_handler:
            await bot.on_message_activity(ctx)
            mock_handler.assert_called_once_with(ctx, ctx.activity.value)

    @pytest.mark.asyncio
    async def test_should_fall_through_to_text_when_no_action(self):
        from app.api.routes.bot import BABot

        bot = BABot()
        ctx = MagicMock()
        ctx.activity = MagicMock()
        ctx.activity.value = None
        ctx.activity.text = "help"
        ctx.activity.entities = None
        ctx.send_activity = AsyncMock()

        await bot.on_message_activity(ctx)
        ctx.send_activity.assert_called_once()


class TestApproveAction:
    """Approve should create PR review + enable auto-merge."""

    @pytest.mark.asyncio
    async def test_should_call_github_approve_and_automerge(self, action_base_data):
        from app.api.routes.bot import BABot

        bot = BABot()
        ctx = MagicMock()
        ctx.update_activity = AsyncMock()

        with patch("app.api.routes.bot._github_approve_pr", new_callable=AsyncMock) as mock_approve, \
             patch("app.api.routes.bot._github_enable_automerge", new_callable=AsyncMock) as mock_automerge, \
             patch("app.api.routes.bot._update_card_to_terminal", new_callable=AsyncMock):
            await bot._handle_card_action(ctx, {**action_base_data, "action": "approve"})
            mock_approve.assert_called_once_with("centific-cn/kevin-test-target", 7)
            mock_automerge.assert_called_once_with("centific-cn/kevin-test-target", 7)


class TestRejectAction:
    """Reject should show form, then close PR + post comment."""

    @pytest.mark.asyncio
    async def test_should_show_reject_form(self, action_base_data):
        from app.api.routes.bot import BABot

        bot = BABot()
        ctx = MagicMock()
        ctx.update_activity = AsyncMock()

        with patch("app.api.routes.bot._update_card_with", new_callable=AsyncMock) as mock_update:
            await bot._handle_card_action(ctx, {**action_base_data, "action": "reject"})
            mock_update.assert_called_once()
            # Verify it was called with a reject form card
            card_arg = mock_update.call_args[0][1]  # second positional arg
            input_blocks = [b for b in card_arg["body"] if b.get("type") == "Input.Text"]
            assert len(input_blocks) == 1

    @pytest.mark.asyncio
    async def test_should_close_pr_and_post_comment_on_confirm(self, action_base_data):
        from app.api.routes.bot import BABot

        bot = BABot()
        ctx = MagicMock()
        ctx.update_activity = AsyncMock()

        data = {**action_base_data, "action": "reject_confirm", "reason": "Needs edge cases"}

        with patch("app.api.routes.bot._github_close_pr", new_callable=AsyncMock) as mock_close, \
             patch("app.api.routes.bot._github_post_comment", new_callable=AsyncMock) as mock_comment, \
             patch("app.api.routes.bot._update_card_to_terminal", new_callable=AsyncMock):
            await bot._handle_card_action(ctx, data)
            mock_close.assert_called_once_with("centific-cn/kevin-test-target", 7)
            mock_comment.assert_called_once()
            comment_body = mock_comment.call_args[0][2]
            assert "Needs edge cases" in comment_body


class TestRetryAction:
    """Retry should dispatch repository_dispatch event."""

    @pytest.mark.asyncio
    async def test_should_dispatch_repository_event(self, action_base_data):
        from app.api.routes.bot import BABot

        bot = BABot()
        ctx = MagicMock()
        ctx.update_activity = AsyncMock()

        with patch("app.api.routes.bot._github_dispatch_retry", new_callable=AsyncMock) as mock_dispatch, \
             patch("app.api.routes.bot._update_card_to_terminal", new_callable=AsyncMock):
            await bot._handle_card_action(ctx, {**action_base_data, "action": "retry"})
            mock_dispatch.assert_called_once_with("centific-cn/kevin-test-target", 6)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/randy/Documents/code/ba2/ba-toolkit
python -m pytest backend/tests/test_bot_actions.py -x -v
```

Expected: FAIL — handler methods not found.

- [ ] **Step 3: Implement GitHub API helper functions**

Add to `backend/app/api/routes/bot.py`, after the existing `_github_get_issue` function:

```python
async def _github_approve_pr(repo: str, pr_number: int) -> dict[str, Any]:
    """Create an approving review on a PR."""
    settings = get_settings()
    token = settings.KEVIN_GITHUB_TOKEN
    if not token:
        return {"error": "KEVIN_GITHUB_TOKEN not configured"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={"event": "APPROVE"},
        )
        return resp.json()


async def _github_enable_automerge(repo: str, pr_number: int) -> dict[str, Any]:
    """Enable auto-merge on a PR via GraphQL."""
    settings = get_settings()
    token = settings.KEVIN_GITHUB_TOKEN
    if not token:
        return {"error": "KEVIN_GITHUB_TOKEN not configured"}

    # First get the PR node_id
    async with httpx.AsyncClient(timeout=10.0) as client:
        pr_resp = await client.get(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        pr_data = pr_resp.json()
        node_id = pr_data.get("node_id", "")

        if not node_id:
            return {"error": "Could not get PR node_id"}

        # Enable auto-merge via GraphQL
        mutation = """
        mutation EnableAutoMerge($prId: ID!) {
            enablePullRequestAutoMerge(input: {pullRequestId: $prId, mergeMethod: SQUASH}) {
                pullRequest { autoMergeRequest { enabledAt } }
            }
        }
        """
        gql_resp = await client.post(
            "https://api.github.com/graphql",
            headers={
                "Authorization": f"bearer {token}",
                "Content-Type": "application/json",
            },
            json={"query": mutation, "variables": {"prId": node_id}},
        )
        return gql_resp.json()


async def _github_close_pr(repo: str, pr_number: int) -> dict[str, Any]:
    """Close a PR."""
    settings = get_settings()
    token = settings.KEVIN_GITHUB_TOKEN
    if not token:
        return {"error": "KEVIN_GITHUB_TOKEN not configured"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.patch(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={"state": "closed"},
        )
        return resp.json()


async def _github_post_comment(repo: str, issue_number: int, body: str) -> dict[str, Any]:
    """Post a comment on an issue/PR."""
    settings = get_settings()
    token = settings.KEVIN_GITHUB_TOKEN
    if not token:
        return {"error": "KEVIN_GITHUB_TOKEN not configured"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={"body": body},
        )
        return resp.json()


async def _github_dispatch_retry(repo: str, issue_number: int) -> dict[str, Any]:
    """Dispatch a repository_dispatch event to retrigger Kevin."""
    settings = get_settings()
    token = settings.KEVIN_GITHUB_TOKEN
    if not token:
        return {"error": "KEVIN_GITHUB_TOKEN not configured"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.github.com/repos/{repo}/dispatches",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "event_type": "kevin-run",
                "client_payload": {"issue_number": issue_number},
            },
        )
        # 204 No Content on success
        if resp.status_code == 204:
            return {"ok": True}
        return resp.json()
```

- [ ] **Step 4: Implement card update helpers**

Add to `backend/app/api/routes/bot.py`:

```python
async def _update_card_with(ctx: TurnContext, card: dict[str, Any]) -> None:
    """Replace the current card with a new one."""
    activity = Activity(
        type="message",
        id=ctx.activity.reply_to_id or (ctx.activity.id if ctx.activity else None),
        attachments=[Attachment(
            content_type="application/vnd.microsoft.card.adaptive",
            content=card,
        )],
    )
    await ctx.update_activity(activity)


async def _update_card_to_terminal(
    ctx: TurnContext,
    *,
    terminal_type: str,
    run_id: str,
    repo: str,
    pr_number: int | None,
    issue_number: int,
    issue_title: str = "",
    reason: str = "",
) -> None:
    """Update card to a terminal state (no action buttons)."""
    card = build_terminal_card(
        terminal_type=terminal_type,
        run_id=run_id,
        repo=repo,
        pr_number=pr_number,
        issue_number=issue_number,
        issue_title=issue_title,
        reason=reason,
    )
    await _update_card_with(ctx, card)
```

Also add the import of card builders at the top of the file. Since `build_run_status_card` is defined inline in bot.py, add `build_reject_form_card` and `build_terminal_card` as new functions in the same file (following the existing pattern), OR import from a shared module. Since ba-toolkit keeps card builders inline in bot.py, add them in the same file after `build_run_status_card` — copy the implementations from Task 4 Step 3.

- [ ] **Step 5: Implement `_handle_card_action` in BABot**

Update `BABot.on_message_activity` and add action handler:

```python
    async def on_message_activity(self, turn_context: TurnContext):
        _save_conversation_reference(turn_context)

        # Handle Action.Submit from Adaptive Cards
        value = turn_context.activity.value
        if value and isinstance(value, dict) and "action" in value:
            await self._handle_card_action(turn_context, value)
            return

        user_text = (turn_context.activity.text or "").strip()
        logger.info("Bot received message: %s", user_text)

        # 去掉 @mention 前缀 (existing code continues...)
```

```python
    async def _handle_card_action(self, ctx: TurnContext, value: dict) -> None:
        """Route Action.Submit from Adaptive Cards."""
        action = value.get("action", "")
        repo = value.get("repo", "")
        run_id = value.get("run_id", "")
        pr_number = value.get("pr_number")
        issue_number = value.get("issue_number")
        issue_title = value.get("issue_title", "")

        match action:
            case "approve":
                await _github_approve_pr(repo, pr_number)
                await _github_enable_automerge(repo, pr_number)
                await _update_card_to_terminal(
                    ctx, terminal_type="approved", run_id=run_id,
                    repo=repo, pr_number=pr_number,
                    issue_number=issue_number, issue_title=issue_title,
                )

            case "reject":
                card = build_reject_form_card(
                    run_id=run_id, repo=repo, pr_number=pr_number,
                    issue_number=issue_number, issue_title=issue_title,
                )
                await _update_card_with(ctx, card)

            case "reject_confirm":
                reason = value.get("reason", "No reason provided")
                comment_body = f"\u274c **Rejected via Teams**\n\n{reason}"
                await _github_post_comment(repo, pr_number, comment_body)
                await _github_close_pr(repo, pr_number)
                await _update_card_to_terminal(
                    ctx, terminal_type="rejected", run_id=run_id,
                    repo=repo, pr_number=pr_number,
                    issue_number=issue_number, issue_title=issue_title,
                    reason=reason,
                )

            case "reject_cancel":
                # Re-fetch payload from card_registry to rebuild completed card
                existing = _card_registry.get(run_id)
                if existing and existing.get("last_payload"):
                    card = build_run_status_card(existing["last_payload"])
                    await _update_card_with(ctx, card)

            case "retry":
                await _github_dispatch_retry(repo, issue_number)
                await _update_card_to_terminal(
                    ctx, terminal_type="retried", run_id=run_id,
                    repo=repo, pr_number=pr_number,
                    issue_number=issue_number, issue_title=issue_title,
                )

            case _:
                logger.warning("Unknown card action: %s", action)
```

- [ ] **Step 6: Update `_card_registry` to store last payload for reject_cancel**

In the `notify()` endpoint, update the registry entry to include the payload:

```python
# In notify(), when registering a new card (around line 633):
# BEFORE:
                        _card_registry[run_id] = {
                            "conversation_id": conv_id,
                            "activity_id": resp.id,
                        }

# AFTER:
                        _card_registry[run_id] = {
                            "conversation_id": conv_id,
                            "activity_id": resp.id,
                            "last_payload": payload,
                        }
```

- [ ] **Step 7: Run tests**

```bash
cd /Users/randy/Documents/code/ba2/ba-toolkit
python -m pytest backend/tests/test_bot_actions.py -x -v
```

Expected: All PASS.

- [ ] **Step 8: Run full ba-toolkit test suite**

```bash
python -m pytest backend/tests/ -x -q
```

Expected: All existing + new tests PASS.

- [ ] **Step 9: Commit**

```bash
cd /Users/randy/Documents/code/ba2/ba-toolkit
git add backend/app/api/routes/bot.py backend/tests/test_bot_actions.py
git commit -m "feat: add Teams card action handlers for approve/reject/retry

- Action.Submit routing in on_message_activity
- _github_approve_pr + _github_enable_automerge (GraphQL)
- _github_close_pr + _github_post_comment for reject flow
- _github_dispatch_retry for repository_dispatch retrigger
- Reject form card with required reason input
- Terminal state cards prevent duplicate actions"
```

---

## Phase 3: HITL Approval (F1)

### Task 7: ba-toolkit — Sync card builders with AgenticSDLC

**Files:**
- Modify: `backend/app/api/routes/bot.py` (ba-toolkit)

The card builders in ba-toolkit's `bot.py` need the same updates as AgenticSDLC's `cards.py`:
duration display, action buttons, reject form, and terminal states.

- [ ] **Step 1: Update `build_run_status_card` in ba-toolkit**

Replace the existing `build_run_status_card` function (lines 124-179 in ba-toolkit's `bot.py`) with the updated version that includes:
- Duration suffix in block lines (same as Task 3 Step 3)
- Action.Submit buttons for approve/reject/retry (same as Task 3 Step 7)

```python
def build_run_status_card(payload: dict[str, Any]) -> dict[str, Any]:
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

    block_lines = []
    for b in blocks:
        icon = _status_icon(b.get("status", "pending"))
        duration = _format_duration(b.get("duration_seconds"))
        suffix = f" ({duration})" if duration else ""
        block_lines.append(f"{icon} **{b['block_id']}**: {b['name']}{suffix}")
    blocks_text = "\n\n".join(block_lines) if block_lines else "No blocks"

    body: list[dict[str, Any]] = [
        {"type": "TextBlock", "text": title, "size": "large", "weight": "bolder", "color": _header_color(status)},
        {"type": "FactSet", "facts": [
            {"title": "Issue", "value": f"#{issue_number} {issue_title}"},
            {"title": "Repo", "value": repo},
            {"title": "Blueprint", "value": blueprint_id},
            {"title": "Run", "value": run_id},
        ]},
        {"type": "TextBlock", "text": "**Blocks**", "weight": "bolder", "spacing": "medium"},
        {"type": "TextBlock", "text": blocks_text, "wrap": True},
    ]

    if error:
        body.append({"type": "TextBlock", "text": f"\u274c **Error**: {error}", "color": "attention", "wrap": True, "spacing": "medium"})

    actions: list[dict[str, Any]] = []

    # Action.Submit buttons
    if status == "completed" and pr_number:
        submit_data_base = {
            "run_id": run_id,
            "repo": repo,
            "pr_number": pr_number,
            "issue_number": issue_number,
            "issue_title": issue_title,
        }
        actions.append({
            "type": "Action.Submit",
            "title": "Approve",
            "style": "positive",
            "data": {**submit_data_base, "action": "approve"},
        })
        actions.append({
            "type": "Action.Submit",
            "title": "Reject",
            "style": "destructive",
            "data": {**submit_data_base, "action": "reject"},
        })
    elif status == "failed":
        actions.append({
            "type": "Action.Submit",
            "title": "Retry",
            "data": {
                "action": "retry",
                "run_id": run_id,
                "repo": repo,
                "issue_number": issue_number,
                "issue_title": issue_title,
            },
        })

    # OpenUrl buttons
    if repo and issue_number:
        actions.append({"type": "Action.OpenUrl", "title": "View Issue", "url": f"https://github.com/{repo}/issues/{issue_number}"})
    if pr_number and repo:
        actions.append({"type": "Action.OpenUrl", "title": "View PR", "url": f"https://github.com/{repo}/pull/{pr_number}"})
    if logs_url:
        actions.append({"type": "Action.OpenUrl", "title": "View Logs", "url": logs_url})

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "actions": actions,
    }
```

Also add `_format_duration` helper (same as `format_duration` from Task 3, renamed with underscore to match ba-toolkit's private convention):

```python
def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    return f"{minutes}m{secs}s"
```

- [ ] **Step 2: Add `build_reject_form_card` and `build_terminal_card` to ba-toolkit**

Copy the implementations from Task 4 Step 3 into `backend/app/api/routes/bot.py`, after `build_run_status_card`.

- [ ] **Step 3: Run ba-toolkit tests**

```bash
cd /Users/randy/Documents/code/ba2/ba-toolkit
python -m pytest backend/tests/ -x -q
```

Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
cd /Users/randy/Documents/code/ba2/ba-toolkit
git add backend/app/api/routes/bot.py
git commit -m "feat: sync card builders — duration, action buttons, terminal states

Update build_run_status_card with duration suffix and Action.Submit
buttons. Add build_reject_form_card and build_terminal_card."
```

---

### Task 8: E2E Verification

**No code changes.** Manual testing against live environment.

- [ ] **Step 1: Deploy ba-toolkit changes**

```bash
cd /Users/randy/Documents/code/ba2/ba-toolkit
# Deploy per existing process (Azure Container Apps)
```

- [ ] **Step 2: Update target repo workflow**

Copy the updated `kevin-caller-template.yaml` to `centific-cn/kevin-test-target/.github/workflows/kevin.yaml` (add `repository_dispatch` trigger).

- [ ] **Step 3: Configure branch protection on target repo**

In GitHub Settings → Branches → Branch protection rules for `main`:
- [x] Require pull request reviews before merging (1 approval)
- [x] Dismiss stale pull request reviews
- [x] Require status checks to pass before merging
- [x] Allow auto-merge

- [ ] **Step 4: Run E2E checklist**

```
[ ] Trigger Issue #6 → observe block duration display on Card
[ ] Completed Card shows Approve / Reject buttons
[ ] Click Approve → PR review approved + auto-merge enabled
[ ] Click Reject → reject form with text input appears
[ ] Fill reason + Confirm → PR closed + Issue comment with reason
[ ] Click Cancel → back to Completed Card
[ ] Trigger failure scenario → Retry button on Card
[ ] Click Retry → new workflow run starts
[ ] Double-click any button → no duplicate operations
[ ] Auto-merge after CI failure → auto-merge cancelled
```

- [ ] **Step 5: Document results**

Create session report at `docs/2026-03-28-session2-hitl-retry-duration-report.md` with test results and any issues found.

---

## Architectural Decision: F1 Control Plane

> **Decision required before Task 6 implementation.**

The HITL approval in this plan uses **Teams as a lightweight frontend that triggers GitHub native actions**:
- Approve = GitHub PR review approve + auto-merge (GitHub controls merge)
- Reject = GitHub PR close + comment (GitHub records the decision)
- State of truth = GitHub PR status (not bot memory)

This means:
- `kevin-hitl.yaml` (if it exists) remains a separate concern for workflow-level continuation
- The bot does NOT maintain its own approval state machine
- If Teams is down, users can still approve/reject directly on GitHub

**Alternative not chosen:** Bot-driven approval where the bot owns the approval state and orchestrates merge. Rejected because it creates a second source of truth and requires persistent state that survives bot restarts.

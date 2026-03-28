# Kevin HITL Approval, One-Click Retry & Block Duration Display

> Date: 2026-03-28
> Status: Draft
> Scope: Teams Card 交互升级 — 审批闭环、失败重跑、耗时可视化

---

## 1. Overview

将 Kevin 的 Teams 体验从"只读通知"升级为"可操作的控制面板"。用户全程不离开 Teams 即可完成：触发 → 追踪 → 审批/拒绝 → 重跑。

### 三个功能

| # | 功能 | 用户价值 |
|---|------|---------|
| F1 | HITL 审批（Approve / Reject PR） | 在 Teams 里决策，不跳转 GitHub |
| F2 | 一键重跑（Retry） | 失败后零摩擦重试 |
| F3 | Block 耗时显示 | 建立"正常/异常"直觉 |

### 设计决策摘要

| 决策点 | 选择 | 理由 |
|--------|------|------|
| HITL 切入点 | PR 创建后（非 B2 后） | PR 是天然审批载体，避免流水线暂停复杂度 |
| Approve 行为 | GitHub PR review approve + 启用 auto-merge + 等 CI 绿灯 | 最安全，CI 失败自动取消 |
| CI 失败/新 push | 取消 auto-merge，需重新 Approve | 最严格策略，适合核心代码库 |
| Reject 行为 | 关闭 PR + 保留 Issue + 强制填写理由 | 需求不消失，理由作为上下文 |
| Retry 触发 | repository_dispatch（非 label 增删） | 语义清晰，可扩展，无 race condition |
| 耗时显示 | 仅完成后显示（非实时计时） | Adaptive Card 无客户端 timer 能力 |
| Card 按钮类型 | Action.Submit（非 Action.Execute） | 最简单，兼容所有 Teams 客户端 |
| GitHub API 调用方 | ba-toolkit bot handler 直接调用 | 最短路径，现有 PAT 权限足够 |

---

## 2. Payload Extension

### Kevin CLI → ba-toolkit 的 notify payload 新增字段

现有 payload 结构不变，新增以下字段：

```json
{
  "event": "run_completed",
  "run_id": "20260328-120000-abc123",
  "issue_number": 6,
  "issue_title": "Implement LRU Cache",
  "repo": "centific-cn/kevin-test-target",
  "blueprint_id": "bp_coding_task.1.0.0",
  "status": "completed",
  "blocks": [
    {
      "block_id": "B1",
      "name": "Architecture Review",
      "status": "passed",
      "duration_seconds": 32
    },
    {
      "block_id": "B2",
      "name": "Implementation",
      "status": "passed",
      "duration_seconds": 133
    },
    {
      "block_id": "B3",
      "name": "Create PR",
      "status": "passed",
      "duration_seconds": 3
    }
  ],
  "pr_number": 7,
  "pr_url": "https://github.com/centific-cn/kevin-test-target/pull/7",
  "logs_url": "https://github.com/centific-cn/AgenticSDLC/actions/runs/789456123"
}
```

**新增字段：**

| 字段 | 类型 | 何时填充 | 来源 |
|------|------|---------|------|
| `blocks[].duration_seconds` | `float \| null` | block 完成后 | `completed_at - started_at` |
| `pr_number` | `int \| null` | run_completed 且 B3 passed | B3 stdout 正则提取 |
| `pr_url` | `str \| null` | 同上 | 拼接 `repo` + `pr_number` |

---

## 3. Adaptive Card States

### 3.1 Running Card（改动：加耗时）

```
+-------------------------------------------+
| (accent) Kevin Running                     |
| Issue    #6 Implement LRU Cache           |
| Repo     centific-cn/kevin-test-target    |
|                                            |
| Blocks                                     |
| ** B1 (32s)  ** B2  ** B3                  |
|                                            |
+-------------------------------------------+
```

已完成的 block 显示耗时，运行中和待运行的不显示。

### 3.2 Completed Card（改动：加 Approve/Reject 按钮 + 耗时）

```
+-------------------------------------------+
| (good) Kevin Completed                     |
| Issue    #6 Implement LRU Cache           |
| Repo     centific-cn/kevin-test-target    |
|                                            |
| Blocks                                     |
| ** B1 (32s)  ** B2 (2m13s)  ** B3 (3s)    |
|                                            |
| [Approve]  [Reject]  [View PR]           |
+-------------------------------------------+
```

按钮 payload：

```json
// Approve
{"action": "approve", "run_id": "...", "repo": "...", "pr_number": 7, "issue_number": 6}

// Reject
{"action": "reject", "run_id": "...", "repo": "...", "pr_number": 7, "issue_number": 6}
```

### 3.3 Failed Card（改动：加 Retry 按钮 + 耗时）

```
+-------------------------------------------+
| (attention) Kevin Failed                   |
| Issue    #6 Implement LRU Cache           |
| Repo     centific-cn/kevin-test-target    |
|                                            |
| Blocks                                     |
| ** B1 (32s)  ** B2 (45s)  ** B3            |
| Error: [B2] test_cache.py assertion failed |
|                                            |
| [Retry]  [View Logs]                      |
+-------------------------------------------+
```

按钮 payload：

```json
{"action": "retry", "run_id": "...", "repo": "...", "issue_number": 6}
```

### 3.4 Reject Form Card（新状态）

点 Reject 后 Card 原地更新为输入表单：

```
+-------------------------------------------+
| (warning) Rejecting PR #7                  |
| Issue    #6 Implement LRU Cache           |
|                                            |
| Rejection reason (required):               |
| +---------------------------------------+ |
| |                                       | |
| +---------------------------------------+ |
|                                            |
| [Confirm Reject]  [Cancel]               |
+-------------------------------------------+
```

Confirm 按钮 payload：

```json
{"action": "reject_confirm", "run_id": "...", "repo": "...", "pr_number": 7, "issue_number": 6, "reason": "..."}
```

Cancel 按钮 payload：

```json
{"action": "reject_cancel", "run_id": "...", "repo": "...", "pr_number": 7, "issue_number": 6}
```

### 3.5 Terminal States（按钮消失，防止重复操作）

**Approved：**

```
+-------------------------------------------+
| (good) PR #7 Approved                      |
| Issue    #6 Implement LRU Cache           |
| Auto-merge enabled, waiting for CI         |
|                                            |
| [View PR]  [View Issue]                   |
+-------------------------------------------+
```

**Rejected：**

```
+-------------------------------------------+
| (attention) PR #7 Rejected                 |
| Issue    #6 Implement LRU Cache           |
| Reason: edge case handling insufficient    |
|                                            |
| [View Issue]                               |
+-------------------------------------------+
```

**Retried：**

```
+-------------------------------------------+
| (accent) Retry Triggered                   |
| Issue    #6 Implement LRU Cache           |
| New run dispatched                         |
|                                            |
| [View Issue]                               |
+-------------------------------------------+
```

---

## 4. ba-toolkit Bot Handler

### 4.1 Action Submit 处理入口

`Action.Submit` 通过 Bot Framework 的 `on_message_activity` 回调进入。当 `activity.value` 包含 `action` 字段时，分发到对应 handler。

```
on_message_activity
  ├─ activity.value has "action"? → _handle_card_action()
  └─ else → existing text command handling
```

### 4.2 Action Handlers

**_approve_pr(ctx, value):**

1. `POST /repos/{repo}/pulls/{pr}/reviews` — body: `{"event": "APPROVE"}`
2. GraphQL `enablePullRequestAutoMerge` — mergeMethod: `SQUASH`
3. Update Card → Approved 终态

**_show_reject_form(ctx, value):**

1. Build reject form card (Input.Text + Confirm/Cancel buttons)
2. Update Card → Reject Form 状态
3. 保留 `run_id`, `repo`, `pr_number`, `issue_number` 在按钮 payload 中

**_reject_pr(ctx, value):**

1. `POST /repos/{repo}/issues/{pr}/comments` — body 包含拒绝理由
2. `PATCH /repos/{repo}/pulls/{pr}` — body: `{"state": "closed"}`
3. Update Card → Rejected 终态

**_restore_completed_card(ctx, value):**

1. 用 `run_id` 从 `_card_registry` 恢复原 Completed Card（带 Approve/Reject 按钮）
2. Update Card → 回到 3.2 Completed 状态

**_retry_run(ctx, value):**

1. `POST /repos/{repo}/dispatches` — body: `{"event_type": "kevin-run", "client_payload": {"issue_number": N}}`
2. Update Card → Retried 终态

### 4.3 幂等性

所有 action handler 在执行 GitHub API 调用前，先检查当前状态：

- Approve：检查 PR 是否已 merged/closed → 已处理则跳过，直接更新 Card
- Reject：检查 PR 是否已 closed → 已处理则跳过
- Retry：无需检查（workflow dispatch 是幂等的，concurrency group 会取消旧 run）

### 4.4 Card 更新机制

所有 handler 通过 `_update_card()` 更新 Teams Card：

```python
async def _update_card(self, ctx: TurnContext, run_id: str, card: dict) -> None:
    existing = _card_registry.get(run_id)
    if not existing:
        return
    activity = Activity(
        type="message",
        id=existing["activity_id"],  # 从 registry 获取原 Card 的 activity ID
        attachments=[Attachment(
            content_type="application/vnd.microsoft.card.adaptive",
            content=card,
        )],
    )
    await ctx.update_activity(activity)
```

### 4.5 GitHub Token

使用现有的 `CHECKOUT_TOKEN`（PAT with `repo` scope）。所需权限：

| 操作 | API | 所需权限 |
|------|-----|---------|
| Create PR review | `POST /repos/{repo}/pulls/{pr}/reviews` | `repo` |
| Enable auto-merge | GraphQL `enablePullRequestAutoMerge` | `repo` |
| Close PR | `PATCH /repos/{repo}/pulls/{pr}` | `repo` |
| Post comment | `POST /repos/{repo}/issues/{pr}/comments` | `repo` |
| Workflow dispatch | `POST /repos/{repo}/dispatches` | `repo` |

---

## 5. Kevin CLI Changes

### 5.1 Block Duration 计算

在 `_notify_teams()` 中，构建 `block_list` 时计算耗时：

```python
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

### 5.2 PR Number 提取

从 B3 的 `output_summary` 中正则提取 PR number：

```python
def _extract_pr_number(run: RunState) -> int | None:
    b3 = run.blocks.get("B3")
    if not b3 or not b3.output_summary:
        return None
    match = re.search(r"github\.com/[^/]+/[^/]+/pull/(\d+)", b3.output_summary)
    return int(match.group(1)) if match else None
```

在 `run_completed` 事件中调用，填充 `pr_number` 和 `pr_url`。

### 5.3 确认 started_at / completed_at 写入

验证 `_execute_blocks()` 中 `BlockState.started_at` 和 `completed_at` 被正确设置。如果当前未设置，需补充：

```python
# block 开始时
bs.started_at = datetime.now(timezone.utc).isoformat()

# block 完成时（passed 或 failed）
bs.completed_at = datetime.now(timezone.utc).isoformat()
```

---

## 6. Retry Trigger Mechanism

### 6.1 repository_dispatch

ba-toolkit bot 通过 GitHub API 触发 `repository_dispatch` 事件：

```python
# POST https://api.github.com/repos/{repo}/dispatches
{
    "event_type": "kevin-run",
    "client_payload": {
        "issue_number": 6
    }
}
```

### 6.2 Caller Workflow 改动

```yaml
# kevin-caller-template.yaml
on:
  issues:
    types: [labeled]
  repository_dispatch:
    types: [kevin-run]

jobs:
  kevin:
    if: >-
      (github.event_name == 'issues' && github.event.label.name == 'kevin') ||
      github.event_name == 'repository_dispatch'
    uses: centific-cn/AgenticSDLC/.github/workflows/kevin-reusable.yaml@main
    with:
      issue_number: >-
        ${{ github.event.issue.number || github.event.client_payload.issue_number }}
      issue_title: >-
        ${{ github.event.issue.title || github.event.client_payload.issue_title || '' }}
      repo: ${{ github.repository }}
    secrets:
      # ...existing secrets unchanged...
```

### 6.3 issue_title 处理

`repository_dispatch` 的 `client_payload` 中没有 `issue_title`。两种处理方式：

- **简单方案**：ba-toolkit 在 dispatch 前先查 GitHub API 获取 issue title，放入 `client_payload`
- **更简单方案**：Kevin CLI 启动时从 GitHub API 获取 issue 信息（已有此逻辑），workflow 传空字符串即可

采用更简单方案：workflow 中 `issue_title` 允许为空，Kevin CLI 自行获取。

---

## 7. Auto-merge Cancellation & Re-approval

### 7.1 GitHub 原生行为

| 场景 | GitHub 行为 |
|------|------------|
| CI 失败 | auto-merge 自动取消 |
| 新 push 到 PR branch | 取决于 branch protection "Dismiss stale PR reviews" 设置 |

### 7.2 Branch Protection 配置要求

目标 repo 需启用：

- **Require pull request reviews before merging** — 至少 1 个 approval
- **Dismiss stale pull request reviews** — 新 push 后旧 approval 失效
- **Require status checks to pass before merging** — CI 必须通过
- **Allow auto-merge** — 启用 auto-merge 功能

### 7.3 Re-approval 通知

当 auto-merge 被取消时（CI 失败或 review dismissed），用户需要知道。

**实现方式**：不主动轮询。当用户在 Teams 执行 `status #6` 命令时，查询 PR 当前状态并显示是否需要重新审批。

**未来增强**：可通过 GitHub Webhook 监听 `pull_request_review` 和 `check_suite` 事件主动推送，但不在本次 MVP 范围内。

---

## 8. Files Changed

### AgenticSDLC repo

| File | Change |
|------|--------|
| `kevin/cli.py` | `_notify_teams()` 新增 `duration_seconds`, `pr_number`, `pr_url` |
| `kevin/teams_bot/cards.py` | 新增 5 种 Card 状态构建函数 |
| `.github/workflows/kevin-caller-template.yaml` | 新增 `repository_dispatch` trigger |

### ba-toolkit repo

| File | Change |
|------|--------|
| `backend/app/api/routes/bot.py` | 新增 `_handle_card_action()` 及 5 个 action handler |
| `backend/app/api/routes/bot.py` | `build_run_status_card()` 更新支持耗时、按钮 |

### Target repo（每个接入 Kevin 的 repo）

| File | Change |
|------|--------|
| `.github/workflows/kevin.yaml` | 新增 `repository_dispatch` trigger（从更新后的 template 复制） |

---

## 9. Test Strategy

### 9.1 Unit Tests（自动化）

**kevin/tests/test_cards.py（新增）：**

- should build card with duration when blocks have timestamps
- should build card with approve/reject buttons when status is completed
- should build card with retry button when status is failed
- should build reject form card with input field
- should build terminal card without buttons after action taken
- should omit duration when block has no completed_at
- should format duration as seconds for < 60s and minutes for >= 60s

**kevin/tests/test_cli.py（扩展）：**

- should include duration_seconds in notify payload
- should include pr_number when B3 output contains PR URL
- should extract pr_number from various gh pr create output formats
- should return None when B3 output has no PR URL

### 9.2 Integration Tests（自动化，mock GitHub API）

**ba-toolkit/tests/test_bot_actions.py（新增）：**

- should call GitHub approve review API on approve action
- should enable auto-merge on approve action
- should update card to approved terminal state
- should show reject form on reject action
- should close PR and post comment on reject_confirm with reason
- should dispatch repository_dispatch on retry action
- should ignore duplicate approve when PR already merged
- should ignore duplicate reject when PR already closed

### 9.3 E2E Verification（手动）

```
[ ] 触发 Issue #6 → 观察 block 耗时显示
[ ] 成功后 Card 出现 Approve / Reject 按钮
[ ] 点 Approve → PR review approved + auto-merge 启用
[ ] 点 Reject → 出现理由输入框
[ ] 填写理由 + 确认 → PR 关闭 + Issue 评论包含理由
[ ] 点 Cancel → 回到 Completed Card
[ ] 触发失败场景 → Card 出现 Retry 按钮
[ ] 点 Retry → 新 workflow run 启动
[ ] 重复点击按钮 → 不产生重复操作
[ ] auto-merge 后 CI 失败 → auto-merge 取消
```

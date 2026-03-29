# Kevin Session 1 — Block-Level Notifications & Reliability Fixes

> Date: 2026-03-28
> Duration: ~2.5 hours
> Scope: Teams 实时通知 + 失败诊断 + B3 幂等性 + Workflow 基础设施修复

---

## Executive Summary

本 session 目标是将 Kevin 的 Teams 集成从"开始/结束通知"升级为"Block 级实时进度推送"，同时修复失败时的诊断能力和重跑幂等性。

实际执行中，暴露并修复了 **4 个基础设施级问题**（Reusable Workflow 跨 repo 访问、Secret 传递机制、URL 配置错误、B3 push 冲突），使得原计划的 30 分钟 quick wins 扩展为完整的可靠性加固 session。

**最终成果**：Kevin 从"黑盒执行"变为"Teams 内可观测的实时流水线"，每个 Block 的启动、完成、失败都有可视化反馈。

---

## Delivered Changes

### 1. Block 级实时 Teams 通知

**文件**: `kevin/cli.py`

**改动**:
- `_execute_blocks()` 在每个 block 开始前调用 `_notify_teams(status="running")`
- Teams Adaptive Card 原地更新（通过 ba-toolkit 的 `_card_registry` + `update_activity`）
- 用户在 Teams 中看到的效果：

```
Block B1 开始 → Card: 🔄 B1  ⏳ B2  ⏳ B3
Block B2 开始 → Card: ✅ B1  🔄 B2  ⏳ B3    ← 原地更新
Block B3 开始 → Card: ✅ B1  ✅ B2  🔄 B3    ← 原地更新
完成          → Card: ✅ B1  ✅ B2  ✅ B3     [View Issue] [View PR] [View Logs]
```

**通知时序（实测 7 次 /api/notify，全部 200 OK）**:

| 时间 | 来源 | 事件 |
|------|------|------|
| +0s | Workflow curl | `run_started` |
| +1s | Kevin cli.py | `block_update` (B1 🔄) |
| +32s | Kevin cli.py | `block_update` (B2 🔄) |
| +165s | Kevin cli.py | `block_update` (B3 🔄) |
| +168s | Kevin cli.py | `run_completed` ✅ |
| +170s | Workflow curl | `run_completed` |

### 2. 失败时错误摘要 + GitHub Actions 日志链接

**文件**: `kevin/cli.py`, `kevin/teams_bot/cards.py`

**改动**:
- `_notify_teams()` 新增 `error` 和 `logs_url` 参数
- 失败时从 `run.blocks` 提取 failed block 的 stderr（截断 300 字符）
- 从 `GITHUB_RUN_ID` + `GITHUB_REPOSITORY` 环境变量构造 Actions logs URL
- `cards.py` 新增 "View Logs" 按钮（`logs_url` 存在时显示）

**失败 Card 效果**:
```
┌─────────────────────────────────────┐
│ ❌ Kevin Failed                      │
│ Issue    #6 Implement LRU Cache     │
│ ✅ B1  ✅ B2  ❌ B3                  │
│ ❌ Error: [B3] push rejected...     │
│ [View Issue] [View Logs]            │
└─────────────────────────────────────┘
```

### 3. B3 幂等性修复

**文件**: `blueprints/bp_coding_task.1.0.0.yaml`

**问题**: Kevin 重跑同一 issue 时，`kevin/issue-N` 分支已存在，`--force-with-lease` 因 fresh clone 缺少 remote ref 而失败。

**修复逻辑**:
```
PR 已 merged? → skip B3, exit 0
      ↓ no
git fetch origin (获取 remote ref)
      ↓
git push --force-with-lease (安全覆盖)
      ↓
PR 已 open? → 打印 "updated", exit 0
      ↓ no
gh pr create (创建新 PR)
```

**验证**: 对 issue #6 连续跑 3 次，B3 在第 2、3 次均 PASSED（更新已有 PR #7）。

### 4. Reusable Workflow 基础设施修复

**文件**: `.github/workflows/kevin-reusable.yaml`, `.github/workflows/kevin-caller-template.yaml`

修复了 4 个阻塞 reusable workflow 跨 repo 调用的问题：

| 问题 | 根因 | 修复 |
|------|------|------|
| Job 0 个，秒失败 | AgenticSDLC `access_level: none` | 改为 `organization` |
| Job 无 steps，秒失败 | Caller 缺少 `permissions` 块 | 添加 `issues: write` 等 |
| Secrets 全部为空 | `secrets: inherit` + `required: true` 冲突 | 改为 `required: false` |
| Secrets 仍为空 | Org secrets 在 GitHub Free plan 不生效 | 恢复 repo-level secrets |

### 5. ba-toolkit View Logs 按钮

**文件**: `ba-toolkit/backend/app/api/routes/bot.py`（外部 repo）

`build_run_status_card()` 新增 `logs_url` 字段解析和 "View Logs" Action 按钮。待 ba-toolkit 部署后生效。

---

## Infrastructure Discoveries

### GitHub Free Plan 不支持 Org-Level Secrets

**现象**: 通过 API 成功创建 org secrets（visibility: `private`），API 查询显示对 target repo 可见，但 Actions runner 注入的值为空字符串。

**验证方法**: 创建 debug workflow，用 `${{ secrets.X != '' }}` 表达式检测。repo-level secrets 返回 `true`，org-level 返回 `false`。

**根因**: `centific-cn` 是 GitHub Free plan，org secrets 是 Team/Enterprise 功能。API 不阻止创建，但 runner 不注入。

**决策**: 放弃 org secrets 方案，恢复 repo-level secrets。新 repo 接入需配 10 个 secrets（而非理想的 1 个）。

**未来**: 升级到 GitHub Team plan 后可重新启用 org secrets。

### `secrets: inherit` 行为

| 场景 | 结果 |
|------|------|
| Caller `secrets: inherit` + Reusable 声明 `required: true` | ❌ Job dispatch 失败（Free plan） |
| Caller `secrets: inherit` + Reusable 声明 `required: false` | ❌ Secrets 为空（Free plan） |
| Caller `secrets: inherit` + Reusable 无声明 | ❌ Secrets 为空 |
| Caller 显式传 `secrets: {X: ${{ secrets.X }}}` | ✅ 正常工作 |

**结论**: 在 GitHub Free plan 下，必须显式传递 secrets，`secrets: inherit` 不可靠。

### TEAMS_BOT_URL 尾部空格

Kevin 的 `_notify_teams()` 日志中：
```
URL can't contain control characters.
'ba-toolkit-backend.orangemushroom-fca5a6c5.eastus.azurecontainerapps.io '
                                                                          ^ trailing space
```

**根因**: 用户通过 `gh secret set` 交互式输入时，末尾多了一个空格。

**修复**: `gh secret set TEAMS_BOT_URL --body "https://..."` 使用 `--body` 显式传值避免交互式输入的尾部空白。

---

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `kevin/cli.py` | Block 通知 + error summary + logs_url | +46 |
| `kevin/teams_bot/cards.py` | View Logs 按钮 | +142 (new) |
| `blueprints/bp_coding_task.1.0.0.yaml` | B3 幂等性 | +17/-3 |
| `.github/workflows/kevin-reusable.yaml` | Secret 声明 required: false | +6/-6 |
| `.github/workflows/kevin-caller-template.yaml` | Permissions + explicit secrets | +23/-3 |
| `kevin/tests/test_blueprint_loader.py` | 修复 timeout 断言 | +67 (new) |
| `ba-toolkit/.../bot.py` | logs_url + View Logs 按钮 | +2 (外部 repo) |

**Commits**: 7 (AgenticSDLC) + 1 pending (ba-toolkit)

---

## Test Results

```
$ python -m pytest kevin/tests/ -x -q
76 passed in 54.93s
```

## End-to-End Verification

| 测试 | Issue | 结果 |
|------|-------|------|
| LRU Cache 首次运行 | #6 | ✅ B1→B2→B3 全部 passed，PR #7 创建 |
| LRU Cache 重跑（幂等性） | #6 | ✅ B3 fetch + force-push + "PR updated" |
| Teams 通知 — block_update | #6 | ✅ 7 次 /api/notify 全部 200 OK |
| Teams 通知 — run_completed | #6 | ✅ Adaptive Card 实时更新 |

---

## Architecture (After)

```
                    ┌─────────────────────────────────┐
                    │         Microsoft Teams          │
                    │                                  │
                    │  Adaptive Card (原地更新)         │
                    │  🔄 B1 → ✅ B1 → ✅ B1          │
                    │  ⏳ B2   🔄 B2   ✅ B2          │
                    │  ⏳ B3   ⏳ B3   ✅ B3          │
                    │  [View Issue] [View PR] [Logs]   │
                    └──────────▲───────────────────────┘
                               │ update_activity
                    ┌──────────┴───────────────────────┐
                    │  ba-toolkit-backend (Azure)       │
                    │  POST /api/notify                 │
                    │  card_registry: run_id→activity_id│
                    └──────────▲───────────────────────┘
                               │ HTTP POST
          ┌────────────────────┼────────────────────────┐
          │                    │                         │
    Workflow curl         Kevin cli.py              Workflow curl
    (run_started)     (block_update ×3)          (run_completed)
                      (run_completed)
                      (run_failed + error)
          │                    │                         │
          └────────────────────┼────────────────────────┘
                    ┌──────────┴───────────────────────┐
                    │  GitHub Actions Runner            │
                    │  kevin-reusable.yaml@main         │
                    │  B1 → B2 → B3                    │
                    └──────────────────────────────────┘
```

---

## What's Next

| Priority | Item | Effort | Dependency |
|----------|------|--------|------------|
| **Now** | ba-toolkit 部署 View Logs 按钮 | 5 min | 代码已写好 |
| **Session 2** | HITL 审批 — Teams 内 Approve/Reject PR | ~2 天 | 无 |
| **Future** | 升级 GitHub Team plan → 启用 org secrets | 30 min + 费用 | 组织审批 |

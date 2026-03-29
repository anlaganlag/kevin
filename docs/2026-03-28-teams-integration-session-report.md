# Kevin Teams Integration — Session Report

> Date: 2026-03-28
> Duration: ~4 hours
> From: zero Teams integration → fully working Teams ↔ Kevin pipeline

---

## Executive Summary

在一个 session 内，将 Kevin AI Agent 系统与 Microsoft Teams 完全打通。团队现在可以**不离开 Teams**完成以下操作：

- 查看哪些 issue 待处理
- 一键触发 Kevin 自动编码
- 实时接收运行状态通知
- 点击链接查看 Issue / PR

---

## Before → After

```
BEFORE                              AFTER
─────                               ─────
打开 GitHub                         Teams 发 "list"
找到 Issue                          看到分类列表
手动加 kevin label                   发 "run #3"
切到 Actions 页面看进度              自动收到 Adaptive Card
刷新页面等结果                       Card 原地更新为 ✅/❌
打开 PR 链接                         Card 上直接点 View PR
```

---

## Delivered Features

### 1. Teams Bot 基础设施

| 资源 | 详情 |
|------|------|
| Azure Bot Service | ba-toolkit-bot (F0 免费) |
| 部署位置 | 集成在 ba-toolkit-backend (Azure Container Apps) |
| 月成本增量 | $0（复用已有基础设施） |

### 2. 命令系统

在 Teams 对话中可用的命令：

```
help                              → 显示命令菜单
ping                              → 检查连接
run #3                            → 触发 Kevin 执行 issue #3
run centific-cn/other-repo#5      → 指定 repo 触发
status #3                         → 查看 issue 状态
list                              → 查看 issue 分类列表
list centific-cn/other-repo       → 指定 repo 查看
```

### 3. 通知推送

Kevin 运行时自动推送 Adaptive Card 到 Teams：

```
┌─────────────────────────────────────┐
│ 🔄 Kevin Running                    │
│                                     │
│ Issue    #3 [TASK] 测试Teams bot    │
│ Repo     centific-cn/kevin-test     │
│ Blueprint bp_coding_task.1.0.0      │
│                                     │
│ ✅ B1: analyze_requirements         │
│ 🔄 B2: implement_solution           │
│ ⏳ B3: create_pull_request           │
│                                     │
│ [View Issue]                        │
└─────────────────────────────────────┘
        │
        ▼ (完成后原地更新，不发新消息)
┌─────────────────────────────────────┐
│ ✅ Kevin Completed                   │
│ ...                                 │
│ ✅ B1: analyze_requirements          │
│ ✅ B2: implement_solution            │
│ ✅ B3: create_pull_request           │
│                                     │
│ [View Issue] [View PR]              │
└─────────────────────────────────────┘
```

### 4. Issue 列表看板

`list` 命令返回按状态分类的 Adaptive Card：

```
┌─────────────────────────────────────┐
│ 📋 centific-cn/kevin-test-target    │
│                                     │
│ 🔄 Running (1)                      │
│   #8 Add caching layer    [link]   │
│                                     │
│ 📥 Ready (2)                        │
│   #5 Add login page       [link]   │
│   #7 Fix search bug       [link]   │
│                                     │
│ ✅ Completed (3)                     │
│   #3 测试Teams bot        [link]   │
│   #1 Add /health endpoint [link]   │
│                                     │
│ View all issues on GitHub           │
└─────────────────────────────────────┘
```

分类规则：
- **Running**: 有 `kevin` label（Kevin 正在跑）
- **Ready**: 有 task label 但没有 `kevin`（可以触发）
- **Completed**: 有 `kevin-completed` label

### 5. Reusable Workflow

新 repo 接入 Kevin 从 **配置 100+ 行 YAML + 7 个 secrets** 简化为：

```yaml
# .github/workflows/kevin.yaml — 只需 20 行
name: Kevin Planning Agent
on:
  issues:
    types: [labeled]
concurrency:
  group: kevin-issue-${{ github.event.issue.number }}
  cancel-in-progress: true
jobs:
  kevin:
    if: github.event.label.name == 'kevin'
    uses: centific-cn/AgenticSDLC/.github/workflows/kevin-reusable.yaml@main
    with:
      issue_number: ${{ github.event.issue.number }}
      issue_title: ${{ github.event.issue.title }}
      repo: ${{ github.repository }}
    secrets: inherit
```

所有逻辑在 AgenticSDLC 的 reusable workflow 里，更新一处全局生效。

### 6. Bug Fixes & Reliability

| Fix | 问题 | 解决 |
|-----|------|------|
| `--cwd` flag | Claude CLI 不支持 `--cwd` | 改用 `subprocess.Popen(cwd=)` |
| B3 幂等性 | 重跑 issue 时 branch 冲突 | `--force-with-lease` + PR 存在检测 |
| Cross-repo checkout | GITHUB_TOKEN 无法访问 AgenticSDLC | 使用 PAT (CHECKOUT_TOKEN) |
| PR 创建权限 | 组织限制 GITHUB_TOKEN 创建 PR | 使用 PAT |
| 千帆兼容 | Claude CLI 默认模型不被千帆支持 | 传入全套 ANTHROPIC_* 环境变量 |
| Label 生命周期 | Kevin 完成后 `kevin` label 不清理 | 自动切换为 `kevin-completed` |
| Block name 缺失 | 通知只显示 B1/B2/B3 没有名字 | GitHub 评论 + Teams Card 都带 block name |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Microsoft Teams                     │
│                                                       │
│  用户: "run #3"  ←→  Adaptive Card 通知               │
└────────┬─────────────────────────▲────────────────────┘
         │                         │
         ▼                         │
┌──────────────────────────────────┴────────────────────┐
│         ba-toolkit-backend (Azure Container Apps)      │
│                                                        │
│  POST /api/messages  ← Teams Bot Framework             │
│  POST /api/notify    ← GitHub Actions (curl)           │
│  POST /api/notify    ← Kevin CLI (_notify_teams)       │
│                                                        │
│  Command Handler: run / list / status / help / ping    │
│  Card Builder: run status card / issue list card       │
│  GitHub API: add label / list issues / get issue       │
└────────┬─────────────────────────▲────────────────────┘
         │ add "kevin" label       │ curl /api/notify
         ▼                         │
┌──────────────────────────────────┴────────────────────┐
│              GitHub Actions                            │
│                                                        │
│  kevin-caller (target repo)                            │
│    → kevin-reusable.yaml (AgenticSDLC)                 │
│      → python -m kevin run                             │
│        → B1: analyze → B2: implement → B3: PR          │
│        → _notify_teams() → /api/notify                 │
│        → label: kevin → kevin-completed                │
└───────────────────────────────────────────────────────┘
```

---

## Files Changed

### AgenticSDLC repo

| File | Change |
|------|--------|
| `.github/workflows/kevin.yaml` | 加 Teams 通知 + 千帆环境变量 + PAT |
| `.github/workflows/kevin-reusable.yaml` | **新建** — reusable workflow |
| `.github/workflows/kevin-caller-template.yaml` | **新建** — 20 行 caller 模板 |
| `kevin/cli.py` | 加 block name 到评论 + Teams 通知 + label 切换 |
| `kevin/agent_runner.py` | 移除 `--cwd` flag + 改进 validators |
| `blueprints/bp_coding_task.1.0.0.yaml` | B3 幂等性 + 移除硬编码 model |
| `docs/kevin-teams-integration-guide.md` | **新建** — 852 行深度接入文档 |
| `docs/superpowers/specs/2026-03-27-kevin-teams-bot-design.md` | **新建** — 设计 spec |

### ba-toolkit repo

| File | Change |
|------|--------|
| `backend/app/api/routes/bot.py` | 加 notify endpoint + run/list/status 命令 + Adaptive Card |
| `backend/app/config.py` | 加 `TEAMS_BOT_SECRET` + `KEVIN_GITHUB_TOKEN` |

### kevin-test-target repo

| File | Change |
|------|--------|
| `.github/workflows/kevin.yaml` | 从完整 workflow → 20 行 reusable caller |

---

## Secrets & Configuration

### centific-cn/kevin-test-target (repo secrets)

| Secret | Purpose |
|--------|---------|
| `CHECKOUT_TOKEN` | GitHub PAT — checkout + push + PR 创建 |
| `ANTHROPIC_API_KEY` | 千帆 API key |
| `ANTHROPIC_BASE_URL` | 千帆代理 URL |
| `ANTHROPIC_MODEL` | qianfan-code-latest |
| `ANTHROPIC_SMALL_FAST_MODEL` | qianfan-code-latest |
| `ANTHROPIC_DEFAULT_*_MODEL` | qianfan-code-latest (haiku/sonnet/opus) |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | 1 |
| `TEAMS_BOT_URL` | ba-toolkit-backend URL |

### Azure Container App (ba-toolkit-backend)

| Env Var | Purpose |
|---------|---------|
| `KEVIN_GITHUB_TOKEN` | Bot 调 GitHub API（add label / list issues） |

---

## What's Next

| Priority | Item | Effort |
|----------|------|--------|
| **Next session** | Phase 2: HITL 审批 — Teams 内 Approve/Reject PR | 2 天 |
| **Quick win** | Block 级实时通知 — 每个 block 开始时更新 Card | 1 小时 |
| **Optimization** | Org-level secrets — 避免每个 repo 重复配 | 30 min |
| **Enhancement** | 失败时 Card 附带错误摘要 + 日志链接 | 1 小时 |

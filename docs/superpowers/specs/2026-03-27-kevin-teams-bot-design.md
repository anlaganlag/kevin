# Kevin Teams Bot Integration Design

## Overview

将 Kevin agent 系统与 Microsoft Teams 打通，实现三个核心场景：
1. **触发执行** — 在 Teams 里通过 @mention 或命令菜单触发 Kevin 运行
2. **状态通知** — Kevin 运行状态实时推送到 Teams 频道（单 Card 更新）
3. **HITL 审批** — 在 Teams 内通过 Adaptive Card 完成 PR 审批，不跳转 GitHub

## Architecture

### 技术方案

Azure Bot Service + Bot Framework Python SDK，部署在 Azure App Service。

### 核心原则

- **Bot 是旁路，不是关键路径** — Bot 挂了，Kevin 通过 GitHub 仍然正常工作
- **幂等通知** — 同一个 event 多次推送不会产生重复 Card
- **优雅降级** — Card 更新失败就发新消息，GitHub API 失败就提示手动操作
- **无状态优先** — Card Registry 丢失后，最坏情况是发新 Card 而不是更新旧 Card

### 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                    Microsoft Teams                       │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │ @Kevin run   │  │ Adaptive Card│  │ 通知消息        │ │
│  │ 命令菜单     │  │ Approve/Reject│  │ 状态更新        │ │
│  └──────┬──────┘  └──────┬───────┘  └───────▲────────┘ │
└─────────┼────────────────┼──────────────────┼──────────┘
          │                │                  │
          ▼                ▼                  │
┌─────────────────────────────────────────────┴──────────┐
│              Azure Bot Service (Channel)                 │
└─────────────────────────┬──────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│           Kevin Teams Bot (Azure App Service)           │
│  ┌──────────┐  ┌───────────┐  ┌─────────────────────┐ │
│  │ Command   │  │ Approval  │  │ Notification        │ │
│  │ Handler   │  │ Handler   │  │ Service             │ │
│  └─────┬────┘  └─────┬─────┘  └──────────┬──────────┘ │
│        │              │                   │             │
│  ┌─────┴──────────────┴───────────────────┴──────────┐ │
│  │              Kevin Core (existing)                 │ │
│  │  intent.py │ blueprint_loader.py │ agent_runner.py │ │
│  └─────┬──────────────┬───────────────────┬──────────┘ │
└────────┼──────────────┼───────────────────┼────────────┘
         │              │                   │
         ▼              ▼                   ▼
┌──────────────┐ ┌─────────────┐  ┌──────────────────┐
│ GitHub API   │ │ .kevin/runs │  │ GitHub Actions   │
│ (gh CLI)     │ │ (State)     │  │ (CI runners)     │
└──────────────┘ └─────────────┘  └──────────────────┘
```

### 关键决策

Bot 本身不直接执行 Kevin 任务，而是通过 `workflow_dispatch` 触发 GitHub Actions 来执行：
- 执行环境不变（GitHub Actions runner）
- 不需要在 App Service 上装 Claude CLI
- Bot 只负责通信和状态中转

## Scenario 1: Trigger Execution

### 交互流

```
用户在 Teams:  @Kevin run anlaganlag/myrepo#42
        │
        ▼
Bot Command Handler:
  1. 解析命令 → repo: anlaganlag/myrepo, issue: #42
  2. 调 GitHub API 验证 issue 存在 + 有 kevin label
  3. 触发 GitHub Actions workflow_dispatch (kevin.yaml)
     传参: issue_number=42, repo=anlaganlag/myrepo
  4. 回复 Adaptive Card（运行已启动）
```

### 支持的命令

| 命令 | 说明 |
|------|------|
| `@Kevin run <repo>#<issue>` | 触发执行 |
| `@Kevin status <repo>#<issue>` | 查询最近一次 run 状态 |
| `@Kevin list-runs <repo>` | 列出最近 runs |
| `@Kevin dry-run <repo>#<issue>` | 试运行不实际执行 |
| `@Kevin help` | 显示命令菜单 |

命令菜单通过 Bot Command Menu 注册，Teams 输入框自动提示。

## Scenario 2: Status Notifications

### Card 更新机制

**一个 Run 只发一张 Card，后续状态更新同一张 Card**。

```
Run Started → Bot 发 Card → 保存 (conversation_id, activity_id, run_id) 映射
Block 完成  → Bot 查映射 → 用 activity_id 更新 Card 内容
Run 完成    → Bot 查映射 → 最终更新 Card + 如果有 PR 则追加审批 Card
```

### Card Registry 存储

```python
@dataclass(frozen=True)
class CardRecord:
    run_id: str
    conversation_id: str
    activity_id: str        # Teams 消息 ID，用于更新
    service_url: str        # Bot Framework 回调 URL
    created_at: datetime
```

第一版：内存 dict + JSON 文件持久化。后续可换 Redis / Azure Table Storage。

### 状态 Card 视觉

- 运行中：蓝色 header，block 状态列表（✅/🔄/⏳）
- 成功：绿色 header，附 PR 链接和日志链接
- 失败：红色 header，附失败 block + 错误摘要

### 通知触发方式

GitHub Actions 通过 `curl` 调 Bot 的 `/api/notify` endpoint：

```yaml
# kevin.yaml 中添加
env:
  TEAMS_BOT_URL: ${{ secrets.TEAMS_BOT_URL }}
  TEAMS_BOT_SECRET: ${{ secrets.TEAMS_BOT_SECRET }}

steps:
  - name: Notify Teams - Run Started
    run: |
      curl -X POST "$TEAMS_BOT_URL/api/notify" \
        -H "X-Bot-Secret: $TEAMS_BOT_SECRET" \
        -H "Content-Type: application/json" \
        -d '{"event":"run_started","issue":${{ github.event.inputs.issue_number }},...}'
```

更细粒度的 Block 级通知：改造 `agent_runner.py`，在每个 block 执行前后调 notify endpoint。通过环境变量 `TEAMS_BOT_URL` 判断是否启用。

## Scenario 3: HITL Approval

### 审批流程

```
Kevin 创建 PR → GitHub Actions curl /api/notify (event: approval_request)
       │
       ▼
Bot 发审批 Adaptive Card:
  - Issue 信息 + PR 信息
  - 变更摘要（文件列表 + diff stats）
  - [✅ Approve] [❌ Reject] [View PR ↗] 按钮
       │
       ▼ (用户点 Approve)
Bot Approval Handler:
  1. 验证 action.data 签名（HMAC 防篡改）
  2. 查 user_mapping：teams_email → github_username
  3. 检查权限：can_approve == true
  4. 调 GitHub API 提交 PR Review (APPROVE)
  5. 更新 Card → 「✅ 已审批 by @randy」，按钮灰掉
       │
       ▼
kevin-hitl.yaml 自动触发：merge PR + 清理分支
```

### Reject 流程

- 点 Reject → 弹出文本框输入拒绝原因
- Bot 在 PR 上发 review comment（request changes）
- Bot 在 issue 上 post comment 通知原因
- Card 更新为「❌ 已拒绝 by @randy — {reason}」

### User Mapping

```yaml
# config/user_mapping.yaml
mappings:
  - teams_email: "randy@company.com"
    github_username: "anlaganlag"
    can_approve: true
```

第一版 YAML 配置文件，后续可升级为 OAuth 绑定流程。

## Technical Implementation

### 项目结构

```
kevin/teams_bot/
├── app.py                  # FastAPI + Bot Framework 入口
├── bot.py                  # TeamsBot 主类，路由消息到 handlers
├── config.py               # Azure AD、Bot、GitHub 配置
├── handlers/
│   ├── command_handler.py  # 解析 @mention 命令 + 命令菜单
│   ├── approval_handler.py # Adaptive Card 按钮回调
│   └── notify_handler.py   # 接收 GitHub Actions 推送
├── cards/
│   ├── run_status.py       # 运行状态 Card 模板
│   ├── approval_request.py # 审批请求 Card 模板
│   └── card_builder.py     # Adaptive Card JSON 构建工具
├── services/
│   ├── github_service.py   # 封装 GitHub API（触发 workflow、审批 PR）
│   ├── user_mapping.py     # Teams User ↔ GitHub User 映射
│   └── state_service.py    # 查询 .kevin/runs 状态
├── models/
│   └── commands.py         # 命令解析模型（Pydantic）
└── deploy/
    ├── Dockerfile
    ├── app_service.bicep    # Azure App Service IaC
    └── bot_registration.bicep # Azure Bot Service IaC
```

### API Endpoints

| Endpoint | 来源 | 认证方式 |
|----------|------|---------|
| `POST /api/messages` | Azure Bot Service（Teams 消息） | Bot Framework JWT |
| `POST /api/notify` | GitHub Actions（状态推送） | Shared Secret (HMAC) |

### 核心依赖

```
botbuilder-core
botbuilder-integration-aiohttp
fastapi
uvicorn
pydantic
httpx
```

## Deployment

### Azure 资源清单

```
Resource Group: rg-kevin-teams-bot
├── App Service Plan (B1 tier)          # ~$13/月
│   └── App Service: kevin-teams-bot
│       ├── Python 3.11 runtime
│       ├── Always On: enabled
│       └── 环境变量:
│           ├── MICROSOFT_APP_ID
│           ├── MICROSOFT_APP_PASSWORD
│           ├── TEAMS_BOT_SECRET
│           ├── GITHUB_TOKEN
│           └── TEAMS_CHANNEL_ID
├── Bot Service: kevin-bot              # 免费 tier
│   └── Teams Channel 已启用
└── Key Vault: kv-kevin-bot             # 可选，第二版
```

**月成本**：约 $13-15

### 本地开发

```bash
uvicorn kevin.teams_bot.app:app --port 3978
ngrok http 3978
# Azure Bot Settings → Messaging Endpoint: https://xxxx.ngrok.io/api/messages
```

## Error Handling

| 场景 | 处理方式 |
|------|---------|
| GitHub Actions 触发失败 | Bot 回复错误 Card：「workflow 触发失败，请检查 repo 权限」 |
| Issue 不存在或无 kevin label | Bot 回复：「Issue #42 不存在或缺少 kevin label」 |
| Block 执行失败 | 状态 Card 更新为红色，显示失败 block + 错误摘要 |
| Bot → GitHub API 超时 | 重试 3 次，间隔 2s/4s/8s，仍失败则通知用户手动操作 |
| Teams Card 更新失败 | 降级为发新消息 |
| 审批者未绑定 GitHub | ephemeral 消息引导绑定 |
| notify endpoint 非法请求 | HMAC 验证失败 → 401 |
| App Service 宕机 | Kevin 不受影响（GitHub Actions 独立），恢复后补发通知 |

## Testing Strategy

| 层级 | 覆盖内容 | 工具 |
|------|---------|------|
| 单元测试 | 命令解析、Card 构建、User Mapping | pytest + pytest-asyncio |
| 集成测试 | Bot → GitHub API 交互 | pytest + httpx mock |
| Bot 模拟测试 | 完整消息收发流程 | Bot Framework Testing SDK |
| E2E 测试 | 本地 Bot + ngrok + 真实 Teams | 手动验证 checklist |

## Delivery Phases

### Phase 0: Azure 基础设施（前置，半天）
- Azure AD App Registration
- Bot Service 创建
- App Service 部署
- 本地 ngrok 调试环境跑通

### Phase 1: 状态通知（1-2 天）
- Bot 骨架 + `/api/notify` endpoint
- GitHub Actions 加 curl 推送
- 状态 Card 发送 + 更新
- **验收**：Kevin 跑一个 issue，Teams 频道实时看到状态变化

### Phase 2: HITL 审批（1-2 天）
- 审批 Card 模板
- Approval Handler + GitHub PR Review API
- User Mapping 配置
- **验收**：Teams 点 Approve → PR 自动合并

### Phase 3: 触发执行（1 天）
- Command Handler + 命令解析
- workflow_dispatch 触发
- 命令菜单注册
- **验收**：Teams 发 `@Kevin run repo#42` → GitHub Actions 开始执行

## Prerequisites

- [ ] 确认 Azure AD App Registration 权限（问 IT）
- [ ] 创建 GitHub Personal Access Token（scope: repo, workflow）
- [ ] 确定 Teams 频道（用于 Kevin 通知）
- [ ] 准备 Azure 订阅（App Service 部署）

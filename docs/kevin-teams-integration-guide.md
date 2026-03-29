# Kevin Teams Bot 集成指南

> 从零到通知推送的完整实操文档，基于 2026-03-27 实际验证。

---

## 目录

1. [架构总览](#1-架构总览)
2. [前置条件](#2-前置条件)
3. [Step 1: Azure AD App Registration](#3-step-1-azure-ad-app-registration)
4. [Step 2: 创建 Azure Bot Service](#4-step-2-创建-azure-bot-service)
5. [Step 3: 本地 Bot 开发](#5-step-3-本地-bot-开发)
6. [Step 4: ngrok 隧道 + Teams 连通](#6-step-4-ngrok-隧道--teams-连通)
7. [Step 5: 通知推送（Adaptive Card）](#7-step-5-通知推送adaptive-card)
8. [Step 6: 接入 Kevin GitHub Actions](#8-step-6-接入-kevin-github-actions)
9. [Step 7: 部署到 Azure App Service](#9-step-7-部署到-azure-app-service)
10. [故障排查](#10-故障排查)
11. [附录：关键概念解释](#11-附录关键概念解释)

---

## 1. 架构总览

### 系统拓扑

```
┌─────────────────────────────────────────────┐
│              Microsoft Teams                 │
│  用户发消息 / 收到 Adaptive Card 通知         │
└──────────┬────────────────▲─────────────────┘
           │                │
           ▼                │
┌──────────────────────────────────────────────┐
│         Azure Bot Service (Channel)           │
│  • 验证 JWT token                             │
│  • 路由消息到 Bot Endpoint                     │
│  • 免费 F0 tier（仅 Teams channel）            │
└──────────┬────────────────▲─────────────────┘
           │                │
     HTTPS POST        HTTPS POST
    /api/messages      (主动推送)
           │                │
           ▼                │
┌──────────────────────────────────────────────┐
│        Kevin Teams Bot (Python aiohttp)       │
│                                               │
│  POST /api/messages  ← Teams 消息入口          │
│  POST /api/notify    ← GitHub Actions 推状态   │
│  GET  /api/health    ← 健康检查                │
│                                               │
│  运行环境:                                     │
│    开发: 本地 + ngrok                          │
│    生产: Azure App Service                     │
└──────────┬───────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│           GitHub Actions (kevin.yaml)         │
│  Kevin 执行引擎 → curl /api/notify 推状态      │
└──────────────────────────────────────────────┘
```

### 核心设计原则

| 原则 | 说明 |
|------|------|
| **Bot 是旁路** | Bot 挂了不影响 Kevin 执行（GitHub Actions 独立运行） |
| **单 Card 更新** | 一个 Run 只发一张 Card，后续状态原地刷新，不刷屏 |
| **无状态优先** | Card Registry 丢失的最坏结果是发新 Card，而非系统崩溃 |
| **幂等通知** | 同一事件多次推送不产生重复消息 |

### 消息流详解

```
1. Teams 用户发消息
   → Azure Bot Service 验证 JWT
   → POST 到 Bot 的 /api/messages
   → Bot 处理并回复

2. GitHub Actions 推送通知
   → curl POST 到 Bot 的 /api/notify
   → Bot 用保存的 conversation reference 主动发/更新 Card
   → Teams 用户看到 Adaptive Card
```

---

## 2. 前置条件

### 必须有

| 条件 | 用途 | 如何获取 |
|------|------|---------|
| Microsoft 365 企业版账号 | 访问 Teams + Azure Portal | 公司 IT 分配 |
| Azure AD App Registration 权限 | 注册 Bot 应用 | 问 IT：「我需要在 Azure Portal 的 App Registrations 里注册一个 app」 |
| Azure 订阅 | 创建 Bot Service + App Service | 公司 Azure 订阅或免费试用 |
| Python 3.11+ | 运行 Bot | `python --version` |
| ngrok | 本地开发隧道 | `brew install ngrok` 或 https://ngrok.com |
| Node.js（可选） | 后续安装 Teams Toolkit | `node --version` |

### 关于权限的关键提示

**Azure AD App Registration 是唯一的硬性权限要求。** 如果你的企业限制了这个操作，整个方案都无法进行。在写任何代码之前，先确认这个权限。

沟通话术：
> "我需要在 Azure Portal 注册一个 Azure AD Application，用于开发一个内部 Teams Bot 来接收自动化系统的状态通知。Bot 只在我们的 Tenant 内使用（SingleTenant），不会暴露给外部用户。"

---

## 3. Step 1: Azure AD App Registration

### 3.1 创建 App Registration

1. 登录 [Azure Portal](https://portal.azure.com)
2. 搜索 **App registrations** → 点击 **New registration**
3. 填写：
   - **Name**: `ba-toolkit-bot`（或你喜欢的名字）
   - **Supported account types**: 选 **Accounts in this organizational directory only (Single tenant)**
   - **Redirect URI**: 留空
4. 点击 **Register**

### 3.2 记录关键信息

注册完成后，在 **Overview** 页面记录：

```
Application (client) ID:  ← 这是 MICROSOFT_APP_ID
Directory (tenant) ID:    ← 这是 MICROSOFT_APP_TENANT_ID
```

### 3.3 创建 Client Secret

1. 左侧菜单 → **Certificates & secrets**
2. **Client secrets** → **New client secret**
3. Description: `kevin-bot-secret`
4. Expires: 选 24 months
5. 点击 **Add**
6. **立即复制 Value**（离开页面后无法再看到）

```
Secret Value: ← 这是 MICROSOFT_APP_PASSWORD
```

⚠️ **Risk**: Client Secret 只显示一次。如果忘记复制，需要删除重新创建。

### 3.4 信息汇总

创建完成后你应该有三个值：

```env
MICROSOFT_APP_ID=<Application (client) ID>
MICROSOFT_APP_PASSWORD=<Client Secret Value>
MICROSOFT_APP_TENANT_ID=<Directory (tenant) ID>
```

---

## 4. Step 2: 创建 Azure Bot Service

### 4.1 创建 Bot

1. Azure Portal → 搜索 **Azure Bot** → **Create**
2. 填写：
   - **Bot handle**: `ba-toolkit-bot`
   - **Subscription**: 你的订阅
   - **Resource group**: 新建 `rg-bot-service` 或选已有的
   - **Pricing tier**: **F0 (Free)**（每月无限消息，仅限 Standard channels）
   - **Type of App**: **Single Tenant**
   - **Creation type**: **Use existing app registration**
   - **App ID**: 填 Step 1 的 `MICROSOFT_APP_ID`
   - **App tenant ID**: 填 Step 1 的 `MICROSOFT_APP_TENANT_ID`
3. 点击 **Review + create** → **Create**

### 4.2 启用 Teams Channel

1. 进入创建好的 Bot 资源
2. 左侧 **Channels** → 点击 **Microsoft Teams**
3. 勾选同意条款 → **Apply**
4. 状态变为 **Running** 即可

### 4.3 配置 Messaging Endpoint（暂时留空）

后面 ngrok 跑起来后再填。位置：**Configuration** → **Messaging endpoint**

---

## 5. Step 3: 本地 Bot 开发

### 5.1 项目结构

```
kevin/teams_bot/
├── app.py              # aiohttp 入口，注册路由
├── bot.py              # KevinBot 类，处理 Teams 消息
├── cards.py            # Adaptive Card JSON 构建器
├── config.py           # 环境变量配置
├── requirements.txt    # Python 依赖
└── .env                # 本地环境变量（不提交 git）
```

### 5.2 创建 .env

```env
MICROSOFT_APP_ID=<你的 App ID>
MICROSOFT_APP_PASSWORD=<你的 Client Secret>
MICROSOFT_APP_TENANT_ID=<你的 Tenant ID>
MICROSOFT_APP_TYPE=SingleTenant
PORT=3978
TEAMS_BOT_SECRET=
```

### 5.3 安装依赖

```bash
cd kevin/teams_bot
pip install -r requirements.txt
```

依赖清单：
```
botbuilder-core>=4.16.1           # Bot Framework SDK 核心
botbuilder-integration-aiohttp>=4.16.1  # aiohttp HTTP 适配器
aiohttp>=3.9.0                    # 异步 HTTP 服务器
python-dotenv>=1.0.0              # .env 文件加载
```

### 5.4 核心代码解析

#### config.py — 配置管理

```python
import os
from dotenv import load_dotenv

load_dotenv()

class BotConfig:
    PORT: int = int(os.getenv("PORT", "3978"))
    APP_ID: str = os.getenv("MICROSOFT_APP_ID", "")
    APP_PASSWORD: str = os.getenv("MICROSOFT_APP_PASSWORD", "")
    APP_TENANT_ID: str = os.getenv("MICROSOFT_APP_TENANT_ID", "")
    APP_TYPE: str = os.getenv("MICROSOFT_APP_TYPE", "SingleTenant")
    BOT_SECRET: str = os.getenv("TEAMS_BOT_SECRET", "")
```

所有敏感信息通过环境变量注入，不硬编码。

#### bot.py — Bot 核心逻辑

```python
class KevinBot(ActivityHandler):
    def __init__(self) -> None:
        super().__init__()
        # conversation_reference 持久化到文件，Bot 重启不丢失
        self.conversation_references: dict[str, dict] = self._load_references()

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        # 每次收到消息都保存 reference（用于后续主动推送）
        self._save_conversation_reference(turn_context)
        # ... 处理命令
```

**关键概念：Conversation Reference**

Bot 要主动给 Teams 发消息（而非回复），必须知道「往哪发」。这个信息叫 `conversation_reference`，包含：
- `conversation.id` — 对话/频道 ID
- `service_url` — Bot Framework 的回调 URL
- `channel_id` — 通道类型（msteams）
- `bot` — Bot 自己的信息

Bot 只有在收到用户消息时才能获得 reference。所以**第一次使用必须先在 Teams 里给 Bot 发一条消息**。

Reference 持久化到 `.conversation_references.json` 文件，Bot 重启后自动加载。

#### cards.py — Adaptive Card 构建

Adaptive Card 是 Teams 的富消息格式，类似于 Slack 的 Block Kit。本质是一个 JSON 结构。

```python
def build_run_status_card(payload: dict) -> dict:
    """根据 Kevin 运行状态构建 Adaptive Card JSON"""
    # Card 结构:
    # - 标题（带颜色：蓝=运行中，绿=成功，红=失败）
    # - FactSet（Issue、Repo、Blueprint、Run ID）
    # - Block 状态列表（✅/🔄/⏳/❌）
    # - 错误信息（如果有）
    # - 操作按钮（View Issue、View PR）
```

#### app.py — HTTP 入口

三个 endpoint：

| Endpoint | 方法 | 来源 | 用途 |
|----------|------|------|------|
| `/api/messages` | POST | Azure Bot Service | 接收 Teams 消息 |
| `/api/notify` | POST | GitHub Actions (curl) | 接收运行状态推送 |
| `/api/health` | GET | 任何人 | 健康检查 |

**`/api/notify` 的 Card 更新逻辑**：

```python
# 伪代码
if run_id in card_registry:
    # 已有 Card → 原地更新（不发新消息）
    update_activity(existing_activity_id, new_card)
else:
    # 新 Run → 发送新 Card，记录 activity_id
    response = send_activity(new_card)
    card_registry[run_id] = response.activity_id
```

这就是为什么同一个 Run 的多次通知只产生一张 Card 且原地更新。

### 5.5 启动验证

```bash
python app.py
# Kevin Teams Bot starting on port 3978...

# 另一个终端验证
curl http://localhost:3978/api/health
# {"status": "ok", "bot": "kevin-teams-bot", "conversations": 0}
```

---

## 6. Step 4: ngrok 隧道 + Teams 连通

### 6.1 为什么需要 ngrok

Teams 消息 → Azure Bot Service → **你的 Bot Endpoint**

Azure Bot Service 需要通过公网 HTTPS 访问你的 Bot。本地开发时用 ngrok 把 localhost 暴露到公网。

```
Teams → Azure Bot Service → ngrok 公网 URL → localhost:3978
```

### 6.2 启动 ngrok

```bash
ngrok http 3978
```

输出类似：
```
Forwarding  https://xxxx.ngrok-free.dev -> http://localhost:3978
```

记下 `https://xxxx.ngrok-free.dev` 这个 URL。

### 6.3 配置 Messaging Endpoint

1. Azure Portal → Bot Service → **Configuration**
2. **Messaging endpoint** 填: `https://xxxx.ngrok-free.dev/api/messages`
3. **保存**

### 6.4 在 Teams 里测试

方法一：Azure Portal → Bot Service → **Channels** → Microsoft Teams → **Open in Teams**

方法二：Teams 里搜索 Bot 名称（如 `BA Toolkit Bot`）直接对话

发送 `ping`，如果回复 `pong 🏓`，链路通了。

### 6.5 ngrok 的限制

| 问题 | 影响 | 解决方案 |
|------|------|---------|
| 免费版 URL 每次重启会变 | 需要重新改 Azure 配置 | 付费固定域名（$8/月）或部署到 Azure |
| 免费版有访问警告页 | 浏览器访问会弹拦截页 | 对 Bot API 调用无影响 |
| 关终端隧道就断 | Bot 收不到 Teams 消息 | 保持 ngrok 运行，或用 `tmux`/`screen` |

---

## 7. Step 5: 通知推送（Adaptive Card）

### 7.1 前置条件

Bot 至少收到过一条 Teams 消息（以获取 conversation reference）。

验证：
```bash
curl http://localhost:3978/api/health
# conversations 应该 >= 1
```

### 7.2 发送通知

```bash
curl -X POST http://localhost:3978/api/notify \
  -H "Content-Type: application/json" \
  -d '{
    "event": "run_started",
    "run_id": "20260327-001",
    "issue_number": 42,
    "issue_title": "Add rate limiting",
    "repo": "anlaganlag/myrepo",
    "blueprint_id": "bp_coding_task.1.0.0",
    "status": "running",
    "blocks": [
      {"block_id": "B1", "name": "Analyze", "status": "running"},
      {"block_id": "B2", "name": "Implement", "status": "pending"},
      {"block_id": "B3", "name": "Create PR", "status": "pending"}
    ]
  }'
```

Teams 中会收到一张 Adaptive Card：

```
┌────────────────────────────────┐
│ 🔄 Kevin Running               │
│                                │
│ Issue     #42 Add rate limiting│
│ Repo      anlaganlag/myrepo    │
│ Blueprint bp_coding_task.1.0.0 │
│ Run       20260327-001         │
│                                │
│ Blocks                         │
│ 🔄 B1: Analyze                 │
│ ⏳ B2: Implement               │
│ ⏳ B3: Create PR               │
│                                │
│ [View Issue]                   │
└────────────────────────────────┘
```

### 7.3 更新通知（原地更新）

用**相同的 `run_id`** 再发一次，Card 会原地更新而非发新消息：

```bash
curl -X POST http://localhost:3978/api/notify \
  -H "Content-Type: application/json" \
  -d '{
    "event": "run_completed",
    "run_id": "20260327-001",
    "status": "completed",
    "issue_number": 42,
    "issue_title": "Add rate limiting",
    "repo": "anlaganlag/myrepo",
    "blueprint_id": "bp_coding_task.1.0.0",
    "blocks": [
      {"block_id": "B1", "name": "Analyze", "status": "passed"},
      {"block_id": "B2", "name": "Implement", "status": "passed"},
      {"block_id": "B3", "name": "Create PR", "status": "passed"}
    ],
    "pr_number": 58
  }'
```

原来的 Card 变成：

```
┌────────────────────────────────┐
│ ✅ Kevin Completed              │
│ ...                            │
│ ✅ B1: Analyze                  │
│ ✅ B2: Implement                │
│ ✅ B3: Create PR                │
│                                │
│ [View Issue] [View PR]         │
└────────────────────────────────┘
```

### 7.4 /api/notify Payload 规范

```jsonc
{
  // 必填
  "event": "run_started | block_update | run_completed | run_failed",
  "run_id": "string — 唯一标识，用于 Card 更新匹配",
  "status": "running | completed | failed",
  "blocks": [
    {
      "block_id": "B1",
      "name": "Block 名称",
      "status": "pending | running | passed | failed"
    }
  ],

  // 可选（推荐填写）
  "issue_number": 42,
  "issue_title": "Issue 标题",
  "repo": "owner/repo",
  "blueprint_id": "bp_coding_task.1.0.0",

  // 可选
  "error": "错误信息（失败时显示）",
  "pr_number": 58  // 完成时显示 View PR 按钮
}
```

### 7.5 认证

`/api/notify` 支持 HMAC 签名认证（可选）：

1. 设置 `TEAMS_BOT_SECRET` 环境变量
2. 请求时携带 `X-Bot-Signature` header:

```bash
SECRET="your-shared-secret"
BODY='{"event":"run_started",...}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

curl -X POST http://localhost:3978/api/notify \
  -H "Content-Type: application/json" \
  -H "X-Bot-Signature: $SIGNATURE" \
  -d "$BODY"
```

未配置 `TEAMS_BOT_SECRET` 时跳过验证（开发环境）。

---

## 8. Step 6: 接入 Kevin GitHub Actions

### 8.1 添加 GitHub Secrets

在 Kevin 的 GitHub 仓库：**Settings → Secrets → Actions** 添加：

| Secret 名称 | 值 |
|-------------|---|
| `TEAMS_BOT_URL` | Bot 的公网 URL（ngrok 或 Azure App Service） |
| `TEAMS_BOT_SECRET` | 与 Bot `.env` 中 `TEAMS_BOT_SECRET` 一致（可选） |

### 8.2 修改 kevin.yaml

在 `.github/workflows/kevin.yaml` 中添加通知步骤：

```yaml
env:
  TEAMS_BOT_URL: ${{ secrets.TEAMS_BOT_URL }}
  TEAMS_BOT_SECRET: ${{ secrets.TEAMS_BOT_SECRET }}

jobs:
  kevin-run:
    steps:
      # ... 已有的 setup 步骤 ...

      - name: Notify Teams — Run Started
        if: env.TEAMS_BOT_URL != ''
        run: |
          curl -sf -X POST "$TEAMS_BOT_URL/api/notify" \
            -H "Content-Type: application/json" \
            -d '{
              "event": "run_started",
              "run_id": "${{ github.run_id }}",
              "issue_number": ${{ github.event.inputs.issue_number }},
              "repo": "${{ github.event.inputs.repo }}",
              "status": "running",
              "blocks": []
            }' || echo "Teams notify failed (non-fatal)"

      - name: Run Kevin
        run: python -m kevin run --issue ${{ github.event.inputs.issue_number }} ...

      - name: Notify Teams — Run Completed
        if: always() && env.TEAMS_BOT_URL != ''
        run: |
          STATUS="${{ job.status == 'success' && 'completed' || 'failed' }}"
          curl -sf -X POST "$TEAMS_BOT_URL/api/notify" \
            -H "Content-Type: application/json" \
            -d "{
              \"event\": \"run_${STATUS}\",
              \"run_id\": \"${{ github.run_id }}\",
              \"issue_number\": ${{ github.event.inputs.issue_number }},
              \"repo\": \"${{ github.event.inputs.repo }}\",
              \"status\": \"${STATUS}\",
              \"blocks\": []
            }" || echo "Teams notify failed (non-fatal)"
```

### 8.3 更细粒度：Block 级通知

改造 `kevin/agent_runner.py`，在每个 block 执行前后调用 notify：

```python
import json
import os
import urllib.request

TEAMS_BOT_URL = os.getenv("TEAMS_BOT_URL", "")

def notify_teams(payload: dict) -> None:
    """向 Teams Bot 推送状态（非阻塞，失败不影响 Kevin 执行）"""
    if not TEAMS_BOT_URL:
        return
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{TEAMS_BOT_URL}/api/notify",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[WARN] Teams notify failed: {e}")
```

在 block 执行循环中调用：

```python
for block in blocks:
    notify_teams({
        "event": "block_update",
        "run_id": run_state.run_id,
        "status": "running",
        "blocks": serialize_blocks(run_state),
        ...
    })

    result = execute_block(block)

    notify_teams({
        "event": "block_update",
        "run_id": run_state.run_id,
        "status": "running" if remaining else "completed",
        "blocks": serialize_blocks(run_state),
        ...
    })
```

---

## 9. Step 7: 部署到 Azure App Service

### 9.1 为什么要部署

| 本地 + ngrok | Azure App Service |
|-------------|-------------------|
| URL 每次重启会变 | 固定 URL |
| 关终端就断 | 7×24 运行 |
| 适合开发调试 | 适合生产使用 |
| 免费 | ~$13/月（B1 tier） |

### 9.2 准备 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3978
CMD ["python", "app.py"]
```

### 9.3 Azure CLI 部署

```bash
# 登录
az login

# 创建 App Service Plan
az appservice plan create \
  --name asp-kevin-bot \
  --resource-group rg-bot-service \
  --sku B1 \
  --is-linux

# 创建 Web App
az webapp create \
  --name kevin-teams-bot \
  --resource-group rg-bot-service \
  --plan asp-kevin-bot \
  --runtime "PYTHON:3.11"

# 配置环境变量
az webapp config appsettings set \
  --name kevin-teams-bot \
  --resource-group rg-bot-service \
  --settings \
    MICROSOFT_APP_ID="<your-app-id>" \
    MICROSOFT_APP_PASSWORD="<your-secret>" \
    MICROSOFT_APP_TENANT_ID="<your-tenant-id>" \
    MICROSOFT_APP_TYPE="SingleTenant" \
    TEAMS_BOT_SECRET="<your-bot-secret>" \
    PORT="3978"

# 启用 Always On（防止冷启动）
az webapp config set \
  --name kevin-teams-bot \
  --resource-group rg-bot-service \
  --always-on true

# 部署代码
az webapp up \
  --name kevin-teams-bot \
  --resource-group rg-bot-service
```

### 9.4 更新 Bot Messaging Endpoint

Azure Portal → Bot Service → Configuration：

```
Messaging endpoint: https://kevin-teams-bot.azurewebsites.net/api/messages
```

### 9.5 更新 GitHub Secret

```
TEAMS_BOT_URL = https://kevin-teams-bot.azurewebsites.net
```

---

## 10. 故障排查

### 10.1 Teams 发消息，Bot 无响应

```
检查顺序:
1. Bot 进程在跑吗？         → curl http://localhost:3978/api/health
2. ngrok 在跑吗？           → curl https://xxxx.ngrok-free.dev/api/health
3. Messaging endpoint 对吗？ → Azure Portal → Bot → Configuration
4. App ID / Password 对吗？  → .env 文件 vs Azure Portal
5. Tenant ID 对吗？          → SingleTenant 必须匹配
```

### 10.2 /api/notify 返回 400: "No conversation references"

Bot 还没收到过任何 Teams 消息，不知道往哪发。

**解决**：在 Teams 里给 Bot 发一条消息（任何内容都行）。

### 10.3 Card 发了新消息而非更新

可能原因：
- Bot 重启导致 `card_registry`（内存中）丢失了 `activity_id`
- `run_id` 不一致

当前 `card_registry` 仅在内存中，Bot 重启后丢失。这是已知限制，后续可持久化到文件或 Redis。

### 10.4 ngrok ERR_NGROK_3200: endpoint offline

ngrok 进程挂了或网络断了。重启 ngrok：

```bash
ngrok http 3978
```

如果 URL 变了，需要更新 Azure Bot 的 Messaging endpoint。

### 10.5 Bot Framework 认证错误

```
[ERROR] BotFrameworkAdapter: ... 401 Unauthorized
```

常见原因：
- `MICROSOFT_APP_PASSWORD` 过期（Client Secret 有有效期）
- `MICROSOFT_APP_TENANT_ID` 错误（SingleTenant 必须匹配）
- App Registration 被删除

### 10.6 调试技巧

```bash
# 查看 Bot 进程日志（后台运行时）
tail -f /path/to/bot.log

# 查看 ngrok 请求日志（浏览器打开）
http://localhost:4040

# 手动测试 notify
curl -v -X POST http://localhost:3978/api/notify \
  -H "Content-Type: application/json" \
  -d '{"event":"test","run_id":"test-001","status":"running","blocks":[]}'
```

ngrok 的本地 Web UI（http://localhost:4040）非常有用，可以看到每个请求的完整 header、body 和响应。

---

## 11. 附录：关键概念解释

### Azure AD App Registration

Azure AD（现称 Microsoft Entra ID）的应用注册，类似于 OAuth 中的 Client 注册。你的 Bot 需要一个身份（App ID + Secret）来和 Azure Bot Service 通信。

### Azure Bot Service

微软的 Bot 托管和路由服务。它的作用是：
1. 接收来自各 Channel（Teams、Slack、Web Chat 等）的消息
2. 验证消息的合法性（JWT token）
3. 把消息转发到你的 Bot Endpoint
4. 帮你的 Bot 把回复发回 Channel

你不需要在 Bot Service 上跑代码。它只是一个消息路由器。

### Bot Framework SDK

微软的 Bot 开发 SDK，Python 版本是 `botbuilder-core`。它帮你：
- 解析 Bot Service 转发的消息
- 验证 JWT token
- 序列化/反序列化 Activity 对象
- 主动向 conversation 发消息（`continue_conversation`）

### Conversation Reference

Bot 主动推送消息所需的"地址"。包含 conversation ID、service URL、channel ID 等。只有在 Bot 收到用户消息时才能获取。

### Adaptive Card

Teams 的富消息格式，用 JSON 描述卡片结构。支持：
- 文本、图片、表格
- 按钮（打开链接、提交表单、展开更多内容）
- 样式（颜色、粗体、大小）

设计工具：https://adaptivecards.io/designer/

### Activity

Bot Framework 中的消息抽象。每条消息（文本、Card、事件）都是一个 Activity 对象，包含类型、内容、发送者、接收者等信息。

`activity.id`（也叫 `activity_id`）是消息的唯一标识，用于后续更新这条消息。

### SingleTenant vs MultiTenant

- **SingleTenant**: Bot 只在你的组织内使用。认证时会校验 Tenant ID。
- **MultiTenant**: Bot 可以被任何组织安装使用。

企业内部 Bot 选 SingleTenant。

---

## 当前状态与后续规划

### 已完成（2026-03-27 验证通过）

- [x] Azure AD App Registration
- [x] Azure Bot Service (F0)
- [x] 本地 Bot + ngrok 链路
- [x] Teams 双向通信（ping/pong）
- [x] Adaptive Card 通知推送
- [x] Card 原地更新（单 Run 单 Card）

### 后续规划

| Phase | 内容 | 状态 |
|-------|------|------|
| 接入真实 Kevin | 改 kevin.yaml + agent_runner.py 加 curl 通知 | 待做 |
| 部署 Azure App Service | 替代 ngrok，7×24 稳定运行 | 待做 |
| Phase 3: 触发执行 | @Kevin run repo#42 触发 GitHub Actions | 待做 |
| Phase 2: HITL 审批 | Adaptive Card 内联审批 PR | 待做 |

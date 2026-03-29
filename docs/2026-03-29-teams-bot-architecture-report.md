# Kevin Teams Bot 架构决策报告：单 Bot vs 多 Bot & 权限控制

> Date: 2026-03-29
> Status: 决策分析
> Scope: Bot 部署模型选择 + 权限隔离方案设计

---

## 背景

Kevin Teams Bot 当前架构：
- **单 Bot 实例**（ba-toolkit-bot, Azure Bot Service F0 免费）
- **广播模式** — `handle_notify` 向所有已知 conversation 推送通知
- **无权限控制** — Adaptive Card 上的 Approve/Reject 按钮任何人可点击
- **无身份映射** — Teams 用户与 GitHub 用户之间没有绑定关系
- **Action.Submit 未实现** — `bot.py` 只处理文本命令，Card 按钮回调无处理逻辑

随着团队规模扩大和多 repo 接入，需要回答两个核心问题。

---

## 核心议题一：单 Bot vs 多 Bot

### 方案 A：每用户/每团队一个独立 Bot

```
Azure AD App Registration × N
Azure Bot Service × N
App Service / Container × N
Teams App 安装 × N

用户A ←→ Bot-A (App ID: aaa) ←→ repo-a
用户B ←→ Bot-B (App ID: bbb) ←→ repo-b
用户C ←→ Bot-C (App ID: ccc) ←→ repo-c
```

#### 优势

| 项目 | 说明 |
|------|------|
| 天然隔离 | 不同 Bot 之间零共享状态，无泄露风险 |
| 独立生命周期 | 可以独立升级、重启、回滚 |
| 简单心智模型 | 每个 Bot 只关心自己的 repo 和 conversation |

#### 劣势

| 项目 | 影响 |
|------|------|
| Azure AD 注册 × N | 每个 Bot 需要独立的 App Registration（App ID + Secret），需 Azure AD Admin 权限 |
| 部署复杂度 × N | N 个 Container / App Service 实例，N 套 CI/CD pipeline |
| 月成本 × N | Bot Service 免费，但每个后端需要 ≥ B1 ($13/mo) 或 Container App 计算资源 |
| Teams Admin 审批 × N | 每个 Bot 都需要 Teams Admin 安装到组织，每次都走审批流程 |
| Secret 管理 × N | N 套 App ID/Password/Tenant，N 套 TEAMS_BOT_URL 配置到各 repo |
| 用户体验碎片化 | 用户需要记住 @Kevin-A 管 repo-a、@Kevin-B 管 repo-b |
| 跨 repo 操作困难 | 用户如果同时维护多个 repo，需要切换不同 Bot 对话 |

#### 成本估算

| 规模 | Bot Service | 后端计算 | Secret 管理 | 月总成本 |
|------|------------|---------|------------|---------|
| 1 Bot | $0 | $0（复用 ba-toolkit） | 1 套 | $0 |
| 5 Bot | $0 | $65（5 × $13 B1） | 5 套 | ~$65 |
| 20 Bot | $0 | $260 或共享集群 | 20 套 | ~$100-260 |

### 方案 B：单 Bot + 逻辑隔离（推荐）

```
Azure AD App Registration × 1
Azure Bot Service × 1
App Service / Container × 1
Teams App 安装 × 1

                    ┌─────────────────────────────────────┐
                    │          Kevin Bot (单实例)           │
                    │                                      │
用户A ──── Channel-A ──→ 路由层 ──→ repo-a 通知           │
用户B ──── Channel-B ──→ 路由层 ──→ repo-b 通知           │
用户C ──── Channel-A ──→ 路由层 ──→ repo-a 通知 (共享)    │
                    │                                      │
                    │  权限层：谁能看什么 + 谁能做什么       │
                    └─────────────────────────────────────┘
```

#### 优势

| 项目 | 说明 |
|------|------|
| 零额外基础设施 | 一个 Bot Service + 一个后端实例，复用现有 ba-toolkit |
| 统一体验 | 用户只和一个 @Kevin 交互，Bot 内部按上下文路由 |
| 集中管理 | 一套 Secret、一套 CI/CD、一个监控 dashboard |
| 跨 repo 操作 | `run org/repo-a#42` 和 `run org/repo-b#7` 在同一对话中完成 |
| 增量复杂度 | 权限逻辑在代码层实现，可按需逐步增加 |

#### 劣势

| 项目 | 影响 |
|------|------|
| 单点故障 | Bot 挂了影响所有用户（但 Kevin 核心通过 GitHub Actions 不受影响） |
| 需要自建权限逻辑 | 通知路由、操作授权需要编码实现 |
| 共享状态 | `conversation_references` 和 `card_registry` 需要区分上下文 |

### 决策矩阵

| 维度 | 多 Bot (A) | 单 Bot + 逻辑隔离 (B) | 权重 |
|------|-----------|---------------------|------|
| 部署运维成本 | ❌ 线性增长 | ✅ 恒定 | 高 |
| 安全隔离强度 | ✅ 进程级 | ⚠️ 代码级 | 中 |
| 用户体验 | ❌ 碎片化 | ✅ 统一 | 高 |
| 跨 repo 操作 | ❌ 不支持 | ✅ 原生支持 | 高 |
| 扩展成本 | ❌ $13/bot | ✅ 固定 | 中 |
| 实现难度 | ✅ 简单复制 | ⚠️ 需要设计权限 | 中 |
| Teams Admin 审批 | ❌ × N 次 | ✅ × 1 次 | 中 |

### 结论

**推荐方案 B：单 Bot + 逻辑隔离**。

理由：
1. Kevin Bot 是**旁路系统**，不在关键路径上，进程级隔离的收益有限
2. 多 Bot 的运维成本和用户体验碎片化是硬伤
3. 权限控制完全可以在代码层实现，且可以利用 Teams 原生能力
4. 当前只有 1 个 Bot Service + 0 成本，没有理由增加复杂度

**例外场景**：如果面向**外部客户**（不同组织/租户）部署独立 Kevin 实例，则需要多 Bot（Multi-Tenant Bot 或 Per-Tenant Bot）。但当前是**内部团队使用**，单 Bot 足够。

---

## 核心议题二：权限控制与管理

### 当前问题

```
问题 1: 广播通知
  handle_notify → 遍历所有 conversation_references → 全部推送
  → 所有人看到所有 repo 的通知，包括无关的

问题 2: 无操作授权
  Adaptive Card [Approve] [Reject] [Retry] → 任何人可点击
  bot.py on_message_activity 未处理 activity.value (Card 回调)
  → 无关人员可以审批/拒绝 PR

问题 3: 无身份映射
  Teams User (AAD Object ID) ←→ GitHub User (username) 无绑定
  → 即使校验权限，也不知道对应的 GitHub 身份
```

### 权限模型设计

#### 三层权限架构

```
┌─────────────────────────────────────────────────────────┐
│  Layer 3: 操作授权 (Action Authorization)                │
│  "这个人能对这个 PR 做什么？"                              │
│  → Action.Submit 回调时校验                               │
├─────────────────────────────────────────────────────────┤
│  Layer 2: 通知路由 (Notification Routing)                 │
│  "这条通知应该发给谁？"                                    │
│  → handle_notify 时按订阅关系过滤                          │
├─────────────────────────────────────────────────────────┤
│  Layer 1: 身份映射 (Identity Binding)                     │
│  "这个 Teams 用户是哪个 GitHub 用户？"                     │
│  → 一次性绑定，后续自动识别                                │
└─────────────────────────────────────────────────────────┘
```

#### Layer 1: 身份映射

**问题**：Teams 使用 Azure AD 身份（`aad_object_id`），Kevin/GitHub 使用 GitHub username。需要建立双向映射。

**方案对比**：

| 方案 | 实现 | 优点 | 缺点 |
|------|------|------|------|
| A. 静态 YAML 配置 | `user_mapping.yaml` 手工维护 | 最简单，无外部依赖 | 新成员需手动添加 |
| B. Bot 命令绑定 | `link @github-user` 一次性绑定 | 自助服务，无需管理员 | 需要信任用户输入 |
| C. OAuth 绑定 | GitHub OAuth 流程验证 | 最安全，身份不可伪造 | 实现复杂，需要 OAuth App |
| D. Azure AD + GitHub EMU | 企业级 SSO 统一身份 | 零配置 | 需要 GitHub Enterprise |

**推荐**：**B（Bot 命令绑定）为主 + A（YAML）为底**

```python
# 用户在 Teams 中：
link anlaganlag          # 绑定 GitHub 用户名
whoami                   # 查看当前绑定

# 数据结构
user_mapping = {
    "aad-object-id-xxx": {
        "github_user": "anlaganlag",
        "display_name": "Randy",
        "bound_at": "2026-03-29T10:00:00Z",
        "bound_by": "self"        # self | admin
    }
}
```

**安全考虑**：
- `link` 命令不需要 OAuth 验证，因为这是**内部团队使用**
- 如果需要更高安全级别，可以要求管理员确认绑定（`admin-link @teams-user @github-user`）
- 绑定关系持久化到 JSON 文件（与 conversation_references 同级）

#### Layer 2: 通知路由

**核心思路**：利用 **Teams Channel 作为天然的隔离边界**，而不是在代码里自建 ACL。

**方案 1: Channel → Repo 映射（推荐）**

```
Team: Kevin Notifications
├── #repo-a-notifications     → 只推 org/repo-a 的通知
├── #repo-b-notifications     → 只推 org/repo-b 的通知
├── #security-alerts          → 只推带 security label 的通知
├── #all-notifications        → 全量通知（管理员用）
└── #private-review (Private) → 敏感 repo 的审批通知
```

**实现方式**：

```python
# 扩展 conversation_references 结构
{
    "conv_repo_a": {
        "conversation": {"id": "19:xxx@thread.tacv2"},
        "service_url": "...",
        "channel_id": "msteams",
        "bot": {...},
        "routing": {
            "repos": ["org/repo-a"],          # 订阅的 repo
            "labels": [],                      # 可选：按 label 过滤
            "events": ["all"]                  # 可选：只要某些事件
        }
    }
}

# handle_notify 中
async def handle_notify(req: Request) -> Response:
    ...
    payload_repo = payload.get("repo", "")

    for conv_id, ref_dict in bot.conversation_references.items():
        routing = ref_dict.get("routing", {})
        allowed_repos = routing.get("repos", [])

        # 空列表 = 接收所有（向后兼容）
        if allowed_repos and payload_repo not in allowed_repos:
            continue

        # 推送通知...
```

**订阅管理命令**：

```
subscribe org/repo-a              → 当前 channel 订阅 repo-a 的通知
unsubscribe org/repo-a            → 取消订阅
subscriptions                     → 查看当前 channel 的订阅列表
```

**方案 2: 1:1 对话 + 按 assignee 推送**

```python
# 当 issue assignee = "anlaganlag"
# 找到 aad_object_id 映射到 "anlaganlag" 的用户
# 直接 proactive message 到该用户的 1:1 conversation
```

适合：**个人通知**（你负责的 issue 状态变更只通知你）

**推荐组合**：Channel 级路由（团队可见性）+ 1:1 个人通知（可选增强）

#### Layer 3: 操作授权

**当前缺失**：`bot.py` 的 `on_message_activity` 不处理 `activity.value`（Card 按钮回调）。

**需要实现的授权矩阵**：

| 操作 | 权限要求 | 校验方式 |
|------|---------|---------|
| Approve PR | GitHub repo write 权限 | GitHub API 或本地映射 |
| Reject PR | GitHub repo write 权限 | GitHub API 或本地映射 |
| Retry Run | GitHub Actions trigger 权限 | GitHub API 或本地映射 |
| View (OpenUrl) | 无需校验 | Teams 按钮直接跳转 |

**授权方案对比**：

| 方案 | 安全级别 | 延迟 | 实现难度 |
|------|---------|------|---------|
| A. Teams 角色映射 | 中 | 低 | 低 |
| B. 本地权限表 | 中 | 低 | 中 |
| C. GitHub API 实时校验 | 高 | 高（~200ms） | 中 |
| D. A + C 组合 | 高 | 中 | 中 |

**推荐方案 D: Teams 角色快速拒绝 + GitHub API 精确校验**

```python
# bot.py — 新增 Action.Submit 处理
async def on_message_activity(self, turn_context: TurnContext) -> None:
    value = turn_context.activity.value
    if value and isinstance(value, dict):
        action = value.get("action")
        if action in ("approve", "reject", "reject_confirm", "retry"):
            await self._handle_card_action(turn_context, value)
            return

    # 原有文本命令处理...

async def _handle_card_action(self, turn_context: TurnContext, data: dict) -> None:
    actor = turn_context.activity.from_property
    action = data["action"]
    repo = data["repo"]

    # Step 1: Teams 角色快速拒绝（Guest 不可操作）
    try:
        member = await TeamsInfo.get_member(turn_context, actor.id)
        # Guest 用户直接拒绝
        if getattr(member, 'user_role', '') == 'guest':
            await turn_context.send_activity("⛔ Guest 用户无权执行此操作。")
            return
    except Exception:
        pass  # 无法获取角色信息时不阻塞

    # Step 2: 身份映射
    github_user = self.user_mapping.get(actor.aad_object_id)
    if not github_user:
        await turn_context.send_activity(
            "⚠️ 未绑定 GitHub 账号。请发送 `link <github-username>` 绑定。"
        )
        return

    # Step 3: GitHub API 校验（approve/reject 需要 write 权限）
    if action in ("approve", "reject", "reject_confirm"):
        permission = await github_client.get_user_permission(repo, github_user)
        if permission not in ("admin", "write", "maintain"):
            await turn_context.send_activity(
                f"⛔ GitHub 用户 `{github_user}` 对 `{repo}` 无写入权限。"
            )
            return

    # Step 4: 执行操作
    if action == "approve":
        await self._approve_pr(turn_context, data, github_user)
    elif action == "reject":
        await self._show_reject_form(turn_context, data)
    elif action == "reject_confirm":
        await self._reject_pr(turn_context, data, github_user)
    elif action == "retry":
        await self._retry_run(turn_context, data, github_user)
```

**GitHub API 权限校验实现**：

```python
# github_client.py — 新增方法
async def get_user_permission(self, repo: str, username: str) -> str:
    """GET /repos/{owner}/{repo}/collaborators/{username}/permission
    Returns: "admin" | "maintain" | "write" | "triage" | "read" | "none"
    """
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/collaborators/{username}/permission",
         "--jq", ".permission"],
        capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else "none"
```

### 完整权限流程图

```
用户点击 Adaptive Card [Approve] 按钮
          │
          ▼
┌─────────────────────────────────┐
│ Bot: on_message_activity        │
│ 检测 activity.value 存在        │
│ → 这是 Card 按钮回调            │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│ Step 1: Teams 角色检查           │
│ TeamsInfo.get_member()          │
│ Guest? → ⛔ 拒绝                │
└──────────┬──────────────────────┘
           │ Owner/Member
           ▼
┌─────────────────────────────────┐
│ Step 2: 身份映射                 │
│ aad_object_id → github_user     │
│ 未绑定? → ⚠️ 提示 link 命令     │
└──────────┬──────────────────────┘
           │ 已绑定
           ▼
┌─────────────────────────────────┐
│ Step 3: GitHub 权限校验          │
│ GET /repos/{r}/collaborators/   │
│     {user}/permission           │
│ < write? → ⛔ 拒绝              │
└──────────┬──────────────────────┘
           │ write/admin
           ▼
┌─────────────────────────────────┐
│ Step 4: 执行操作                 │
│ approve → GitHub PR Review API  │
│ reject  → 弹出原因表单           │
│ retry   → workflow_dispatch     │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│ Step 5: 更新 Card 为终态         │
│ "✅ Approved by @randy"         │
│ 移除 Submit 按钮，防止重复操作    │
└─────────────────────────────────┘
```

### 实施路线图

```
Phase 1 (Day 1): 基础框架                    ← 最小可用
├── bot.py 增加 activity.value 处理
├── 静态 user_mapping.yaml（手工配置 2-3 人）
├── Action.Submit → GitHub API 执行 approve/reject
└── 终态 Card 替换（防重复点击）

Phase 2 (Day 2): 通知路由
├── conversation_references 增加 routing 字段
├── handle_notify 按 repo 过滤推送
├── subscribe/unsubscribe 命令
└── Channel 级订阅管理

Phase 3 (Day 3): 自助身份绑定
├── link / unlink / whoami 命令
├── user_mapping 持久化到 JSON
├── 绑定提示（未绑定用户点按钮时引导）
└── admin-link 管理员代绑

Phase 4 (Future): 增强
├── GitHub API 实时权限校验
├── 1:1 个人通知（按 assignee）
├── 审计日志（谁在什么时候 approve/reject 了什么）
├── OAuth 绑定流程（高安全场景）
└── Azure AD Group → GitHub Team 自动同步
```

### 数据模型总结

```python
# === 身份映射 (user_mapping.json) ===
{
    "<aad_object_id>": {
        "github_user": "anlaganlag",
        "display_name": "Randy",
        "roles": ["admin"],           # admin | reviewer | observer
        "bound_at": "2026-03-29T10:00:00Z"
    }
}

# === 通知订阅 (conversation_references.json) ===
{
    "<conversation_id>": {
        "conversation": {"id": "..."},
        "service_url": "...",
        "channel_id": "msteams",
        "bot": {"id": "...", "name": "Kevin"},
        "routing": {
            "repos": ["org/repo-a", "org/repo-b"],
            "labels": ["security"],       # 可选过滤
            "events": ["run_completed", "run_failed"]  # 可选过滤
        }
    }
}

# === Card 注册表 (card_registry — 内存 + 持久化) ===
{
    "<run_id>": {
        "conversation_id": "...",
        "activity_id": "...",
        "created_at": "..."
    }
}

# === 审计日志 (audit_log.jsonl — 可选) ===
{"ts": "...", "actor_aad": "...", "actor_github": "randy", "action": "approve", "repo": "org/repo-a", "pr": 42}
```

---

## 总结

| 议题 | 决策 | 理由 |
|------|------|------|
| 单 Bot vs 多 Bot | **单 Bot + 逻辑隔离** | 运维成本、用户体验、扩展性全面优于多 Bot |
| 通知隔离 | **Teams Channel 路由** | 利用 Teams 原生 Channel 权限，零额外基础设施 |
| 操作授权 | **Teams 角色 + GitHub API** | 快速拒绝 Guest + 精确校验 GitHub 写权限 |
| 身份映射 | **Bot 命令自助绑定** | 低摩擦上手，admin 可代绑作为兜底 |
| 实施优先级 | **Phase 1 先做 Action.Submit** | 这是当前最大功能缺口，HITL 审批依赖它 |

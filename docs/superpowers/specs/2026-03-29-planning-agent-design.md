# Planning Agent as Edge Function — Design Spec

> **Date**: 2026-03-29
> **Status**: Draft
> **Scope**: Planning Agent 通过 callback 链编排多步 Executor 调用

---

## 1. 目标

一个 Supabase Edge Function，接收高层需求，拆解为多步 blueprint 调用，通过 callback 链逐步驱动 Executor 完成全部任务。

## 2. 核心约束

| 约束 | 值 | 影响 |
|------|---|------|
| Edge Function 执行时限 | ~150s | 不能同步等 Executor（3-5min） |
| Executor 已有 callback 机制 | POST /callback | 可复用为链式触发 |

**解法**：事件驱动 callback 链。Planning Agent 每次被唤醒只推进一步，状态靠 DB 持久化。

## 3. 架构

```
用户
 │  POST /plan
 │  {instruction: "给 my-app 加登录功能", context: {repo: "owner/app"}}
 ▼
┌────────────────────────────┐
│  /plan (Edge Function)     │
│  ① 校验 API Key            │
│  ② Claude API 拆解需求      │
│     → N 个 steps           │
│  ③ 写 plans 表             │
│  ④ POST /execute (step 0)  │
│     callback_url = /plan/advance
│  ⑤ 返回 {plan_id, steps}  │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  Executor (GitHub Actions) │
│  执行 step 0 blueprint     │
│  完成 →                     │
└────────────┬───────────────┘
             │ POST /plan/advance
             ▼
┌────────────────────────────┐
│  /plan/advance             │
│  ① HMAC 校验               │
│  ② 更新 step 0 = completed │
│  ③ 有下一步？               │
│     → POST /execute step 1 │
│  ④ 全部完成？               │
│     → plan = completed      │
└────────────┬───────────────┘
             │
             ▼  (重复直到所有 step 完成)
┌────────────────────────────┐
│  /plan/advance (最后一步)   │
│  ① 更新 step N = completed │
│  ② plan = completed        │
│  ③ 如有 callback_url → 通知│
└────────────────────────────┘

用户
 │  GET /plan/{plan_id}
 ▼  查看进度和结果
```

### 关键特性

- Planning Agent 每次执行 < 10s，远在 150s 限制内
- 状态全靠 `plans` 表持久化，不靠内存
- 复用 Executor 的 callback 机制，无需新协议
- Step 间串行执行（MVP），后续可支持并行

## 4. API（3 个接口）

### 4.1 POST /plan — 提交高层需求

```
Authorization: Bearer <API_KEY>
```

```json
{
  "instruction": "给 my-app 加用户登录功能，支持 OAuth2 和邮箱密码",
  "context": {
    "repo": "anlaganlag/my-app",
    "ref": "main"
  },
  "callback_url": "https://optional/notify-me-when-done"
}
```

**Response: 202 Accepted**

```json
{
  "plan_id": "uuid",
  "status": "running",
  "steps": [
    {
      "order": 0,
      "blueprint_id": "bp_coding_task.1.0.0",
      "instruction": "实现邮箱密码注册和登录 API",
      "status": "dispatched",
      "run_id": "executor-run-uuid-1"
    },
    {
      "order": 1,
      "blueprint_id": "bp_coding_task.1.0.0",
      "instruction": "集成 OAuth2 (Google, GitHub) 登录",
      "status": "pending",
      "run_id": null
    },
    {
      "order": 2,
      "blueprint_id": "bp_test_feature_comprehensive_testing.1.0.0",
      "instruction": "为登录功能编写集成测试",
      "status": "pending",
      "run_id": null
    }
  ]
}
```

**内部逻辑：**

1. 校验 API Key
2. 调用 Claude API 拆解需求：

```
系统提示：你是一个技术规划器。将用户需求拆解为独立的执行步骤。
每一步必须包含：
- blueprint_id（从可用列表中选择）
- instruction（具体、独立、可执行的指令）
- order（执行顺序，从 0 开始）

可用 blueprint:
- bp_coding_task.1.0.0 — 通用编码（分析→实现→提PR）
- bp_code_review.1.0.0 — 代码审查
- bp_backend_coding_tdd_automation.1.0.0 — 后端 TDD
- bp_test_feature_comprehensive_testing.1.0.0 — 综合测试

输出 JSON 数组，不要解释。
```

3. 写 `plans` 表（status=running）
4. 调 Executor `POST /execute`（step 0），`callback_url` 指向 `/plan/advance`
5. 返回 plan + steps

### 4.2 POST /plan/advance — Executor 回调推进

**内部接口**，由 Executor 完成后自动触发。

```
X-Signature: HMAC-SHA256(<secret>, <body>)
```

```json
{
  "run_id": "executor-run-uuid-1",
  "status": "completed",
  "result": {
    "summary": "PR created",
    "pr_url": "https://github.com/...",
    "blocks": [...]
  }
}
```

**内部逻辑：**

1. HMAC 签名校验
2. 根据 `run_id` 找到对应的 plan + step
3. 更新当前 step 状态（completed / failed）
4. 判断下一步：

```python
if step.status == "failed":
    plan.status = "failed"          # 任一步骤失败 → 整个 plan 失败
elif has_next_step:
    dispatch_next_step()            # POST /execute (step N+1)
else:
    plan.status = "completed"       # 全部完成
    notify_callback_url()           # 通知调用方（如果有）
```

5. 更新 `plans` 表

### 4.3 GET /plan/{plan_id} — 查询进度

```
Authorization: Bearer <API_KEY>
```

**Response: 200 OK**

```json
{
  "plan_id": "uuid",
  "status": "running",
  "instruction": "给 my-app 加用户登录功能...",
  "steps": [
    {
      "order": 0,
      "blueprint_id": "bp_coding_task.1.0.0",
      "instruction": "实现邮箱密码注册和登录 API",
      "status": "completed",
      "run_id": "uuid-1",
      "result": {"pr_url": "https://..."}
    },
    {
      "order": 1,
      "blueprint_id": "bp_coding_task.1.0.0",
      "instruction": "集成 OAuth2 登录",
      "status": "running",
      "run_id": "uuid-2",
      "result": null
    },
    {
      "order": 2,
      "blueprint_id": "bp_test_feature_comprehensive_testing.1.0.0",
      "instruction": "编写集成测试",
      "status": "pending",
      "run_id": null,
      "result": null
    }
  ],
  "created_at": "...",
  "updated_at": "..."
}
```

## 5. 数据模型

```sql
create table plans (
  plan_id       uuid primary key default gen_random_uuid(),
  instruction   text not null,
  context       jsonb default '{}',
  callback_url  text,
  status        text not null default 'pending'
                  check (status in ('pending', 'running', 'completed', 'failed')),
  steps         jsonb not null default '[]',
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

create index idx_plans_status on plans(status);
```

### steps JSONB 结构

```json
[
  {
    "order": 0,
    "blueprint_id": "bp_coding_task.1.0.0",
    "instruction": "具体指令",
    "status": "pending",
    "run_id": null,
    "result": null
  }
]
```

**为什么用 JSONB 而不是独立表？**
- MVP 单表最简
- Steps 始终随 plan 一起读写，不需要独立查询
- 后续需要时可拆出 `plan_steps` 表

### steps 内 status 值

| status | 含义 |
|--------|------|
| `pending` | 等待前序步骤完成 |
| `dispatched` | 已提交给 Executor |
| `running` | Executor 正在执行 |
| `completed` | 执行成功 |
| `failed` | 执行失败 |
| `skipped` | 前序失败，跳过 |

## 6. 状态机

### Plan 状态

```
pending ──→ running ──→ completed
                   └──→ failed
```

```python
PLAN_TRANSITIONS = {
    "pending": {"running"},
    "running": {"completed", "failed"},
}
```

### 推进规则

```
当 /plan/advance 收到 step N 的回调：

  if step N completed:
    if step N+1 exists:
      dispatch step N+1 → plan stays "running"
    else:
      plan = "completed"

  if step N failed:
    mark remaining steps "skipped"
    plan = "failed"
```

## 7. 安全

| 接口 | 认证 |
|------|------|
| POST /plan | API Key (Bearer) |
| GET /plan/{id} | API Key (Bearer) |
| POST /plan/advance | HMAC-SHA256（复用 Executor 的 CALLBACK_HMAC_SECRET） |

### /plan/advance 校验流程

复用 Executor callback 的 HMAC 机制：
1. HMAC 签名校验 → 403
2. run_id 必须属于某个 plan 的某个 step → 404
3. 更新 plan

## 8. Claude API 调用（需求拆解）

### 请求

```typescript
const response = await fetch("https://api.anthropic.com/v1/messages", {
  method: "POST",
  headers: {
    "x-api-key": ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
  },
  body: JSON.stringify({
    model: "claude-sonnet-4-20250514",
    max_tokens: 1024,
    system: PLANNER_SYSTEM_PROMPT,
    messages: [{ role: "user", content: userInstruction }],
  }),
});
```

### 系统提示

```
你是一个技术规划器。将用户需求拆解为可独立执行的步骤。

规则：
1. 每步必须是一个独立的、可验证的交付物
2. 步骤间串行执行，后续步骤可以依赖前序步骤的产出
3. 通常 2-5 步，不要过度拆分
4. 每步指令要足够具体，让执行者不需要额外上下文就能完成

可用 blueprint：
- bp_coding_task.1.0.0 — 通用编码任务（分析→实现→提 PR）
- bp_code_review.1.0.0 — 代码审查
- bp_backend_coding_tdd_automation.1.0.0 — 后端编码（TDD 流程）
- bp_test_feature_comprehensive_testing.1.0.0 — 综合测试

输出严格 JSON 数组，不要任何解释：
[{"order": 0, "blueprint_id": "...", "instruction": "..."}, ...]
```

### 输出解析

```typescript
const text = response.content[0].text;
const steps = JSON.parse(text);  // 直接解析 JSON 数组
```

如果 Claude 返回非法 JSON → plan 立即 failed，error_code = `PLAN_PARSE_FAILED`。

## 9. Executor 回调路由

当前 Executor 的 `callback_url` 是在 `/execute` 请求时指定的。Planning Agent 利用这个机制：

```
POST /execute {
  ...
  "callback_url": "https://<project>.supabase.co/functions/v1/plan/advance"
}
```

Executor 完成后回调 `/plan/advance`，而不是 `/callback`。

**问题**：当前 Executor 回调的是固定的 `/callback` 端点（由 `CALLBACK_BASE_URL` 环境变量决定）。

**改动**：`/execute` 接口已支持 `callback_url` 字段。但当前 Kevin CLI 回调的是 `--callback-url` 参数指定的地址。所以：
- Planning Agent 在调 `/execute` 时传入 `callback_url`（不影响 Executor 现有逻辑）
- `/execute` Edge Function 需要把 caller 的 `callback_url` 透传给 GitHub Actions
- Kevin CLI 已经通过 `--callback-url` 接收回调地址 ✅

**需要确认**：当前 `/execute` 是否将 `callback_url` 传入 GitHub Actions dispatch payload？

查看现有代码：`callback_url` 在 dispatch payload 里是 **Edge Function 自己的 `/callback` 地址**（`CALLBACK_BASE_URL + "/callback"`），不是调用方传入的。

**MVP 方案**：保持现有流程不变。Executor 完成后仍回调 `/callback`，由 `/callback` 负责转发：

```
Executor → POST /callback (现有流程)
              │
              ├─ 更新 runs 表
              └─ 如果 runs.callback_url 存在
                   → POST runs.callback_url (转发给 Planning Agent)
```

这样 `/callback` 成为统一的回调入口，转发给调用方注册的 `callback_url`。

## 10. /callback 需要的改动

在现有 `/callback` Edge Function 末尾，添加转发逻辑：

```typescript
// 更新 runs 表之后...

// 转发给调用方的 callback_url（如果存在）
const { data: runData } = await db
  .from("runs")
  .select("callback_url")
  .eq("run_id", run_id)
  .single();

if (runData?.callback_url) {
  // 用同样的 HMAC 签名转发
  const forwardSig = await signHmac(HMAC_SECRET, rawBody);
  await fetch(runData.callback_url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Signature": forwardSig,
    },
    body: rawBody,
  }).catch(() => {}); // 转发失败不影响主流程
}
```

## 11. 文件结构

```
supabase/
  functions/
    plan/index.ts           # POST /plan — 拆解需求 + 触发第一步
    plan-advance/index.ts   # POST /plan/advance — 回调推进
    plan-status/index.ts    # GET /plan/{plan_id} — 查询进度
    callback/index.ts       # 修改：添加 callback_url 转发逻辑
  migrations/
    002_create_plans.sql    # plans 表
```

## 12. 完整调用链示例

```
用户: POST /plan
  instruction: "给 my-app 加用户登录，支持 OAuth2 和邮箱密码"
  context: {repo: "anlaganlag/my-app", ref: "main"}

Planning Agent:
  ① Claude API 拆解 → 3 步
  ② 写 plans 表
  ③ POST /execute (step 0: "实现邮箱密码注册和登录 API")
     callback_url 存入 runs.callback_url = /plan/advance
  ④ 返回 plan_id

~3min 后...

Executor 完成 step 0 → POST /callback
  /callback:
    ① 更新 runs 表
    ② 发现 runs.callback_url → 转发到 /plan/advance

/plan/advance:
  ① 找到 plan + step (via run_id)
  ② 更新 step 0 = completed
  ③ POST /execute (step 1: "集成 OAuth2 登录")
  ④ 更新 plans 表

~4min 后...

Executor 完成 step 1 → POST /callback → 转发 → /plan/advance
  ① 更新 step 1 = completed
  ② POST /execute (step 2: "编写集成测试")

~3min 后...

Executor 完成 step 2 → POST /callback → 转发 → /plan/advance
  ① 更新 step 2 = completed
  ② 没有更多 step → plan = completed
  ③ 通知 callback_url（如果用户提供了）

总耗时: ~10 分钟（3 步串行）
用户随时可查: GET /plan/{plan_id}
```

## 13. MVP 不做的事

| 项目 | 原因 |
|------|------|
| 步骤并行执行 | MVP 串行更简单，失败语义清晰 |
| 步骤间上下文传递 | step N 的结果自动传给 step N+1 — 后续加 |
| Plan 取消 | 复杂度高，先不做 |
| 步骤重试 | Executor 已有 block 级重试，plan 级先不加 |
| 动态重规划 | step 失败后自动调整后续步骤 — 高级功能 |
| 多 plan 并发限制 | 初期调用量小 |

## 14. 依赖项（需先完成）

| 项目 | 状态 | 说明 |
|------|------|------|
| Executor /execute 支持 callback_url 透传 | ✅ 已有字段 | runs 表已存 callback_url |
| /callback 添加转发逻辑 | ❌ 需改动 | 见第 10 节 |
| ANTHROPIC_API_KEY 配置到 Edge Function | ❌ 需设置 | Claude API 拆解需求用 |

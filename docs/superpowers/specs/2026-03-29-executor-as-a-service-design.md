# Executor as a Service — MVP Spec

> **Date**: 2026-03-29
> **Status**: Draft
> **Scope**: 最小可 demo 版本 — 3 个接口 + 1 张表

---

## 1. 目标

Planning Agent 通过 HTTP 提交任务，Kevin 在 GitHub Actions 执行，回调结果。

```
POST /execute  →  Supabase DB  →  GitHub Actions  →  POST /callback
                                                          ↓
GET /status/{id}  ←──────────── Supabase DB  ←────────────┘
```

## 2. 核心概念

| 字段 | 含义 | 示例 |
|------|------|------|
| `instruction` | 做什么 | "实现用户登录功能" |
| `context` | 用什么 | `{"repo": "owner/app", "ref": "main"}` |
| `blueprint_id` | 怎么做 | `bp_coding_task.1.0.0`（引用 repo 中 YAML） |

## 3. 数据模型（单表）

```sql
create table runs (
  run_id         uuid primary key default gen_random_uuid(),
  blueprint_id   text not null,
  instruction    text not null,
  context        jsonb default '{}',
  callback_url   text,
  status         text not null default 'pending',
  result         jsonb,           -- 完成时写入，含 blocks 状态
  error_code     text,
  error_message  text,
  created_at     timestamptz default now(),
  updated_at     timestamptz default now()
);
```

## 4. 状态机

```
pending ──→ dispatched ──→ running ──→ completed
                │                 └──→ failed
                └──→ dispatch_failed
```

全部终态：`completed`、`failed`、`dispatch_failed`

```python
TRANSITIONS = {
    "pending":     {"dispatched", "dispatch_failed"},
    "dispatched":  {"running"},
    "running":     {"completed", "failed"},
}
```

写入前校验：`new_status not in TRANSITIONS[current] → reject`

## 5. API（3 个接口）

### 5.1 POST /execute

```
Authorization: Bearer <API_KEY>
```

```json
{
  "blueprint_id": "bp_coding_task.1.0.0",
  "instruction": "实现用户登录功能",
  "context": { "repo": "owner/app", "ref": "main" },
  "callback_url": "https://optional/webhook"
}
```

**Response: 202**

```json
{ "run_id": "uuid", "status": "pending" }
```

**逻辑：**
1. 校验 API Key
2. 插入 `runs` 记录（status=pending）
3. 调用 GitHub API `repository_dispatch`（event_type=`executor-run`，payload 含 run_id 等）
4. dispatch 成功 → 更新 status=dispatched → 返回 202
5. dispatch 失败 → 更新 status=dispatch_failed → 返回 502

### 5.2 GET /status/{run_id}

```
Authorization: Bearer <API_KEY>
```

**Response: 200**

```json
{
  "run_id": "uuid",
  "blueprint_id": "bp_coding_task.1.0.0",
  "status": "running",
  "result": null,
  "created_at": "...",
  "updated_at": "..."
}
```

完成后 `result` 示例：

```json
{
  "result": {
    "summary": "PR created",
    "pr_url": "https://github.com/...",
    "blocks": [
      { "block_id": "B1", "status": "passed" },
      { "block_id": "B2", "status": "passed" },
      { "block_id": "B3", "status": "failed", "error": "tests failed" }
    ]
  }
}
```

### 5.3 POST /callback（内部，Kevin → Edge Function）

```
X-Signature: HMAC-SHA256(<secret>, <body>)
```

```json
{
  "run_id": "uuid",
  "status": "completed",
  "result": { "summary": "...", "blocks": [...] }
}
```

或失败：

```json
{
  "run_id": "uuid",
  "status": "failed",
  "error_code": "BLOCK_FAILED",
  "error_message": "B2: pytest exit code 1",
  "result": { "blocks": [...] }
}
```

**逻辑：**
1. HMAC 签名校验 → 失败 403
2. 状态机校验 → 非法转换 409
3. 更新 `runs`（status + result + error_code + updated_at）
4. 返回 200

## 6. 安全

| 接口 | 认证 |
|------|------|
| /execute, /status | API Key (Bearer token) |
| /callback | HMAC-SHA256 |

两个 secret，存 Supabase Edge Function 环境变量：
- `EXECUTOR_API_KEY` — 调用方持有
- `CALLBACK_HMAC_SECRET` — GitHub Actions 持有

## 7. Kevin CLI 改动

新增 executor 模式：

```bash
python -m kevin run \
  --run-id <uuid> \
  --blueprint <blueprint_id> \
  --instruction "..." \
  --context '{"repo": "..."}' \
  --callback-url "https://xxx/callback" \
  --callback-secret "<hmac_secret>"
```

与现有 `--issue` 模式并存。核心变化：
- 输入从 GitHub Issue → CLI 参数
- 执行完通过 HTTP 回调（替代 GitHub comment）
- Block 执行逻辑（claude_cli / shell / api_call）**不变**

Kevin 回调时机：
- `dispatched → running`：首个 block 开始前回调一次
- `running → completed/failed`：全部 block 完成后回调一次
- **共 2 次回调**，最简

## 8. GitHub Actions

```yaml
name: Kevin Executor
on:
  repository_dispatch:
    types: [executor-run]
jobs:
  execute:
    runs-on: ubuntu-latest
    timeout-minutes: 35
    steps:
      - uses: actions/checkout@v4
      - run: npm install -g @anthropic-ai/claude-code && pip install -e .
      - run: |
          python -m kevin run \
            --run-id "${{ github.event.client_payload.run_id }}" \
            --blueprint "${{ github.event.client_payload.blueprint_id }}" \
            --instruction "${{ github.event.client_payload.instruction }}" \
            --context '${{ github.event.client_payload.context }}' \
            --callback-url "${{ github.event.client_payload.callback_url }}" \
            --callback-secret "${{ secrets.CALLBACK_HMAC_SECRET }}"
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## 9. 文件结构

```
supabase/
  functions/
    execute/index.ts     # POST /execute
    status/index.ts      # GET /status/{run_id}
    callback/index.ts    # POST /callback
  migrations/
    001_create_runs.sql  # runs 单表
```

## 10. Demo 流程

```bash
# 1. 提交任务
curl -X POST https://<project>.supabase.co/functions/v1/execute \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"blueprint_id":"bp_coding_task.1.0.0","instruction":"添加健康检查接口","context":{"repo":"owner/app"}}'

# 返回: {"run_id": "abc-123", "status": "pending"}

# 2. 轮询状态
curl https://<project>.supabase.co/functions/v1/status/abc-123 \
  -H "Authorization: Bearer $API_KEY"

# 返回: {"status": "running", ...}
# 等待...
# 返回: {"status": "completed", "result": {"pr_url": "..."}}
```

## 11. MVP 后扩展

| 后续 | 何时加 |
|------|-------|
| Idempotency Key | 调用方会重试时 |
| /cancel | 需要中断长任务时 |
| run_events 事件流 | 需要细粒度观测时 |
| blocks 表 | 需要独立查询 block 状态时 |
| dispatch 重试 / pg_cron | 可靠性要求提高时 |
| callback 转发 | 调用方不想轮询时 |

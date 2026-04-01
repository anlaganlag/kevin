# Kevin Executor API — 快速接入指南

> **最后更新**: 2026-04-01
> **Base URL**: `https://yldkolafvxgolwtthguo.supabase.co/functions/v1`
> **认证**: Bearer Token（找管理员获取 `EXECUTOR_API_KEY`）

---

## 30 秒上手

```bash
# 1. 设置环境变量
export API_KEY="<your-api-key>"
export BASE="https://yldkolafvxgolwtthguo.supabase.co/functions/v1"

# 2. 提交任务
curl -X POST "${BASE}/execute" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_id": "bp_coding_task.1.0.0",
    "instruction": "Add a /health endpoint that returns {\"status\": \"ok\"}",
    "context": {"repo": "centific-cn/AgenticSDLC", "ref": "main"}
  }'
# → {"run_id": "xxx-xxx", "status": "dispatched"}

# 3. 查看结果
curl "${BASE}/status/<run_id>" -H "Authorization: Bearer ${API_KEY}"
```

---

## 5 个核心 Blueprint

### 1. `bp_coding_task.1.0.0` — 编码任务

最常用的 blueprint。给一个编码指令，agent 自动实现、写测试、提 PR。

```bash
curl -X POST "${BASE}/execute" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_id": "bp_coding_task.1.0.0",
    "instruction": "在 kevin/utils.py 中添加 is_valid_run_id(run_id: str) -> bool 函数，验证 UUID v4 格式，包含单元测试",
    "context": {"repo": "centific-cn/AgenticSDLC", "ref": "main"}
  }'
```

**典型用途**: 新功能开发、bug 修复、工具函数添加
**预期耗时**: 3-8 分钟
**产出**: 代码变更 + 单元测试 + PR

---

### 2. `bp_backend_coding_tdd_automation.1.0.0` — TDD 开发

先写测试再实现的 TDD 流程。适合需要高测试覆盖的后端任务。

```bash
curl -X POST "${BASE}/execute" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_id": "bp_backend_coding_tdd_automation.1.0.0",
    "instruction": "TDD 实现 retry_with_backoff(fn, max_retries=3, base_delay=1.0) 装饰器，指数退避策略",
    "context": {"repo": "centific-cn/AgenticSDLC", "ref": "main"}
  }'
```

**典型用途**: 核心业务逻辑、需要 95%+ 覆盖率的模块
**预期耗时**: 5-12 分钟
**产出**: 测试先行 + 实现代码 + 覆盖率报告

---

### 3. `bp_test_unit.1.0.0` — 单元测试

为已有代码补充单元测试。自动检测项目测试框架（pytest/jest/go test）。

```bash
curl -X POST "${BASE}/execute" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_id": "bp_test_unit.1.0.0",
    "instruction": "为 kevin/intent.py 的 classify() 函数添加单元测试，覆盖 exact match、alias fallback、unknown label 三种场景",
    "context": {"repo": "centific-cn/AgenticSDLC", "ref": "main"}
  }'
```

**典型用途**: 提升测试覆盖、回归测试、新模块测试
**预期耗时**: 2-5 分钟
**产出**: 测试文件 + 覆盖率数据

---

### 4. `bp_code_review.1.0.0` — 代码审查

自动审查代码变更，产出结构化 review 报告。

```bash
curl -X POST "${BASE}/execute" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_id": "bp_code_review.1.0.0",
    "instruction": "Review PR #85 的代码质量，重点检查安全性和边界情况覆盖",
    "context": {"repo": "centific-cn/AgenticSDLC", "ref": "main"}
  }'
```

**典型用途**: PR 审查、安全审计、代码质量检查
**预期耗时**: 3-6 分钟
**产出**: Review 报告（.kevin/review_report.md）

---

### 5. `bp_ba_requirement_analysis.1.0.0` — 需求分析

纯分析型 blueprint，不改代码。产出需求分析文档。

```bash
curl -X POST "${BASE}/execute" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_id": "bp_ba_requirement_analysis.1.0.0",
    "instruction": "分析 blueprint 参数验证需求：executor 应在编译阶段校验所有必需模板变量是否已提供",
    "context": {"repo": "centific-cn/AgenticSDLC", "ref": "main"}
  }'
```

**典型用途**: 新功能需求分析、技术方案评估、gap 分析
**预期耗时**: 3-8 分钟
**产出**: 分析文档（.kevin/analysis.md）

---

## API 参考

### POST /execute — 提交任务

```
POST /execute
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

**请求体**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `blueprint_id` | string | ✅ | Blueprint ID（见上方 5 个核心 blueprint） |
| `instruction` | string | ✅ | 自然语言任务描述 |
| `context` | object | 否 | `{"repo": "owner/repo", "ref": "branch"}` |
| `idempotency_key` | string | 否 | 防重复提交（同 key 返回已有 run） |
| `callback_url` | string | 否 | 完成后 webhook 通知地址 |

**响应**:

| 状态码 | 含义 |
|--------|------|
| 202 | 已派发：`{"run_id": "uuid", "status": "dispatched"}` |
| 200 | 幂等命中：`{"run_id": "uuid", "status": "...", "deduplicated": true}` |
| 400 | 参数错误（缺字段、未知 blueprint、repo 格式错） |
| 401 | 未认证 |
| 429 | 限流（每分钟 10 次） |

---

### GET /status — 查询状态

```bash
# 查询单个 run
GET /status/<run_id>
GET /status/<run_id>?events=true    # 带事件时间线

# 列出最近 runs
GET /status?limit=10
```

**Run 状态流转**:

```
pending → dispatched → running → completed
                  ↓        ↓
            dispatch_failed  failed
                             cancelled
```

**响应示例**:

```json
{
  "run_id": "57a9722b-...",
  "blueprint_id": "bp_coding_task.1.0.0",
  "status": "completed",
  "instruction": "Add is_valid_run_id helper",
  "result": {"summary": "Blueprint completed", "blocks": [...]},
  "elapsed_seconds": 790,
  "events": [
    {"event_type": "status_change", "payload": {"from": "dispatched", "to": "running"}},
    {"event_type": "status_change", "payload": {"from": "running", "to": "completed"}}
  ]
}
```

---

### POST /cancel — 取消任务

```bash
curl -X POST "${BASE}/cancel" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"run_id": "<run_id>"}'
```

只能取消 `pending`/`dispatched`/`running` 状态的 run。已完成的返回 409。

---

### GET /health — 健康检查（无需认证）

```bash
curl "${BASE}/health"
```

返回服务状态、可用 blueprint 列表、DB 连接状态、24h 运行统计。

---

## 全部可用 Blueprint

除上述 5 个核心 blueprint 外，还有 12 个可用：

| Blueprint ID | 用途 |
|---|---|
| `bp_frontend_feature_ui_design.1.0.0` | 前端功能开发 |
| `bp_architecture_blueprint_design.1.0.0` | 架构设计 |
| `bp_deployment_monitoring_automation.1.0.0` | 部署与监控 |
| `bp_function_implementation_fip_blueprint.1.0.0` | FIP 功能实现 |
| `bp_test_feature_comprehensive_testing.1.0.0` | 综合测试 |
| `bp_test_integration.1.0.0` | 集成测试 |
| `bp_test_e2e.1.0.0` | E2E 测试 |
| `bp_test_frontend.1.0.0` | 前端测试 |
| `bp_test_advanced.1.0.0` | 高级测试（安全+性能） |
| `bp_test_environment_setup.1.0.0` | 测试环境搭建 |
| `bp_test_strategy_design.1.0.0` | 测试策略设计 |
| `bp_test_report_signoff.1.0.0` | 测试报告签收 |

完整列表可通过 `GET /health` 获取。

---

## 最佳实践

### 1. 写好 instruction

```
❌ "修个 bug"
✅ "修复 kevin/state.py 的 format_duration() 在输入 None 时抛出 TypeError，应返回空字符串"
```

instruction 越具体，agent 产出越精准。包含：**做什么 + 在哪里 + 验收标准**。

### 2. 用 idempotency_key 防重复

```json
{
  "idempotency_key": "fix-format-duration-none-20260401",
  ...
}
```

网络超时重试时，同 key 不会创建新 run。

### 3. 用 context.ref 指定分支

```json
{
  "context": {"repo": "centific-cn/AgenticSDLC", "ref": "feat/my-branch"},
  ...
}
```

默认 `main`，但可以指定任意分支。

### 4. 轮询间隔

```
推荐：每 15 秒轮询一次
超时：10 分钟无变化视为异常
```

或使用 `callback_url` 免轮询——任务完成后 API 会主动 POST 结果到你的 URL。

### 5. 限流

每个 API Key 每分钟 10 次请求。超限返回 429。合理间隔请求即可。

---

## 常见问题

**Q: 任务 dispatched 但一直没有变成 running？**
A: GitHub Actions 可能排队中。通常 30 秒内开始，高峰期可能 1-2 分钟。

**Q: 状态变成 failed，怎么查原因？**
A: `GET /status/<run_id>` 的 `error_code` 和 `error_message` 字段有详情。

**Q: 可以取消正在运行的任务吗？**
A: 可以。`POST /cancel {"run_id": "xxx"}`。但 Claude CLI 进程可能需要几秒才真正停止。

**Q: 怎么知道有哪些 blueprint 可用？**
A: `GET /health` 返回完整列表。

**Q: context.repo 可以指向其他仓库吗？**
A: 可以，只要格式是 `owner/repo` 且 GitHub App 有访问权限。

---

## Python 客户端示例

```python
import json
import time
import urllib.request

BASE = "https://yldkolafvxgolwtthguo.supabase.co/functions/v1"
API_KEY = "<your-api-key>"


def execute(blueprint_id: str, instruction: str, repo: str = "", ref: str = "main") -> dict:
    body = {"blueprint_id": blueprint_id, "instruction": instruction}
    if repo:
        body["context"] = {"repo": repo, "ref": ref}
    req = urllib.request.Request(
        f"{BASE}/execute",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def wait_for_completion(run_id: str, timeout: int = 600) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        req = urllib.request.Request(
            f"{BASE}/status/{run_id}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        if data["status"] in ("completed", "failed", "cancelled"):
            return data
        time.sleep(15)
    raise TimeoutError(f"Run {run_id} did not complete in {timeout}s")


# 使用示例
result = execute("bp_coding_task.1.0.0", "Add hello() function to utils.py", "centific-cn/AgenticSDLC")
print(f"Dispatched: {result['run_id']}")

final = wait_for_completion(result["run_id"])
print(f"Result: {final['status']}")
```

---

## E2E 验证记录（2026-04-01）

| Blueprint | Run ID | 状态 | 耗时 |
|---|---|---|---|
| bp_coding_task | 57a9722b | ✅ completed | 790s |
| bp_backend_coding_tdd | d2380212 | ✅ completed | 789s |
| bp_ba_requirement_analysis | 2b2fea77 | ✅ completed | 788s |
| bp_code_review | c76ce9dc | ✅ completed | 787s |
| bp_test_unit | 08e42952 | ✅ completed | 186s |

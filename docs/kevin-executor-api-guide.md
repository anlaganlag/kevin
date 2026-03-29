# Kevin Executor API 使用指南

## 认证信息

| 项目 | 值 |
|------|---|
| Base URL | `https://yldkolafvxgolwtthguo.supabase.co/functions/v1` |
| API Key | `r8im8LdRShJ8Ze6ujaGV5b7CI/5YO0Mr3f7r8ZFkqsI=` |

所有请求都需要 Header: `Authorization: Bearer <API_KEY>`

---

## 0. 检查服务状态 + 可用 Blueprint

```bash
curl -s "https://yldkolafvxgolwtthguo.supabase.co/functions/v1/execute" \
  -H "Authorization: Bearer r8im8LdRShJ8Ze6ujaGV5b7CI/5YO0Mr3f7r8ZFkqsI=" \
  | python3 -m json.tool
```

返回：
```json
{
    "status": "ok",
    "service": "kevin-executor",
    "available_blueprints": [
        "bp_coding_task.1.0.0",
        "bp_code_review.1.0.0",
        "bp_backend_coding_tdd_automation.1.0.0",
        "bp_function_implementation_fip_blueprint.1.0.0",
        "bp_test_feature_comprehensive_testing.1.0.0"
    ]
}
```

---

## 1. 提交任务

```bash
curl -s -X POST "https://yldkolafvxgolwtthguo.supabase.co/functions/v1/execute" \
  -H "Authorization: Bearer r8im8LdRShJ8Ze6ujaGV5b7CI/5YO0Mr3f7r8ZFkqsI=" \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_id": "bp_coding_task.1.0.0",
    "instruction": "你的任务描述，越详细越好",
    "context": {
      "repo": "centific-cn/kevin-test-target",
      "ref": "main"
    }
  }' | python3 -m json.tool
```

**返回示例（HTTP 202）：**
```json
{
    "run_id": "675e04ae-0f40-4b41-b3ef-df238d5e6a6e",
    "status": "dispatched"
}
```

记下 `run_id`，用于查询状态。

---

## 2. 查询单个任务状态

```bash
curl -s "https://yldkolafvxgolwtthguo.supabase.co/functions/v1/status/{run_id}" \
  -H "Authorization: Bearer r8im8LdRShJ8Ze6ujaGV5b7CI/5YO0Mr3f7r8ZFkqsI=" \
  | python3 -m json.tool
```

**状态流转：** `pending` → `dispatched` → `running` → `completed` / `failed`

一般 3-5 分钟完成。建议每 10 秒轮询一次。

---

## 3. 查看最近所有任务

忘了 run_id？查看最近提交的任务：

```bash
curl -s "https://yldkolafvxgolwtthguo.supabase.co/functions/v1/status?limit=10" \
  -H "Authorization: Bearer r8im8LdRShJ8Ze6ujaGV5b7CI/5YO0Mr3f7r8ZFkqsI=" \
  | python3 -m json.tool
```

---

## 4. 参数说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `blueprint_id` | ✅ | 先调 GET /execute 查看可用列表。常用：`bp_coding_task.1.0.0` |
| `instruction` | ✅ | 任务描述，自然语言，越详细越好 |
| `context.repo` | ✅ | 目标仓库，格式 `owner/repo` |
| `context.ref` | 否 | 目标分支，默认 `main` |

### Blueprint 简介

| Blueprint | 用途 |
|-----------|------|
| `bp_coding_task.1.0.0` | 通用编码任务（分析→编码→提PR），最常用 |
| `bp_code_review.1.0.0` | 代码审查 |
| `bp_backend_coding_tdd_automation.1.0.0` | 后端编码（TDD流程） |
| `bp_function_implementation_fip_blueprint.1.0.0` | 功能实现 |
| `bp_test_feature_comprehensive_testing.1.0.0` | 综合测试 |

---

## 5. 完整示例：一键提交 + 轮询

```bash
#!/bin/bash
API_KEY="r8im8LdRShJ8Ze6ujaGV5b7CI/5YO0Mr3f7r8ZFkqsI="
BASE="https://yldkolafvxgolwtthguo.supabase.co/functions/v1"

# 提交
BODY=$(curl -s -X POST "${BASE}/execute" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_id": "bp_coding_task.1.0.0",
    "instruction": "Add a /health endpoint that returns {\"status\": \"ok\"}",
    "context": {"repo": "centific-cn/kevin-test-target", "ref": "main"}
  }')

RUN_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "Submitted: ${RUN_ID}"

# 轮询
while true; do
  RESP=$(curl -s "${BASE}/status/${RUN_ID}" -H "Authorization: Bearer ${API_KEY}")
  STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "$(date +%H:%M:%S) status=${STATUS}"
  [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] && break
  sleep 10
done

echo "$RESP" | python3 -m json.tool
```

---

## 6. 常见错误 & 排查

| 现象 | 原因 | 解决 |
|------|------|------|
| `401 Unauthorized` + hint | 缺少或错误的 Authorization header | 检查 `Bearer ` 前缀和 API Key 是否完整 |
| `400 Invalid JSON body` | curl -d 里的 JSON 格式错 | 检查引号转义、逗号、大括号 |
| `400 Unknown blueprint_id` | blueprint_id 拼错 | 调 GET /execute 查看可用列表 |
| `400 Invalid context.repo format` | repo 格式不对 | 用 `owner/repo` 格式 |
| 状态一直 `dispatched` | GitHub Actions 排队中 | 等几分钟，或检查 repo 的 Actions 页面 |
| 状态 `failed` + BLOCK_FAILED | 某个执行步骤失败 | 查看返回的 result.blocks 定位哪个 block 失败 |

---

## 7. 注意事项

- 任务完成后会在目标 repo **自动创建 PR**
- 每次执行大约消耗 **3-5 分钟**
- 目标 repo **必须是非空仓库**（至少有一个 commit）
- instruction 中如需包含双引号，用 `\"` 转义
- 目前所有用户共享同一个 API Key

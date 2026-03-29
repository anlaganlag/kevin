# Kevin Planning Agent — E2E 手工验证清单

**日期:** 2026-03-27
**Run ID:** `20260326-164333-cd7897`
**Blueprint:** `bp_coding_task.1.0.0`
**Issue:** centific-cn/kevin-test-target#1
**PR:** centific-cn/kevin-test-target#2
**总耗时:** ~2 分钟 (16:43:33 → 16:45:19 UTC)

---

## 一、验证入口（你需要打开的链接）

| # | 资源 | URL | 验证什么 |
|---|------|-----|---------|
| 1 | GitHub Issue | https://github.com/centific-cn/kevin-test-target/issues/1 | Kevin 的评论（启动 + 完成） |
| 2 | Pull Request | https://github.com/centific-cn/kevin-test-target/pull/2 | 代码变更、PR 描述 |
| 3 | Kevin 源码 | https://github.com/anlaganlag/kevin | 推送的完整仓库 |

---

## 二、Issue #1 评论验证

打开 Issue #1，你应该看到 Kevin 发了以下评论（按时间顺序）：

**前 3 条是失败的调试记录（已修复的 bug），第 4 条是成功的：**

| # | 评论内容 | 状态 | 说明 |
|---|---------|------|------|
| 1 | `Kevin started bp_coding_task.1.0.0 (run: 20260326-163536-c193f2)` | failed | `--cwd` flag 不存在 |
| 2 | `Kevin started bp_coding_task.1.0.0 (run: 20260326-163613-6f9425)` | failed | Claude 未获 Write 权限 |
| 3 | `Kevin started bp_coding_task.1.0.0 (run: 20260326-163942-f99943)` | failed | `git_diff_check` 只检查 working tree |
| 4 | `Kevin started bp_coding_task.1.0.0 (run: 20260326-164333-cd7897)` | **completed** | 最终成功 |

**验证第 4 条评论包含：**
```
Kevin run `20260326-164333-cd7897` — **completed**

| Block | Status |
|-------|--------|
| B1 | ✅ passed |
| B2 | ✅ passed |
| B3 | ✅ passed |
```

---

## 三、PR #2 验证

### 3.1 PR 元数据

| 字段 | 预期值 |
|------|--------|
| Title | `Add a /health endpoint that returns system status and uptime` |
| State | `OPEN` |
| Base branch | `main` |
| Head branch | `kevin/issue-1` |
| Changed files | 2 (`app.py`, `tests/test_app.py`) |
| Additions | 41 |
| Deletions | 0 |
| Label | `kevin-automated` |

### 3.2 PR Body 应包含

- `Resolves #1`
- Changes 统计（`2 files changed, 41 insertions(+)`）
- 来自 `.kevin/analysis.md` 的分析摘要
- 底部签名：`_Automated by Kevin Planning Agent via bp_coding_task.1.0.0_`

### 3.3 代码变更验证

**app.py — 新增部分：**

```python
import datetime
import time

APP_START_TIME = time.monotonic()

@app.route("/health")
def health():
    uptime = round(time.monotonic() - APP_START_TIME, 2)
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return jsonify({"status": "ok", "uptime_seconds": uptime, "timestamp": timestamp})
```

**验证点：**
- [ ] 使用 `time.monotonic()`（非 `time.time()`）— 避免系统时钟漂移
- [ ] `APP_START_TIME` 在模块级别定义 — 应用启动时记录
- [ ] `uptime_seconds` round 到 2 位小数 — 合理精度
- [ ] timestamp 使用 UTC + ISO 8601 — 符合 Issue 要求
- [ ] `status` 固定返回 `"ok"` — 符合 Issue 的 "degraded" 留待未来扩展
- [ ] 无认证要求 — 符合 Issue 的 "no authentication" 要求

**tests/test_app.py — 新增 5 个测试：**

```python
def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200

def test_health_response_schema(client):
    data = client.get("/health").get_json()
    assert set(data.keys()) == {"status", "uptime_seconds", "timestamp"}

def test_health_status_is_ok(client):
    data = client.get("/health").get_json()
    assert data["status"] == "ok"

def test_health_uptime_is_non_negative_number(client):
    data = client.get("/health").get_json()
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0

def test_health_timestamp_is_valid_iso8601(client):
    data = client.get("/health").get_json()
    parsed = datetime.datetime.fromisoformat(data["timestamp"])
    assert parsed.tzinfo is not None
```

**验证点：**
- [ ] 5 个新测试覆盖 Issue 的所有 Acceptance Criteria
- [ ] 测试 schema 检查字段完备性（`set(data.keys()) == {...}`）
- [ ] 测试类型安全（`isinstance(data["uptime_seconds"], (int, float))`）
- [ ] 测试时区感知（`parsed.tzinfo is not None`）
- [ ] 原有 2 个测试未被修改（`test_index_returns_200`, `test_index_returns_json`）

---

## 四、本地复现测试

在你的机器上跑以下命令验证代码可运行：

```bash
# 1. 克隆目标仓库
git clone https://github.com/centific-cn/kevin-test-target.git /tmp/kevin-verify
cd /tmp/kevin-verify

# 2. 切换到 Kevin 生成的 branch
git checkout kevin/issue-1

# 3. 安装依赖
pip install flask pytest

# 4. 跑测试
pytest tests/ -v

# 预期输出：7 passed (2 原有 + 5 新增)

# 5. 手动验证 endpoint
python -c "
from app import app
with app.test_client() as c:
    r = c.get('/health')
    print(r.status_code, r.get_json())
"
# 预期输出: 200 {'status': 'ok', 'uptime_seconds': <number>, 'timestamp': '<ISO 8601>'}
```

---

## 五、Kevin Run State 验证

Run state 持久化在 `.kevin/runs/20260326-164333-cd7897/`：

```bash
cd /tmp/kevin-test-target
ls -la .kevin/runs/20260326-164333-cd7897/
```

### 5.1 run.yaml — 总体运行状态

| 字段 | 值 | 验证 |
|------|---|------|
| `run_id` | `20260326-164333-cd7897` | |
| `blueprint_id` | `bp_coding_task.1.0.0` | |
| `issue_number` | `1` | |
| `repo` | `centific-cn/kevin-test-target` | |
| `status` | `completed` | ← 最重要 |
| `created_at` | `2026-03-26T16:43:33Z` | |
| `completed_at` | `2026-03-26T16:45:19Z` | ~2 分钟完成 |

### 5.2 Block 状态

| Block | Status | Runner | Retries | Validators |
|-------|--------|--------|---------|------------|
| B1 | **passed** | claude_cli | 0 | `file_exists(.kevin/analysis.md)` ✅ |
| B2 | **passed** | claude_cli | 0 | `git_diff_check(2 files vs main)` ✅, `command(grep 'feat:')` ✅ |
| B3 | **passed** | shell | 0 | `command(gh pr list)` ✅ |

### 5.3 Validator 详情

**B1 validator:**
```yaml
- type: file_exists
  passed: true
  path: /tmp/kevin-test-target/.kevin/analysis.md
```

**B2 validators:**
```yaml
- type: git_diff_check
  passed: true
  files_changed: 2
  committed_vs_main: 2
  uncommitted: 0
  expected_min: 1

- type: command
  command: "git log --oneline -1 | grep -q 'feat:'"
  exit_code: 0
  passed: true
```

**B3 validator:**
```yaml
- type: command
  command: "gh pr list --head kevin/issue-1 --json number --jq '.[0].number'"
  exit_code: 0
  passed: true
```

### 5.4 其他文件

| 文件 | 内容 |
|------|------|
| `blueprint_snapshot.yaml` | `bp_coding_task.1.0.0.yaml` 的完整快照 — 确保历史可复现 |
| `logs/B1.log` | B1 的完整 prompt + Claude stdout |
| `logs/B2.log` | B2 的完整 prompt + Claude stdout |
| `logs/B3.log` | B3 的 shell 命令 stdout + stderr |

---

## 六、.kevin/analysis.md — B1 产出验证

Claude 在 B1 阶段生成的分析文档：

```markdown
# Issue #1: Add /health endpoint

## Summary
Add a `GET /health` endpoint to the existing Flask app that returns
system status, server uptime in seconds, and the current ISO 8601 timestamp.

## Files to Modify
| File | Change |
|------|--------|
| `app.py` | Add `/health` route. Record `APP_START_TIME` via `time.monotonic()`. |
| `tests/test_app.py` | Add tests for the new endpoint. |

## Test Scenarios
1. Happy path — GET /health returns 200
2. Response schema — JSON contains exactly `status`, `uptime_seconds`, `timestamp`
3. Status value — `status` equals `"ok"`
4. Uptime type — `uptime_seconds` is a number >= 0
5. Timestamp format — `timestamp` is a valid ISO 8601 string

## Risks
- None significant. Straightforward additive change.
```

**验证点：**
- [ ] 分析文档结构完整（Summary, Files, Tests, Risks）
- [ ] 正确识别了需要修改的文件
- [ ] 测试场景与实际实现的测试一致
- [ ] 技术决策合理（`time.monotonic()` > `time.time()`）

---

## 七、调试历程（3 个 bug 及修复）

E2E 过程中发现并修复了 3 个 Kevin Runtime bug：

| # | Bug | 原因 | 修复 |
|---|-----|------|------|
| 1 | `unknown option '--cwd'` | Claude CLI 无 `--cwd` flag | 改用 `subprocess.run(cwd=...)` |
| 2 | Claude 请求 Write 权限但无法交互 | `-p` 模式下无交互 | 添加 `--allowedTools Read,Write,Edit,Bash,Glob,Grep` |
| 3 | `git_diff_check` 在 B2 报 0 changes | 只检查 working tree，不查 committed diff vs main | 改为 `git diff main...HEAD --name-only` |

这 3 个 bug 是**评审文档 §八 风险登记簿**中 "Claude CLI exit 0 但未完成任务" 的具体体现。验证器层（L1 git_diff_check + L2 command）成功捕获了问题。

---

## 八、Acceptance Criteria 对照

Issue #1 的 Acceptance Criteria vs 实际产出：

| Criteria | 状态 | 证据 |
|----------|------|------|
| GET `/health` returns 200 with JSON response | ✅ | `test_health_returns_200` passed |
| Response includes `status`, `uptime_seconds`, `timestamp` | ✅ | `test_health_response_schema` passed |
| Endpoint requires no authentication | ✅ | 无 auth 中间件，直接访问 |
| Unit tests cover happy path and response schema | ✅ | 5 个新测试，7/7 全部通过 |

---

## 九、验证 Checklist（手工操作）

请逐项勾选：

### GitHub 验证
- [ ] 打开 Issue #1 — 确认有 4 条 Kevin 评论，最后一条状态为 completed
- [ ] 打开 PR #2 — 确认 title、body、label 正确
- [ ] PR #2 Files Changed — 确认只有 `app.py` 和 `tests/test_app.py` 被修改
- [ ] PR #2 代码 — 确认 `/health` 实现逻辑正确

### 本地验证
- [ ] Clone target repo → checkout `kevin/issue-1` → `pytest tests/ -v` → 7 passed
- [ ] 手动调用 `/health` endpoint → 返回正确 JSON

### Kevin 状态验证
- [ ] `.kevin/runs/20260326-164333-cd7897/run.yaml` — status = completed
- [ ] 3 个 Block 状态全部 passed
- [ ] `blueprint_snapshot.yaml` 存在且内容完整
- [ ] `logs/` 下有 B1.log、B2.log、B3.log

### 评审文档对照
- [ ] §2.1 多执行后端 — B1/B2 用 claude_cli, B3 用 shell ✅
- [ ] §2.3 验证器层 — git_diff_check + command 均生效 ✅
- [ ] §2.4 状态管理 — .kevin/runs/ 文件完整 ✅
- [ ] §4.2 Issue #1 验证 — 端到端通过 ✅

---

*本文件为 Kevin Planning Agent v1.0 首次真实 E2E 运行的完整验证记录。*

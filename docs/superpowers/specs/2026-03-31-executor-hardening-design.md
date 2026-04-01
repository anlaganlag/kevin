# Executor Hardening Design Spec

**Date**: 2026-03-31
**Goal**: 确保 9 个 executor-compatible blueprint 的无头化执行链路健壮、可靠、可验证

## Scope

**IN**: Executor 执行链路加固 — load → compile → validate → execute → post-validate → 结果上报
**OUT**: Planning Agent 编排逻辑、新 blueprint 创建、GitHub webhook 触发链路

## 问题分析

### 关键 Gap

| # | 问题 | 严重度 | 位置 |
|---|------|--------|------|
| 1 | `_execute_agentic()` 160 行核心编排零直接测试 | CRITICAL | `cli.py:576-734` |
| 2 | `compile()` 抛 `ValueError`（prompt 过大）未捕获 | CRITICAL | `cli.py` → `blueprint_compiler.py` |
| 3 | validator 可能 raise 异常，不仅仅返回 `passed=False` | HIGH | `executor.py:run_post_validators` |
| 4 | `bp_planning_agent` 无生产级 guard，仅测试排除 | HIGH | `config.py` |
| 5 | dry-run + validator 行为未定义 | HIGH | `cli.py:632-655` |
| 6 | State 持久化（save_executor_logs / complete_run）无测试 | MEDIUM | `state.py` |

## 设计方案（Approach C — 混合分层）

### Phase 1: pytest 集成测试加固

#### 1.1 `test_execute_agentic.py` — 核心编排路径

直接测试 `_execute_agentic()` 函数，mock 外部依赖（worker、GitHub、Teams），验证编排逻辑。

**测试用例：**

| Case | 描述 | 预期 |
|------|------|------|
| happy_path | load → compile → worker 成功 → validators 全过 | return 0, state=completed |
| blueprint_load_fail | 不存在的 blueprint 路径 | return 1, 清晰错误信息 |
| compile_value_error | prompt 超 100KB | return 1, 不 crash |
| validation_invalid | blueprint 无 goal/criteria/steps | return 1, 友好拒绝 |
| worker_failure | worker.execute 返回失败 | return 1, state=failed |
| validator_exception | validator raise RuntimeError | return 1, 不影响状态保存 |
| validator_failed | validator 返回 passed=False | return 1, 记录失败详情 |
| dry_run | config.dry_run=True | 跳过 worker，仍验证 compile |
| non_executable_bp | bp_planning_agent | return 1, 明确说 "orchestrator, not executable" |

#### 1.2 `test_blueprint_full_pipeline.py` — 9 个真实 blueprint 集成

```python
@pytest.mark.parametrize("bp_file", ALL_EXECUTABLE_BLUEPRINTS)
def test_full_dry_pipeline(bp_file):
    """load_semantic → validate → compile_task → 检查 prompt 完整性"""
```

每个 blueprint 验证：
- `load_semantic` 成功，非空
- `validate_for_execution` 返回 `valid=True`
- `compile_task` 生成合法 WorkerTask
- prompt size 在 1-50KB 合理范围
- 必需变量（issue_number, issue_title, target_repo）都被引用

### Phase 2: `kevin validate` 命令

新增 CLI 子命令，运行时 preflight check。

```
$ kevin validate [--blueprint <id>]
```

**输出格式：**

```
Blueprint Validation Matrix
────────────────────────────────────────────────────────
Blueprint                         Load  Compile  Valid  Size
bp_coding_task.1.0.0              ✓     ✓        ✓      2.1KB
bp_backend_coding_tdd.1.0.0       ✓     ✓        ✓      3.4KB
bp_planning_agent.1.0.0           ✓     —        (orchestrator)
────────────────────────────────────────────────────────
Result: 9/10 executor-ready
```

**实现：**
- 遍历 `blueprints/` 下所有 YAML
- 对每个：`load_semantic` → `validate_for_execution` → `compile` (dry)
- 输出 matrix + 汇总
- Exit code: 0 (全部 OK) 或 1 (有失败)

### Phase 3: 生产代码加固

#### 3.1 `_execute_agentic` 异常防护

```python
# compile 异常捕获
try:
    task = compile_task(semantic, variables)
except ValueError as e:
    _err(f"Blueprint compilation failed: {e}")
    return 1

# validator 异常防护
try:
    results = run_post_validators(semantic, variables, cwd)
except Exception as e:
    logger.error(f"Validator execution error: {e}")
    results = [{"name": "validator_error", "passed": False, "error": str(e)}]
```

#### 3.2 非执行 blueprint guard

在 `config.py` 添加：

```python
NON_EXECUTABLE_BLUEPRINTS = {"bp_planning_agent.1.0.0"}
```

在 `_execute_agentic` 入口检查：

```python
if blueprint_id in NON_EXECUTABLE_BLUEPRINTS:
    _err(f"{blueprint_id} is an orchestrator blueprint, not executor-compatible")
    return 1
```

#### 3.3 dry-run 行为明确化

```python
if config.dry_run:
    # 跳过 worker 执行，但仍运行 compile + validate（验证编排）
    # 不运行 post-validators（无实际输出可验证）
    # 不做 GitHub 操作
```

### Phase 4: E2E 真实执行

#### 4.1 验证脚本

```bash
# Step 1: validate 全过
kevin validate

# Step 2: 最轻量 blueprint dry-run
kevin run --issue <test-issue> --repo <repo> --dry-run

# Step 3: 真实执行 bp_coding_task
kevin run --issue <test-issue> --repo <repo>

# Step 4: 逐步扩展到 9 个 blueprint
```

#### 4.2 E2E 验收标准

每个 blueprint 真跑必须：
- [ ] 执行完成，exit code 0
- [ ] state 文件正确写入 `.kevin/runs/`
- [ ] PR 提取成功（如适用）
- [ ] GitHub label 正确更新
- [ ] Teams 通知发送（如配置）

## 文件变更清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `kevin/tests/test_execute_agentic.py` | 新建 | 核心编排路径 9 个测试 |
| `kevin/tests/test_blueprint_full_pipeline.py` | 新建 | 9 blueprint 集成测试 |
| `kevin/cli.py` | 修改 | validate 命令 + _execute_agentic 异常防护 |
| `kevin/config.py` | 修改 | NON_EXECUTABLE_BLUEPRINTS 常量 |
| `kevin/executor.py` | 修改 | validator 异常防护 |

## 不做的事

- 不重构现有模块结构
- 不新增 runner 类型
- 不修改 blueprint YAML 内容
- 不改 GitHub Actions workflow
- 不做 Planning Agent 相关工作

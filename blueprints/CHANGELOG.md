# Blueprint 模板更新日志

## 2026-03-29 - Executor blueprint availability gaps (temporary fallbacks)

### Context
The Supabase Executor currently only has 5 blueprints deployed. Several specialist agents
in `bp_planning_agent.1.0.0.yaml` reference blueprints that exist in this repo but are
not yet deployed to the executor. As a temporary measure, those agents fall back to
`bp_coding_task.1.0.0` with a detailed `instruction` string to guide Kevin.

### Blueprints that exist here but are NOT yet on the executor

| Blueprint file | Blocks who | Temporary fallback |
|---|---|---|
| `bp_ba_requirement_analysis.1.0.0.yaml` | ba-agent | `bp_coding_task.1.0.0` + instruction_hint |
| `bp_architecture_blueprint_design.1.0.0.yaml` | architect-agent | `bp_coding_task.1.0.0` + instruction_hint |
| `bp_deployment_monitoring_automation.1.0.0.yaml` | sre-agent, platform-agent | `bp_coding_task.1.0.0` + instruction_hint |
| *(not yet created)* | security-agent | `bp_code_review.1.0.0` + instruction_hint |
| *(not yet created)* | doc-agent | `bp_coding_task.1.0.0` + instruction_hint |

### What needs to happen to revert

1. Deploy the missing blueprints to the Supabase Executor
2. In `event-driven-architecture-playground/azure-functions/src/blueprintLoader.ts`,
   update each agent's `blueprint_id` back to the proper value (search for `TODO — revert`)
3. Remove the `instruction_hint` fields for those agents (they compensate for the fallback)
4. Redeploy the CF Worker: `npx wrangler deploy`

### Blueprints already on the executor (no action needed)

| Blueprint file | Used by |
|---|---|
| `bp_coding_task.1.0.0.yaml` | builder-agent (proper), others (fallback) |
| `bp_code_review.1.0.0.yaml` | security-agent (fallback) |
| `bp_backend_coding_tdd_automation.1.0.0.yaml` | (available, not currently assigned) |
| `bp_function_implementation_fip_blueprint.1.0.0.yaml` | fip-agent ✓ |
| `bp_test_feature_comprehensive_testing.1.0.0.yaml` | qa-agent ✓ |

---

## 2026-03-29 - Planning Agent Agentic Blueprint (replaces hardcoded state machine)

### New: `blueprints/bp_planning_agent.1.0.0.yaml`

**Why**: The previous implementation encoded the Planning Agent as a hardcoded TypeScript
state machine (`planningAgent.ts`, 567 lines). Every workflow change required a code deploy.
The manager requires all agents — including the Planning Agent — to be described as blueprints,
making behavior evolvable without code changes.

**What's new**:
- Introduced `blueprint_type: "orchestrator"` — a new blueprint type distinct from
  `feature` / `implementation` blueprints used by specialists
- The Planning Agent is now **agentic**: uses Claude SDK (Opus 4.6 with extended thinking)
  to perform intent recognition and decide the next action
- Three-phase execution model: pre-check → intent recognition → agent assembly
- **Agent catalog**: full registry of specialist agents and their blueprint IDs, embedded in
  the blueprint so the LLM knows who it can dispatch and when
- **Action vocabulary**: 8 explicit actions (dispatch_agent, dispatch_parallel, post_comment,
  request_hitl, update_state, mark_complete, handle_failure, no_op)
- **Intent recognition framework**: 4-step reasoning framework for Claude (understand →
  classify → decide → act), produces structured JSON action list
- **State management contract**: 15 known states documented as LLM suggestions (not hardcoded
  transitions — LLM may adapt for novel situations)
- **Q3 decision documented**: Executor is a pure Claude runner; Azure Function executes actions

**Execution platform (Q3 — revised after reviewing Executor API)**:
- Planning Agent calls **Anthropic SDK directly** inside the Azure Function (synchronous, seconds)
- Supabase Executor is used only for **dispatching specialist agents** (async, fire-and-forget)
- Executor is an async GitHub Actions dispatcher (3-5 min, creates PRs) — incompatible with
  synchronous orchestration. Planning agent cannot run on it.
- Executor available blueprints: bp_coding_task, bp_code_review, bp_backend_coding_tdd_automation,
  bp_function_implementation_fip_blueprint, bp_test_feature_comprehensive_testing

**Related files**:
- `blueprints/planning_agent_state_machine.yaml` — preserved as reference / rough spec
- `azure-functions/src/planningAgent.ts` — to be refactored (Phase 3, pending Q2 prompt design)
- `azure-functions/src/githubWebhook.ts` — to be updated to call Executor instead of inline TS

---

## 2026-03-28 - Planning Agent Redesign: State Machine Orchestrator

### New: `blueprints/planning_agent_state_machine.yaml`

**Why**: The previous `bp_planning_agent_orchestration.1.0.0.yaml` used a linear task-blueprint
structure (sequential block list), which is fundamentally wrong for an orchestrator. The Planning
Agent is a stateless event-driven orchestrator — it does not execute tasks itself.

**What changed**:
- Introduced `planning_agent_state_machine.yaml` — a YAML state machine definition (not a block list)
- Planning Agent = central event-loop driver; dispatches BA, Architect, FIP, Builder, QA, Security, Platform, Doc, SRE
- Issue classification on `IssueCreatedEvent`: feature / bug / security / docs / infra paths
- Short-circuit paths for bugs, security, docs, infra (skip BA and/or Architect)
- State stored in GitHub issue body metadata (existing `correlation_id` pattern)
- Specialist completion signal: fenced EDA JSON `AgentCompletedEvent` comment on the issue
- HITL Gate 1: Blueprint PR merge → dispatch FIP Agent
- HITL Gate 2: Release PR merge → dispatch SRE Agent

**Related changes**:
- `agents/agent_02_planner.md` — rewritten to reflect orchestrator role
- `event-driven-architecture-playground/azure-functions/src/planningAgent.ts` — inline Azure Function implementing the state machine
- `event-driven-architecture-playground/config/agent-routing.yml` — added `IssueCreatedEvent` and `AgentCompletedEvent` routes
- `event-driven-architecture-playground/adapters/issue-comment-bus-command.ts` — added `AgentCompletedEvent` parsing
- `bp_planning_agent_orchestration.1.0.0.yaml` — deleted (was a linear block-list, wrong shape for an orchestrator)
- `.github/workflows/agent-planning.yaml` — deleted (superseded by inline Azure Function)

---

## 2026-03-27 - Planning Agent Full Lifecycle Orchestration Blueprint

### New Blueprint: bp_planning_agent_orchestration.1.0.0

**Purpose**: Master orchestration blueprint for the Planning Agent as Ralph Loop driver.

**Key design decisions**:
- Blueprint type `orchestration` introduced — distinct from single-agent types (feature/bugfix/test)
- Covers full SDLC lifecycle: RequirementApprovedEvent → Phase 1 design → HITL Gate 1 → Phase 2 cascade → Step 5b audit → HITL Gate 2 → merge to main
- Complements (does NOT replace) `bp_architecture_blueprint_design.1.0.0.yaml`
- **Context pointer model**: Planning Agent selects specific `.agentic/` paths per block; downstream agents pull their own context at execution time. Planning Agent does NOT carry or forward context content.
- **Phase 2 is Git-webhook-driven**: After Gate 1 approval (Blueprint PR merged), Builder and Platform agents start independently via Git webhooks. Planning Agent does NOT dispatch Phase 2 agents at runtime. `BlockAssignedEvent` coordination is intra-Phase-1 only.
- **HITL Gate 2 ordering corrected**: Gate 2 comes AFTER Step 5b automated governance passes — human is the final sign-off on top of an already-greenlighted system.
- Gate 1 rejection triggers rework from B3 (max 1 cycle), then escalates to human.

**New file**: `blueprints/bp_planning_agent_orchestration.1.0.0.yaml`

---

## 2026-03-26 - 配置管理和 Blueprint ID 命名规范更新

### 更新 1: 配置管理架构

**问题**: 之前 Rules 和 Constraints 都硬编码在每个 Blueprint 中，导致：
- ❌ 配置重复，难以维护
- ❌ 无法全局管理和更新
- ❌ 切面化困难

**解决方案**: 实现项目级配置管理架构

#### 新增内容

1. **配置目录结构**
```
.agentic/
├── profiles/          # 配置概要
├── rules/             # 规则定义
│   ├── naming/
│   ├── security/
│   ├── testing/
│   └── workflows/
└── constraints/       # 约束定义
    ├── infra/
    ├── devops/
    └── business/
```

2. **配置加载优先级**
```
系统默认 → 全局配置 → Profile → Blueprint → 运行时
```

3. **三种配置方式**
   - `load_from`: 引用整个目录
   - `specific`: 引用特定文件
   - `inline`: Blueprint 特定配置和覆盖

4. **创建的配置文件**
   - `.agentic/rules/naming/general.yaml` - 通用命名规范
   - `.agentic/rules/naming/go.yaml` - Go 命名规范
   - `.agentic/rules/security/owasp_top10.yaml` - OWASP 安全规则
   - `.agentic/constraints/infra/static/technical_stack.yaml` - 技术栈约束
   - `.agentic/constraints/devops/ci/quality_gates.yaml` - 质量门禁
   - `.agentic/profiles/default_profile.yaml` - 默认配置概要
   - `.agentic/profiles/strict_profile.yaml` - 严格配置概要
   - `.agentic/profiles/fast_profile.yaml` - 快速配置概要

5. **配置管理文档**
   - `CONFIG_MANAGEMENT.md` - 完整的配置管理架构说明

#### Blueprint 模板更新

新增 `configuration` 部分：

```yaml
blueprint:
  configuration:
    profile:
      name: "default_profile"

    rules:
      load_from:
        - ".agentic/rules/naming/"
        - ".agentic/rules/security/"
      inline:
        custom_rules: [...]

    constraints:
      load_from:
        - ".agentic/constraints/infra/"
      inline:
        go_version: "1.22"  # 覆盖全局配置
```

#### 优势

✅ **全局管理** - 在 `.agentic/` 目录统一管理
✅ **切面化** - 按类别组织（命名、安全、测试等）
✅ **层级覆盖** - 支持全局配置和局部覆盖
✅ **易于维护** - 集中管理，避免重复
✅ **灵活性** - 支持内联覆盖和运行时覆盖

---

## 2026-03-26 - Blueprint ID 命名规范更新

### 更新原因

之前的 Blueprint ID 使用时间戳格式（`BLUEPRINT-{timestamp}-{sequence}`），存在以下问题：
- ❌ 缺乏语义化，无法从 ID 看出 Blueprint 的用途
- ❌ 不便于分类和检索
- ❌ 不符合人类阅读习惯
- ❌ 难以进行版本管理

### 新的命名规范

采用语义化命名格式：

```
bp_{domain}_{type}_{name}.{version}
```

#### 格式说明

| 部分 | 说明 | 示例 |
|------|------|------|
| `bp_` | Blueprint 前缀 | `bp_` |
| `{domain}` | 业务域/模块 | `auth`, `frontend`, `backend` |
| `{type}` | Blueprint 类型 | `feature`, `bugfix`, `incident` |
| `{name}` | 具体功能/任务名称 | `jwt_login`, `user_profile` |
| `.{version}` | 版本号 | `1.0.0` |

### 命名示例

#### 功能开发 (Feature)
```
bp_auth_feature_jwt_authentication.1.0.0
bp_frontend_feature_user_dashboard.1.0.0
bp_backend_feature_payment_integration.1.0.0
```

#### Bug 修复 (Bug Fix)
```
bp_frontend_bugfix_login_button.1.0.0
bp_backend_bugfix_api_timeout.1.0.0
bp_auth_bugfix_token_validation.1.0.0
```

#### 事件响应 (Incident)
```
bp_incident_database_outage.1.0.0
bp_incident_payment_gateway_down.1.0.0
```

#### 重构 (Refactor)
```
bp_backend_refactor_user_service.1.0.0
bp_frontend_refactor_component_library.1.0.0
```

### 更新的文件

1. **blueprints/BP_ID_NAMING_CONVENTION.md** (新增)
   - 完整的 Blueprint ID 命名规范文档
   - 包含格式说明、示例、最佳实践
   - 提供验证规则和迁移指南

2. **blueprints/templates/blueprint_template.yaml** (更新)
   - 更新 `blueprint_id` 字段定义
   - 添加命名规范注释和示例
   - 更新 `blueprint_type` 枚举值

3. **blueprints/examples/feature_development_example.yaml** (更新)
   - 更新 Blueprint ID 为 `bp_auth_feature_jwt_authentication.1.0.0`
   - 更新所有相关引用

4. **blueprints/blocks/block_template.yaml** (更新)
   - 更新 Block ID 命名格式说明
   - 添加更多示例

5. **blueprints/README.md** (更新)
   - 添加 Blueprint ID 命名规范章节
   - 更新目录结构

### 版本号规范

遵循 [Semantic Versioning 2.0.0](https://semver.org/)：

```
MAJOR.MINOR.PATCH

MAJOR:    不兼容的 API 变更
MINOR:    向后兼容的功能新增
PATCH:    向后兼容的问题修复
```

#### 版本示例

```
bp_auth_feature_jwt_authentication.1.0.0    # 初始版本
bp_auth_feature_jwt_authentication.1.1.0    # 新增 refresh token 功能
bp_auth_feature_jwt_authentication.1.1.1    # 修复 token 过期时间 bug
bp_auth_feature_jwt_authentication.2.0.0    # 重构 API，不兼容 1.x
```

### Domain（域）分类

#### 通用域
- `frontend` - 前端相关
- `backend` - 后端相关
- `auth` - 认证授权
- `database` - 数据库相关
- `infra` - 基础设施
- `ci_cd` - CI/CD 流水线
- `monitoring` - 监控告警
- `security` - 安全相关
- `performance` - 性能优化
- `testing` - 测试相关
- `ui_ux` - UI/UX 设计
- `mobile` - 移动端
- `analytics` - 数据分析

#### 业务域（根据实际业务调整）
- `payment` - 支付相关
- `order` - 订单相关
- `user` - 用户相关
- `product` - 商品相关
- `inventory` - 库存相关
- `shipping` - 物流相关

### Type（类型）分类

| Type | 说明 | 使用场景 |
|------|------|----------|
| `feature` | 新功能开发 | 添加新功能, 新特性 |
| `bugfix` | Bug 修复 | 修复缺陷, 错误 |
| `incident` | 事件响应 | 生产事故, 紧急修复 |
| `refactor` | 重构 | 代码重构, 架构调整 |
| `infra` | 基础设施变更 | IaC, 配置变更 |
| `perf` | 性能优化 | 性能提升, 优化 |
| `security` | 安全相关 | 安全加固, 漏洞修复 |
| `test` | 测试相关 | 测试增强, 覆盖率提升 |
| `docs` | 文档更新 | API 文档, 架构文档 |
| `config` | 配置变更 | 特性开关, 环境配置 |
| `hotfix` | 紧急修复 | 关键问题紧急修复 |
| `experimental` | 实验性功能 | 实验性, 试用性功能 |
| `deps_update` | 依赖更新 | 第三方依赖更新 |

### 最佳实践

#### ✅ 好的示例

```
✅ bp_auth_feature_jwt_authentication.1.0.0
✅ bp_frontend_bugfix_login_button.1.0.0
✅ bp_backend_refactor_user_service.1.0.0
✅ bp_infra_k8s_migration.1.0.0
```

#### ❌ 不好的示例

```
❌ bp_auth_feat_jwt.1.0.0                    # 缩写不明确
❌ bp_frontend_bug_fix_login_btn.1.0.0       # 过长
❌ bp_backend_feature_do_something.1.0.0     # 不明确
❌ bp-auth-feature-jwt-authentication.1.0.0  # 使用连字符
❌ BP_AUTH_FEATURE_JWT.1.0.0                 # 使用大写
```

### 与 GitHub Issue 的关联

在 GitHub Issue 标题中使用 Blueprint ID：

```
[bp_auth_feature_jwt_authentication.1.0.0] 实现 JWT 认证系统
```

建议添加的标签：
- `blueprint`
- `{domain}`: `auth`, `frontend`, `backend` 等
- `{type}`: `feature`, `bugfix`, `incident` 等
- `version:{version}`: `version:1.0.0`

### 验证规则

使用正则表达式验证 Blueprint ID 格式：

```regex
^bp_[a-z0-9]+_(feature|bugfix|incident|refactor|infra|perf|security|test|docs|config|hotfix|experimental|deps_update)_[a-z0-9_]+\.\d+\.\d+\.\d+$
```

### 迁移指南

从旧格式迁移到新格式：

```
旧格式: BLUEPRINT-20260326-001
新格式: bp_auth_feature_jwt_authentication.1.0.0

迁移步骤:
1. 确定业务域: auth
2. 确定类型: feature
3. 确定名称: jwt_authentication
4. 分配版本: 1.0.0
```

在迁移期间，可以在 Blueprint 元数据中保留旧 ID：

```yaml
metadata:
  blueprint_id: "bp_auth_feature_jwt_authentication.1.0.0"
  legacy_id: "BLUEPRINT-20260326-001"  # 保留以便追溯
```

### 优势

使用新的命名规范可以：

✅ 提高可读性和可理解性
✅ 便于分类和检索
✅ 支持版本管理
✅ 增强可追溯性
✅ 提升团队协作效率

### 相关文档

- [完整命名规范](BP_ID_NAMING_CONVENTION.md)
- [Blueprint 模板](templates/blueprint_template.yaml)
- [使用指南](README.md)

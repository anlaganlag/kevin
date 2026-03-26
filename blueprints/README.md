# Blueprint 模板使用指南

## 概述

Blueprint 是 AgenticSDLC 中端到端的可执行计划，由可重用的 Blocks 组成。当事件触发后，系统通过 Blueprint 调用对应的 Sub-Agents 完成任务。

## Blueprint ID 命名规范

**重要**: Blueprint ID 使用语义化命名格式，遵循以下规范：

```
bp_{domain}_{type}_{name}.{version}
```

### 示例

```
# 功能开发
bp_auth_feature_jwt_authentication.1.0.0
bp_frontend_feature_user_dashboard.1.0.0
bp_backend_feature_payment_integration.1.0.0

# Bug 修复
bp_frontend_bugfix_login_button.1.0.0
bp_backend_bugfix_api_timeout.1.0.0
bp_auth_bugfix_token_validation.1.0.0

# 事件响应
bp_incident_database_outage.1.0.0
bp_incident_payment_gateway_down.1.0.0

# 重构
bp_backend_refactor_user_service.1.0.0
bp_frontend_refactor_component_library.1.0.0
```

**详细命名规范请参考**: [BP_ID_NAMING_CONVENTION.md](BP_ID_NAMING_CONVENTION.md)

## 配置管理

**重要**: Rules 和 Constraints 现在通过项目级配置管理，实现切面化和全局管理。

### 配置目录结构

```
project/
├── .agentic/                    # 配置根目录
│   ├── profiles/                # 配置概要（预设组合）
│   │   ├── default_profile.yaml
│   │   ├── strict_profile.yaml
│   │   └── fast_profile.yaml
│   │
│   ├── rules/                   # 规则定义
│   │   ├── naming/              # 命名规范
│   │   ├── security/            # 安全规则
│   │   ├── testing/             # 测试规则
│   │   └── workflows/           # 工作流规则
│   │
│   └── constraints/             # 约束定义
│       ├── infra/               # 基础设施约束
│       ├── devops/              # DevOps 约束
│       └── business/            # 业务约束
```

### 配置加载优先级

```
1. 系统默认配置 (最低优先级)
   ↓
2. 全局项目配置 (.agentic/)
   ↓
3. Profile 配置 (.agentic/profiles/)
   ↓
4. Blueprint 级别配置 (Blueprint 文件中)
   ↓
5. 运行时覆盖 (最高优先级)
```

### Blueprint 中的配置引用

```yaml
blueprint:
  metadata:
    profile: "default_profile"  # 引用 Profile

  configuration:
    # Profile 引用
    profile:
      name: "strict_profile"

    # Rules 加载
    rules:
      load_from:
        - ".agentic/rules/naming/"
        - ".agentic/rules/security/"

      inline:
        # Blueprint 特定规则
        custom_rules:
          - name: "jwt_token_expiration"
            rule: "JWT tokens must expire within 1 hour"

    # Constraints 加载
    constraints:
      load_from:
        - ".agentic/constraints/infra/"

      inline:
        # Blueprint 特定约束（覆盖全局配置）
        go_version: "1.22"  # 覆盖全局的 1.21
```

### 配置管理命令

```bash
# 查看当前生效的配置
agentic config show

# 查看配置来源
agentic config trace <rule_name>

# 测试配置
agentic config test --blueprint <blueprint_id>

# 导出配置
agentic config export --output merged_config.yaml
```

**详细配置管理请参考**: [CONFIG_MANAGEMENT.md](CONFIG_MANAGEMENT.md)

## 目录结构

```
blueprints/
├── templates/          # Blueprint 模板
│   └── blueprint_template.yaml
├── blocks/            # 可重用的 Blueprint Blocks
│   ├── block_template.yaml
│   ├── block_analysis.yaml
│   ├── block_design.yaml
│   ├── block_implementation.yaml
│   └── ...
├── examples/          # Blueprint 示例
│   ├── feature_development_example.yaml
│   ├── bug_fix_example.yaml
│   └── incident_response_example.yaml
├── BP_ID_NAMING_CONVENTION.md  # Blueprint ID 命名规范
└── README.md          # 本文档
```

## Blueprint 核心组件

### 1. 输入定义 (Input)

定义 Blueprint 的触发器和输入上下文：

```yaml
input:
  trigger:
    event_type: "IssueCreatedEvent"
    event_source: "github"
    event_schema:
      issue_id: "123"
      issue_type: "requirement"
      labels: ["feature", "auth"]

  context:
    source_documents:
      - type: "BRD"
        location: "docs/brd/auth-system.md"
```

### 2. 执行 Agent (Execution)

定义 Primary Agent 和 Sub-Agents 的协调：

```yaml
execution:
  primary_agent:
    agent_type: "BA_Agent"
    selection_logic:
      label_priority:
        - label: "security"
          primary_agent: "SecurityAgent"

  sub_agents:
    - agent_type: "PlanningAgent"
      phase: "design"
    - agent_type: "BuilderAgent"
      phase: "implementation"
```

### 3. 技能配置 (Capabilities)

定义 Agent 可用的技能和工具：

```yaml
capabilities:
  agent_skills:
    PlanningAgent:
      - "blueprint_design"
      - "task_decomposition"

  tool_access:
    - tool: "github_api"
      permissions: ["issues:read/write"]
```

### 4. 约束和依赖 (Constraints)

定义 Infra Layer 和业务规则：

```yaml
constraints:
  infra_dependency_layer:
    static_constraints:
      technical_constraints:
        language_stack: ["Go", "Python"]
        framework_versions:
          go: "1.21+"

  business_rules:
    naming_rules:
      source: "docs/naming_conventions.md"
    security_policies:
      source: "docs/security_policy.md"
```

### 5. 完成条件 (Completion)

定义验收条件和输出制品：

```yaml
completion:
  acceptance_criteria:
    functional:
      - "所有用户故事已实现"
    non_functional:
      - "测试覆盖率 ≥ 95%"

  artifacts:
    - artifact_type: "source_code"
      name: "功能实现代码"
    - artifact_type: "test_report"
      name: "测试报告"
```

### 6. 度量指标 (Metrics)

定义执行的度量标准：

```yaml
metrics:
  velocity_metrics:
    - metric_name: "requirement_to_production_time"
      target: "≤ 48h"

  quality_metrics:
    - metric_name: "test_coverage_percentage"
      target: "≥ 95%"
      threshold: "hard_gate"
```

## Blueprint 类型

### 1. 功能开发 Blueprint (Feature Development)

适用于新功能开发的标准流程：

```yaml
blueprint:
  metadata:
    blueprint_type: "feature_development"

  execution:
    primary_agent:
      agent_type: "BA_Agent"
      phase: "analysis"

    sub_agents:
      - agent_type: "PlanningAgent"
      - agent_type: "BuilderAgent"
      - agent_type: "QAAgent"
      - agent_type: "SecurityAgent"
```

### 2. Bug 修复 Blueprint (Bug Fix)

适用于缺陷修复的快速流程：

```yaml
blueprint:
  metadata:
    blueprint_type: "bug_fix"

  constraints:
    business_rules:
      bug_fix_rules:
        source: "docs/bug_fix_rules.md"
```

### 3. 事件响应 Blueprint (Incident Response)

适用于生产事故的应急响应：

```yaml
blueprint:
  metadata:
    blueprint_type: "incident_response"

  input:
    trigger:
      event_type: "IncidentDetectedEvent"
      event_source: "prometheus"

  execution:
    primary_agent:
      agent_type: "SREAgent"
```

### 4. 数据分析 Blueprint (Data Analysis)

适用于数据分析和洞察生成：

```yaml
blueprint:
  metadata:
    blueprint_type: "data_analysis"

  execution:
    primary_agent:
      agent_type: "LearningAgent"
```

## Ralph Loop 执行流程

Blueprint 遵循 Ralph Loop 5 步流程：

### Step 1: 确认 Primary Agent
基于 Issue 标签和类型选择合适的 Primary Agent

### Step 2: 加载规则和上下文
- 从 Infra Layer 加载静态和动态约束
- 从 Learning Agent 获取历史模式

### Step 3: 协调 Sub-Agents
- 解析 Blueprint Block 依赖图
- 发布事件驱动 Sub-Agent 执行
- 并行执行独立 Blocks

### Step 4: 确认完成并交付输出
- 更新 GitHub Issues
- 生成 BlueprintExecutionReport Artifact

### Step 5: 审计和治理决策
- 并行 Audit Agents 生成报告
- Governance Layer 检查所有 Gates
- 做出 Pass/Fail 决策

## Blueprint Blocks 库

Blueprint 由可重用的 Blocks 组成：

### 开发 Blocks
- `block_code_analysis`: 静态代码分析
- `block_unit_test`: 单元测试生成
- `block_code_review`: 代码审查

### 验证 Blocks
- `block_security_scan`: 安全扫描
- `block_qa_validation`: QA 验证
- `block_contract_check`: API 合约检查

### 部署 Blocks
- `block_build`: 构建制品
- `block_canary_deploy`: 金丝雀部署
- `block_rollback`: 回滚

### 文档 Blocks
- `block_api_doc`: API 文档生成
- `block_changelog`: 变更日志生成
- `block_diagram_update`: 架构图更新

## 治理 Gates

所有 Blueprint 必须通过以下硬 Gates：

### 质量 Gates
- 测试覆盖率 ≥ 95%
- Code smell 阈值
- 技术债务限制

### 安全 Gates
- 无关键漏洞
- 无高危漏洞
- 依赖扫描合规

### 合约 Gates
- API 合约合规
- Schema 兼容性
- 接口一致性

### 预算 Gates
- Token 使用 ≤ 预算
- 计算时间 ≤ 限制
- 存储成本 ≤ 阈值

## 最佳实践

1. **从模板开始**: 使用 `blueprint_template.yaml` 作为起点
2. **定义清晰的触发器**: 明确事件类型和来源
3. **选择合适的 Primary Agent**: 基于任务类型和标签
4. **声明所有约束**: 包括 Infra Layer 和业务规则
5. **定义可测量的完成条件**: 使用具体的验收标准
6. **设置合理的度量指标**: 跟踪速度、质量、效率
7. **规划风险管理**: 识别风险并定义应急处理

## 示例

查看 `blueprints/examples/` 目录获取完整示例：

- `feature_development_example.yaml`: 功能开发示例
- `bug_fix_example.yaml`: Bug 修复示例
- `incident_response_example.yaml`: 事件响应示例

## 相关文档

- [设计文档 v2.0](../design_doc.md): 完整架构说明
- [Agent 定义](../agents/): 各个 Agent 的详细说明
- [架构文档](../agentic_sdlc_architecture.md): 系统架构图

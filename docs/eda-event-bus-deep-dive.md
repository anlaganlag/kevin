# Event-Driven Architecture (EDA) Deep Dive

> AgenticSDLC 事件总线架构解析：设计原理、隐含洞察与战略价值

**Version**: 1.0.0
**Date**: 2026-03-28
**Status**: Analysis Document
**Audience**: Architects, Tech Leads, Engineering Managers

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [EDA 在五层架构中的定位](#2-eda-在五层架构中的定位)
3. [事件模型](#3-事件模型)
4. [事件路由与协调机制](#4-事件路由与协调机制)
5. [架构洞察](#5-架构洞察)
6. [Kevin v1.0 与 EDA 的映射关系](#6-kevin-v10-与-eda-的映射关系)
7. [业务价值分析](#7-业务价值分析)
8. [演进路线](#8-演进路线)
9. [Appendix: 完整事件类型参考](#9-appendix-完整事件类型参考)

---

## 1. Executive Summary

AgenticSDLC 的 Event-Driven Architecture (EDA) 是一套面向 AI Agent 协作的异步通信基础设施。它通过事件总线（Event Bus）实现了 Agent 之间的松耦合协调，使多个 AI Agent 能够像一个自组织团队一样并行工作——而非串行执行脚本。

EDA 在 AgenticSDLC 中扮演三重角色：

- **通信基础设施**：Agent 之间的唯一通信通道
- **可观测性数据源**：事件流即审计日志，支撑全链路追踪
- **治理执行面**：Governance Layer 通过订阅事件流实现实时监控

本文从架构设计、隐含洞察和业务价值三个维度，对 EDA 进行深度解析。

---

## 2. EDA 在五层架构中的定位

AgenticSDLC 采用五层 Event-Driven Architecture，EDA 位于第三层——承上启下的核心枢纽：

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 5: Governance & Audit Layer                              │
│  独立验证、策略执行、横切监控                                       │
│  ← 订阅 Layer 3 的所有事件，实时旁听                                │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4: Agent Orchestration Layer                             │
│  Ralph Loop 事件处理框架、Agent 协调                               │
│  ← 通过 Layer 3 发布/接收事件来驱动 Agent 执行                      │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: Event-Driven Architecture (EDA)            ★ 本文焦点  │
│  Event Bus、事件路由、Pub/Sub                                     │
│  ← 连接上层 Agent 与下层接口/基础设施                                │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: Standard Interfaces Layer                             │
│  Issues、Tasks、Commits、Pipelines、Artifacts                    │
│  ← 产生 Source Events 供 Layer 3 路由                             │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: Infra Dependency Layer (EEF)                          │
│  静态约束 + 动态运行时状态                                          │
│  ← 约束条件通过事件同步给上层                                       │
└─────────────────────────────────────────────────────────────────┘
```

**关键定位**：Layer 3 不做任何业务决策——它只负责**路由**。决策在 Layer 4（Agent Orchestration）和 Layer 5（Governance）中发生。

---

## 3. 事件模型

### 3.1 事件基础结构

所有事件共享统一的 Base Schema：

```yaml
Event_Base:
  event_id: "UUID"                                    # 全局唯一标识
  event_type: "BlockCompletedEvent"                   # 事件类型
  timestamp: "2026-03-28T10:05:30Z"                   # ISO 8601
  source: "github | system | agent"                   # 事件来源
  correlation_id: "uuid-for-chain-tracing"            # 事件链追踪标识
  payload:                                            # 类型特定数据
    # ...
```

其中 `correlation_id` 是全链路追踪的关键——同一条业务链路上的所有事件共享同一个 `correlation_id`，实现从 Issue 到 Deployment 的完整溯源。

### 3.2 事件分类体系

AgenticSDLC 定义了 **23 种事件类型**，分为三大类：

```
┌──────────────────────────────────────────────────────────────────┐
│                        Event Taxonomy                            │
├────────────────────┬────────────────────┬────────────────────────┤
│   Source Events    │  Internal Events   │   Decision Events      │
│   (外部系统触发)     │  (系统内部生成)      │   (治理层产生)          │
├────────────────────┼────────────────────┼────────────────────────┤
│ IssueCreatedEvent  │ BlockAssignedEvent │ GatePassedEvent        │
│ IssueUpdatedEvent  │ BlockStartedEvent  │ GateFailedEvent        │
│ IssueClosedEvent   │ BlockCompletedEvent│ EscalationRequiredEvent│
│ PipelineStarted    │ BlockFailedEvent   │                        │
│ PipelineCompleted  │ BlueprintCreated   │                        │
│ PipelineFailed     │ BlueprintStarted   │                        │
│ CommitPushedEvent  │ BlueprintCompleted │                        │
│ IncidentDetected   │ AuditRequested     │                        │
│                    │ AuditCompleted     │                        │
└────────────────────┴────────────────────┴────────────────────────┘
```

**设计原则**：

- Source Events 由 Layer 2 Standard Interfaces 产生，是系统的输入边界
- Internal Events 由 Agent 在执行过程中产生，是协调的核心
- Decision Events 由 Governance Layer 产生，是控制流的转折点

### 3.3 关键事件详解

#### CommitPushedEvent — Commit 的双重身份

Commit 在 AgenticSDLC 中不仅是代码快照，更是事件触发器：

```yaml
CommitPushedEvent:
  event_type: "CommitPushedEvent"
  payload:
    commit_sha: "abc123def456"
    repository: "owner/repo"
    branch: "feature/auth"
    author: "BuilderAgent"
    files_changed:
      - path: "src/auth/auth_service.go"
        change_type: "modified"
    message: "feat: implement JWT authentication"
    triggers:
      - pipeline: "ci-checks"          # 直接触发 CI Pipeline
      - agent_event: true               # 同时生成事件给其他 Agent
```

一次 `git push` 同时完成三件事：保存代码、触发 CI、通知其他 Agent。Git 仓库因此成为代码和工作流触发的双重 SSOT。

#### EscalationRequiredEvent — AI 自知之明的信号

```yaml
EscalationRequiredEvent:
  payload:
    trigger: "fix_loop_non_convergence"
    condition: "iteration_count > 3 AND issues_remaining > 0"
    context:
      what_was_attempted: "..."
      recommendations: "..."
    action: "halt_and_create_issue"
```

当以下任一条件满足时，系统自动产生 Escalation：

| 触发条件 | 说明 |
|---------|------|
| `budget_exceeded` | Token/计算成本超预算 |
| `fix_loop_non_convergence` | 重试 3 次以上仍未收敛 |
| `security_gate_failure` | 存在 Critical/High 级安全漏洞 |
| `agent_timeout` | Agent 执行超时 |

这不是系统故障，而是**有意设计**的人机协作边界。

---

## 4. 事件路由与协调机制

### 4.1 Pub/Sub 通信模型

```
External Triggers                    EDA System                    Agent Responses
┌──────────────────┐                ┌─────────────┐               ┌──────────────────┐
│  GitHub Issues   │──Trigger───→  │             │──Dispatch──→  │  Subscribed      │
│  Pipeline Status │    Events     │  Event Bus  │    Events     │  Agents          │
│  Monitoring      │               │             │               │                  │
│  Scheduled Jobs  │               │             │               │  - Process       │
└──────────────────┘               └─────────────┘               │  - Generate      │
                                         ▲                       │  - Publish       │
                                         │                       └──────────────────┘
                                    Governance                          │
                                    Layer 订阅                          │
                                    所有事件 ◄──────────────────────────┘
```

Agent 之间**不直接通信**。所有交互通过 Event Bus 中转，实现完全解耦。

### 4.2 Ralph Loop Step 3: 依赖图 + 事件驱动的混合协调

Ralph Loop 的第三步是 EDA 的核心应用场景——Primary Agent 解析 Blueprint 依赖图，通过事件驱动 Sub-Agent 执行：

```
┌─── Step 3 事件驱动协调流程 ───────────────────────────────────────────┐
│                                                                       │
│  1. Primary Agent 解析依赖图，识别就绪 Block: [B1] (无依赖)             │
│     └─→ 发布 BlockAssignedEvent {block: B1, assignee: PlanningAgent}  │
│                                                                       │
│  2. PlanningAgent 收到事件，自主执行                                    │
│     └─→ 完成后发布 BlockCompletedEvent {block: B1, artifact: "..."}   │
│                                                                       │
│  3. Primary Agent 收到完成事件，检查依赖图                              │
│     └─→ B2 依赖 B1 → B1 完成 → B2 就绪                                │
│     └─→ 发布 BlockAssignedEvent {block: B2, assignee: BuilderAgent}   │
│                                                                       │
│  4. B2 完成后，B3 和 B4 的依赖同时满足                                  │
│     └─→ 同时发布 BlockAssignedEvent:B3 和 BlockAssignedEvent:B4       │
│     └─→ QAAgent 和 SecurityAgent 并行执行                              │
│                                                                       │
│  5. B3 和 B4 都完成后，B5 的依赖满足                                    │
│     └─→ 发布 BlockAssignedEvent:B5                                    │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### 4.3 并行执行模型

EDA 使 Agent 并行执行成为可能。当依赖图中存在独立分支时，多个 Block 可同时调度：

```yaml
dependency_graph:
  B1: requirement_analysis     (dependencies: [])
  B2: architecture_design      (dependencies: [B1])
  B3: implementation           (dependencies: [B2])
  B4: testing                  (dependencies: [B3])     # B4 和 B5 都只依赖 B3
  B5: security_scan            (dependencies: [B3])     # → 可以并行
  B6: deployment               (dependencies: [B4, B5]) # → 等两个都完成

execution_order: "B1 → B2 → B3 → (B4 ∥ B5) → B6"
```

```
时间轴:
  B1 ████
  B2      ████████
  B3               ████████████
  B4                            ████████          ← 并行
  B5                            ██████████        ← 并行
  B6                                       ████
                                          ↑
                               两个 CompletedEvent 都收到后触发
```

**对比**：传统串行执行的总时间 = 各步之和；事件驱动并行执行的总时间 = 关键路径长度。

---

## 5. 架构洞察

### 5.1 Event ≠ Issue：两个世界的刻意分离

设计中反复强调 Event 和 Issue 是独立实体。这个区分是架构的灵魂：

| 维度 | Issue (外部实体) | Event (内部实体) |
|------|-----------------|-----------------|
| **受众** | 人类 | Agent |
| **载体** | GitHub Issues | Event Bus |
| **粒度** | 一个 Issue 可触发多个 Events | 一个 Event 只做一件事 |
| **生命周期** | 天/周级 | 秒/分级 |
| **用途** | 人类跟踪进度 | Agent 协调执行 |

**不做此分离的后果**：

1. Agent 交互通信被迫经由 GitHub API（慢、有 rate limit）
2. 单个 Issue 被几十条 Agent 交互评论淹没，人类无法使用
3. 无法支持 Pipeline 事件、监控告警等非 Issue 触发源
4. 人类的工作空间和 Agent 的工作空间互相污染

**本质价值**：人类在 Issue 层面思考"做什么"，Agent 在 Event 层面协作"怎么做"——两个世界通过 Blueprint 连接但不互相干扰。

### 5.2 Correlation ID：全链路可观测性的基石

`correlation_id` 字段的一行定义，撑起了整个系统的可审计性：

```
IssueCreatedEvent ─────────────────── correlation_id: abc-123
    └→ BlueprintStartedEvent ──────── correlation_id: abc-123
        └→ BlockAssignedEvent:B1 ──── correlation_id: abc-123
            └→ BlockCompletedEvent:B1  correlation_id: abc-123
                └→ BlockAssignedEvent:B2  correlation_id: abc-123
                    └→ CommitPushedEvent  correlation_id: abc-123
                        └→ PipelineStartedEvent  correlation_id: abc-123
                            └→ PipelineCompletedEvent  correlation_id: abc-123
                                └→ BlockCompletedEvent:B2  correlation_id: abc-123
                                    └→ AuditCompletedEvent  correlation_id: abc-123
                                        └→ GatePassedEvent  correlation_id: abc-123
```

一条 `correlation_id` 即可实现：

- **事后审计**：一个 PR 从 Issue 到合并的完整决策链
- **根因分析**：从哪个 Event 节点开始偏离预期
- **成本归因**：一个需求消耗了多少 Agent 运算和 Token

在传统 SDLC 中，这些信息散落在 Jira、Git log、CI log、Slack 中——几乎不可能还原一个需求的完整生命链。

### 5.3 Governance 通过事件流实现横切监控

Governance Layer 的"横切"机制并非抽象概念——它通过**订阅 Event Bus 上的所有事件**来实现实时旁听：

```
                    ┌──────────────────────────┐
                    │   Governance Layer        │
                    │   订阅: *Event            │
                    │   角色: 旁听 + 决策        │
                    └──────────┬───────────────┘
                               │ 订阅所有事件
                               │
Agent A ──→  📬 Event Bus  ───┼───→ Agent B
Agent C ──→                 ───┼───→ Agent D
                               │
                    看到一切，但不阻塞执行流
```

| 观测到的事件 | Governance 的检查动作 |
|-------------|---------------------|
| `BlockAssignedEvent` | 验证 Agent 权限是否足够 |
| `CommitPushedEvent` | 检查代码是否符合安全策略 |
| `BlockCompletedEvent` | 验证产出物是否合规 |
| `PipelineFailedEvent` | 评估是否需要人类介入 |
| `AuditCompletedEvent` | 执行最终门禁决策 |

**关键设计约束**：Governance 订阅事件但不阻塞事件流。它的决策通过 Decision Events（`GatePassedEvent` / `GateFailedEvent`）独立发布。

### 5.4 EscalationRequiredEvent：渐进式自治的实现

`EscalationRequiredEvent` 是系统从自动模式切换到人工模式的协议：

```
正常路径:   Event → Agent 处理 → CompletedEvent → 继续
异常路径:   Event → Agent 重试 N 次 → EscalationRequiredEvent → 创建 Issue → 人类介入
恢复路径:   人类解决 → IssueUpdatedEvent → Agent 恢复执行
```

这意味着系统的自治边界不是固定的——它是一个**可动态调整的滑动窗口**：

- 今天：Agent 在并发竞态条件场景需要人类介入
- 明天：Learning Agent 学习到处理模式，同类场景自动处理
- 自治范围随着事件数据的积累逐步扩大

---

## 6. Kevin v1.0 与 EDA 的映射关系

Kevin v1.0 **没有实现 Event Bus**，但它的代码结构为 EDA 预留了升级路径。以下是当前实现与目标 EDA 的对照：

| EDA 概念 | Kevin v1.0 的简化替代 | 目标 EDA 实现 |
|---------|---------------------|-------------|
| Event Bus | `_execute_blocks()` for 循环 | Kafka / GitHub Events API |
| `BlockAssignedEvent` | 直接调用 `run_block()` | Event Bus 发布 |
| `BlockCompletedEvent` | `result.success == True` | Agent 发布完成事件 |
| Correlation ID | `run_id` | `correlation_id` 字段 |
| State Store | `.kevin/runs/*.yaml` | 事件溯源 (Event Sourcing) |
| 并行执行 | 串行 for 循环 | 事件驱动的并行调度 |
| Governance 订阅 | Validator 后置检查 | 实时事件流订阅 |
| `EscalationRequiredEvent` | `break` + `state = "failed"` | 正式 Escalation 事件 |

### 6.1 关键代码对照

**当前**（Kevin v1.0 — 直接调用）：

```python
# kevin/cli.py: _execute_blocks()
for block in blocks:
    result = run_block(block, variables)    # 同步、串行
    if result.success:
        mark_passed(block)
    else:
        mark_failed(block)
        break                               # 失败即停止
```

**目标**（EDA 驱动 — 事件调度）：

```python
# 未来的事件驱动实现（伪代码）
event_bus.publish(BlockAssignedEvent(block_id="B1", assignee="BuilderAgent"))

@event_bus.subscribe(BlockCompletedEvent)
def on_block_completed(event):
    next_blocks = dependency_graph.get_ready_blocks(event.block_id)
    for block in next_blocks:
        event_bus.publish(BlockAssignedEvent(block_id=block.id))  # 可能多个并行
```

### 6.2 Kevin 已具备的 EDA 基础

尽管 Kevin 没有 Event Bus，但以下设计决策使未来迁移成本较低：

1. **拓扑排序（Kahn's Algorithm）** — 依赖图已正确解析，支持识别可并行的 Block
2. **Block 独立性** — 每个 Block 的执行是独立的 `run_block()` 调用，无共享状态
3. **文件系统状态持久化** — 状态可从 YAML 恢复，天然支持断点续传
4. **Blueprint 快照不可变性** — 每次运行冻结一份图纸副本，支持事件回放

---

## 7. 业务价值分析

### 7.1 工程效率

| 维度 | 无 EDA | 有 EDA |
|------|--------|--------|
| **交付速度** | Agent 串行执行，总时间 = 各步之和 | Agent 并行执行，总时间 = 关键路径 |
| **可观测性** | 跨 5+ 系统手动拼凑需求历史 | 一条 correlation_id 串起全链路 |
| **故障恢复** | 从头重跑整个流程 | 从失败的 Event 节点断点续传 |
| **系统扩展** | 加新 Agent 需修改现有 Agent 代码 | 加新 Agent 只需订阅相关 Event |
| **调试效率** | 日志散落在各个 Agent 内部 | 事件流提供统一的时序视图 |

### 7.2 治理与合规

| 维度 | 无 EDA | 有 EDA |
|------|--------|--------|
| **审计追踪** | 事后手动整理证据 | 事件流即审计日志 |
| **安全监控** | 安全检查是末端手动门禁 | SecurityAgent 实时订阅所有代码变更事件 |
| **成本控制** | 事后核算 | 实时监控 Token/Compute 消耗 |
| **合规证明** | 人工出具报告 | 事件链自动生成合规证据 |

### 7.3 人机协作

| 维度 | 无 EDA | 有 EDA |
|------|--------|--------|
| **协作模式** | 全自动 or 全手动，二选一 | 渐进式自治，EscalationEvent 动态切换 |
| **人类介入点** | 固定的门禁检查点 | 任意 Event 节点均可触发人类介入 |
| **自治演进** | 自治范围固定 | Learning Agent 消费事件流，逐步扩大自治边界 |

### 7.4 量化影响估算

以一个中等复杂度的 Feature 开发为例（6 Blocks）：

```
串行执行:  B1(2m) + B2(5m) + B3(10m) + B4(5m) + B5(5m) + B6(2m) = 29 min
并行执行:  B1(2m) + B2(5m) + B3(10m) + max(B4,B5)(5m) + B6(2m) = 24 min
                                                                    ↑ 节省 17%

多 Blueprint 并发:
  团队同时跑 3 个 Blueprint，每个 Blueprint 内部并行
  → Agent 利用率从 ~30%（串行等待）提升到 ~80%（事件驱动并行）
```

---

## 8. 演进路线

```
Phase 1 (当前: Kevin v1.0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ 串行 Block 执行
  ✅ 文件系统状态管理 (.kevin/runs/)
  ✅ run_id 作为简化版 correlation_id
  ✅ Validator 后置检查代替 Governance 订阅
  ✅ break 代替 EscalationRequiredEvent
  ❌ 无 Event Bus
  ❌ 无并行执行
  ❌ 无实时 Governance 监控

Phase 2 (目标: Kevin v2.0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  → 引入轻量 Event Bus（GitHub Events API 或进程内 Pub/Sub）
  → 事件驱动的并行 Block 调度
  → 正式的 correlation_id 事件链追踪
  → Governance Agent 订阅事件流
  → 结构化 EscalationRequiredEvent

Phase 3 (远期: Full AgenticSDLC)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  → 生产级 Event Bus（Kafka / AWS EventBridge）
  → 11 Agent 全量事件驱动协作
  → Learning Agent 消费事件流做模式学习
  → 跨仓库事件编排
  → 事件溯源（Event Sourcing）支撑完整回放
  → 实时 Dashboard 基于事件流（替代文件轮询）
```

### 8.1 技术选型建议

| 阶段 | Event Bus 选型 | 理由 |
|------|---------------|------|
| Phase 2 | GitHub Events API + 进程内队列 | 零额外基础设施，与现有 `gh` CLI 集成 |
| Phase 3 初期 | AWS EventBridge / Google Pub/Sub | 托管服务，无需运维 Kafka 集群 |
| Phase 3 成熟期 | Apache Kafka | 高吞吐、持久化、支持事件回放 |

---

## 9. Appendix: 完整事件类型参考

### Source Events (外部系统触发)

| 事件类型 | 触发源 | 典型消费者 |
|---------|--------|-----------|
| `IssueCreatedEvent` | GitHub | PlannerAgent → 启动 Ralph Loop |
| `IssueUpdatedEvent` | GitHub | Primary Agent → 更新上下文 |
| `IssueClosedEvent` | GitHub | PM Agent → 更新项目状态 |
| `PipelineStartedEvent` | CI/CD | SRE Agent → 监控执行 |
| `PipelineCompletedEvent` | CI/CD | Primary Agent → 触发下一阶段 |
| `PipelineFailedEvent` | CI/CD | Builder Agent → 修复构建 |
| `CommitPushedEvent` | Git | SecurityAgent, QAAgent → 自动扫描 |
| `IncidentDetectedEvent` | Monitoring | SRE Agent → 启动事件响应 |

### Internal Events (系统内部生成)

| 事件类型 | 生产者 | 典型消费者 |
|---------|--------|-----------|
| `BlueprintCreatedEvent` | PlanningAgent | Human → HITL Gate 1 审批 |
| `BlueprintStartedEvent` | Orchestrator | Governance → 开始监控 |
| `BlueprintCompletedEvent` | Orchestrator | PM Agent → 汇报完成 |
| `BlockAssignedEvent` | Primary Agent | 指定的 Sub-Agent |
| `BlockStartedEvent` | Sub-Agent | Governance → 执行监控 |
| `BlockCompletedEvent` | Sub-Agent | Primary Agent → 调度下一 Block |
| `BlockFailedEvent` | Sub-Agent | Primary Agent → 重试或升级 |
| `AuditRequestedEvent` | Orchestrator | Audit Agents → 开始审计 |
| `AuditCompletedEvent` | Audit Agent | Governance → 执行门禁决策 |

### Decision Events (治理层产生)

| 事件类型 | 生产者 | 语义 |
|---------|--------|------|
| `GatePassedEvent` | Governance | 门禁通过，允许继续 |
| `GateFailedEvent` | Governance | 门禁失败，阻止继续 |
| `EscalationRequiredEvent` | System / Governance | 需要人类介入 |

---

> **Document End**
>
> This document is part of the AgenticSDLC project.
> For implementation details, see `kevin/` source code.
> For architecture overview, see `design_doc.md`.

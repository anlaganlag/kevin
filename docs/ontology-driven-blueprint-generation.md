# Ontology-Driven Blueprint Generation: 深度分析与架构设计

> **Date**: 2026-03-29
> **Context**: UPS / 物流行业，BA Agent + 业务方共创 Ontology，连接 Executor 实现全自动交付
> **Status**: 战略设计文档

---

## 1. 全景：你在建什么

```
┌──────────────────────────────────────────────────────────┐
│                      知识飞轮                              │
│                                                          │
│   预置知识底座                                              │
│   (UPS API 规范、物流行业标准、集成模式)                      │
│           +                                              │
│   业务方共创                                               │
│   (具体场景、约束、系统对接细节)                              │
│           ↓                                              │
│   BA Agent → Ontology (UPS ↔ 客户集成全景)                 │
│           ↓                                              │
│   Blueprint Generator (Ontology → 可执行蓝图)              │
│           ↓                                              │
│   Executor (蓝图 → PR/部署/文档)                           │
│           ↓                                              │
│   交付物 → 反馈 → Ontology 持续丰富                        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

表面看，这是一个"AI 写代码"的系统。

**实际上，这是一个把企业集成知识资产化、然后让知识自动执行的平台。**

---

## 2. 为什么这件事在物流行业特别值钱

### 2.1 物流集成的独特复杂度

物流行业不是"一个系统"，而是 **多方系统的协作网络**：

```
电商平台 ←→ UPS API ←→ UPS 内部系统 ←→ 仓储系统 ←→ 末端配送 ←→ 客户系统
    │                                                           │
    └── 每个箭头都是一个集成点，每个集成点都有：                      │
        - 数据格式要求                                            │
        - 业务规则约束                                            │
        - 错误处理规范                                            │
        - SLA 要求                                               │
        - 合规要求 (海关、危险品、跨境)                             │
        └───────────────────────────────────────────────────────┘
```

**一个"对接 UPS 退货 API"的需求，背后涉及：**

| 层面 | 隐藏的复杂度 |
|------|------------|
| API 对接 | UPS Returns API 版本、认证方式、速率限制 |
| 业务规则 | 退货窗口期、不同商品类别的退货策略、退款规则 |
| 数据映射 | 客户 SKU → UPS 包裹类型、客户地址格式 → UPS 地址标准 |
| 异常处理 | 地址校验失败、包裹超尺寸、危险品标识 |
| 合规 | 跨境退货海关申报、不同国家退货法规 |
| 下游联动 | 退货触发库存更新 → 仓储系统 → 财务系统退款 |

**这些知识散落在 UPS 文档、客户经理的脑子里、历史工单里、以及无数次踩坑的经验中。**

没有人系统地把这些知识结构化过。BA Agent + Ontology 做的就是这件事。

### 2.2 市场空白

| 现有工具 | 能做什么 | 不能做什么 |
|---------|---------|-----------|
| UPS Developer Kit | 提供 API 文档 | 不知道客户的系统长什么样 |
| MuleSoft / Dell Boomi | 集成平台，拖拽连接器 | 不知道 UPS 的业务规则 |
| Devin / Cursor | 能写代码 | 不知道 UPS API 的 edge case |
| 咨询公司 | 出方案文档 | 不能自动执行 |

**你的位置：唯一同时拥有 UPS 一线知识 + 自动执行能力的系统。**

---

## 3. Ontology 架构：三层 + 两个视角

### 3.1 三层模型

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: 业务概念层 (What)                               │
│                                                         │
│  [包裹] --contains--> [商品]                              │
│  [商品] --has--> [危险品等级]                               │
│  [退货] --triggers--> [退款]                               │
│  [退货] --requires--> [退货标签]                            │
│  [客户] --subscribes--> [服务等级: Ground/Express/Freight]  │
│                                                         │
│  每个节点携带:                                             │
│    - 业务规则 (退货窗口 30 天)                              │
│    - 数据约束 (重量上限 150lbs)                             │
│    - 合规标记 (跨境需海关申报)                              │
└────────────────────┬────────────────────────────────────┘
                     │ maps_to
┌────────────────────▼────────────────────────────────────┐
│  Layer 2: 系统层 (Where)                                  │
│                                                         │
│  UPS 侧:                                                │
│    [Returns API v2] --endpoint--> /returns/labels        │
│    [Tracking API] --webhook--> status_update             │
│    [Address Validation API] --validates--> [地址]         │
│    [Billing System] --calculates--> [运费]               │
│                                                         │
│  客户侧:                                                │
│    [电商平台] --tech: Shopify/自建                         │
│    [WMS] --tech: Manhattan/自建                           │
│    [ERP] --tech: SAP/Oracle                               │
│                                                         │
│  集成点:                                                  │
│    [电商平台] --calls--> [Returns API v2]                 │
│    [Returns API v2] --notifies--> [WMS]                  │
│    [WMS] --updates--> [ERP]                              │
│                                                         │
│  每个系统节点携带:                                         │
│    - 技术栈 (Java/Python/SAP ABAP)                       │
│    - Repo 地址 (github.com/org/repo)                     │
│    - Owner (团队/联系人)                                   │
│    - 约束 (变更审批要求、部署窗口)                          │
│    - API 规范版本                                         │
└────────────────────┬────────────────────────────────────┘
                     │ governed_by
┌────────────────────▼────────────────────────────────────┐
│  Layer 3: 流程层 (How)                                    │
│                                                         │
│  标准集成流程:                                             │
│    需求分析 → API 对接开发 → 数据映射 → 联调测试 →          │
│    UAT → 安全审查 → 灰度上线 → 监控                       │
│                                                         │
│  按风险等级分叉:                                           │
│    低 (改配置): 开发 → 测试 → 上线                         │
│    中 (改API对接): 开发 → 联调 → UAT → 上线               │
│    高 (改核心逻辑): 全流程 + 安全审查 + 双人审批            │
│                                                         │
│  企业特有流程:                                             │
│    UPS: 涉及计费系统变更 → 必须财务审批                     │
│    UPS: 涉及跨境 → 必须合规审查                            │
│    客户: 可能有自己的 change management 流程               │
└─────────────────────────────────────────────────────────┘
```

### 3.2 两个视角

同一个 ontology，两个视角看：

**UPS 视角**（向内看）：

```
我的 API 有哪些 → 每个 API 的规范是什么 → 业务规则是什么 →
调用约束是什么 → 常见错误和处理方式
```

**客户视角**（向外看）：

```
我的系统是什么 → 我要对接 UPS 哪些能力 →
数据怎么映射 → 我的约束是什么（部署窗口、技术栈、审批流）
```

**Ontology 的核心价值是把这两个视角连起来：**

```
客户的 [Shopify 订单]
    → 映射为 UPS 的 [Shipment Request]
    → 需要调 [Shipping API v3]
    → 必须先调 [Address Validation API]
    → 如果跨境 → 还需要 [Customs API]
    → 客户的 Shopify 技术栈 → 用 Node.js SDK
    → UPS 侧要求 OAuth2 认证
    → 这个客户是 Express 服务等级 → 有 SLA 约束
```

**这条链路，UPS 文档里没有，客户自己也理不清楚。只有你的 ontology 里有完整的端到端映射。**

---

## 4. 从 Ontology 到 Blueprint：自动生成引擎

### 4.1 生成过程

```
输入:
  - 用户需求 (自然语言): "我们的 Shopify 店铺要对接 UPS 退货"
  - Ontology (图谱 + 文档)
  - 预置 Blueprint 模式库

处理:
  Step 1: 实体识别与链接
  Step 2: 影响范围分析
  Step 3: 约束收集
  Step 4: 流程匹配
  Step 5: Blueprint 组装

输出:
  - 完整的 Blueprint YAML
  - 人类可读的执行计划说明
```

### 4.2 Step 1: 实体识别与链接

Claude + Ontology 配合：

```
用户说: "我们的 Shopify 店铺要对接 UPS 退货"

实体识别:
  "Shopify" → 系统层: [电商平台, tech=Shopify]
  "UPS 退货" → 业务概念层: [退货]
              → 系统层: [Returns API v2]

链接扩展 (从 ontology 图谱自动遍历):
  [退货] --requires--> [退货标签] --generated_by--> [Returns API v2]
  [退货] --triggers--> [退款] --processed_by--> [Billing System]
  [退货] --updates--> [库存] --lives_in--> [WMS]
  [Returns API v2] --requires--> [Address Validation API] (前置依赖)
  [Shopify] --connects_via--> [Webhook] (技术模式)
```

### 4.3 Step 2: 影响范围分析

从链接结果自动推导：

```
直接影响:
  ✦ Shopify 侧: 需要新增退货发起流程 + webhook 接收
  ✦ UPS Returns API: 需要对接 label 生成 + status tracking

间接影响 (从 ontology 关系链自动发现):
  ✦ Address Validation: 退货地址需要校验 (Returns API 前置依赖)
  ✦ WMS: 退货入库需要通知仓储系统
  ✦ Billing: 退款需要触发计费系统

风险标记 (从 ontology 约束属性自动提取):
  ⚠ 涉及 Billing System → 需要财务审批
  ⚠ 如有跨境退货 → 需要合规审查
  ⚠ Returns API v2 速率限制: 100 req/min
```

### 4.4 Step 3: 约束收集

从 ontology 各层自动聚合：

```yaml
constraints:
  business_rules:
    - 退货窗口: 30 天
    - 不可退商品类别: [危险品, 定制品]
    - 退货运费策略: 卖家承担(Express), 买家承担(Ground)

  technical_constraints:
    - Shopify: webhook 必须在 5s 内返回 200
    - Returns API: OAuth2 认证, sandbox 环境可用
    - 速率限制: 100 req/min (需要排队机制)

  compliance:
    - 跨境退货: 海关申报 (CN22/CN23)
    - PII: 退货地址含个人信息, 需脱敏存储

  process_constraints:
    - 涉及 Billing → 财务审批 (张三/李四)
    - 核心系统变更 → 双人 code review
    - 部署窗口: 周二/周四 10:00-14:00 UTC
```

### 4.5 Step 4: 流程匹配

根据影响范围和约束，从流程层匹配：

```
涉及 Billing System (核心) → 风险等级: 高
高风险流程:
  需求分析 → API 对接 → 数据映射 → 联调 → UAT → 安全审查 → 财务审批 → 灰度上线 → 监控
```

### 4.6 Step 5: Blueprint 组装

```yaml
blueprint:
  metadata:
    generated_from: ontology
    requirement: "Shopify 店铺对接 UPS 退货"
    risk_level: high
    affected_systems: ["Shopify", "Returns API v2", "Address Validation", "WMS", "Billing"]
    constraints_applied: 12
    estimated_steps: 8

  blocks:
    - block_id: B1
      name: "需求分析与数据映射"
      runner: claude_cli
      prompt_template: |
        分析 Shopify 退货 → UPS Returns 的数据映射:

        Shopify 退货数据结构:
        {{shopify_return_schema}}      # 从 ontology 客户系统层注入

        UPS Returns API 请求格式:
        {{ups_returns_api_schema}}     # 从 ontology UPS 系统层注入

        业务规则:
        {{business_rules}}             # 从 ontology 业务概念层注入

        产出: .kevin/data-mapping.md

    - block_id: B2
      name: "地址校验集成"          # ← ontology 发现的前置依赖
      dependencies: [B1]
      runner: claude_cli
      context:
        repo: "{{customer_repo}}"    # 从 ontology 客户系统节点获取
        tech: "Node.js"             # 从 ontology 技术栈属性获取
        api_docs: "{{address_validation_api_docs}}"  # 从 ontology 注入
      prompt_template: |
        实现 UPS Address Validation API 集成:
        - 使用 {{tech}} SDK
        - 退货地址在创建退货标签前必须校验
        - 处理校验失败: 提示用户修正
        - 速率限制: {{rate_limit}}

    - block_id: B3
      name: "退货 API 对接"
      dependencies: [B2]            # 地址校验是前置
      runner: claude_cli
      context:
        repo: "{{customer_repo}}"
        api_version: "v2"
        auth: "OAuth2"              # 从 ontology 获取
      prompt_template: |
        实现 UPS Returns API v2 集成:
        - 创建退货标签 (POST /returns/labels)
        - 接收状态更新 (Webhook)
        - 业务规则: {{return_business_rules}}
        - 错误处理: {{known_error_patterns}}  # 从 ontology 的历史经验注入
        - PII 脱敏: 退货地址存储时脱敏

    - block_id: B4
      name: "WMS 库存同步"          # ← ontology 发现的间接影响
      dependencies: [B3]
      runner: claude_cli
      context:
        repo: "{{wms_repo}}"
        tech: "{{wms_tech}}"
      prompt_template: |
        退货入库时通知 WMS:
        - 触发时机: UPS status = "delivered_to_warehouse"
        - 数据: SKU, 数量, 退货原因
        - 接口: {{wms_inbound_api}}  # 从 ontology 获取

    - block_id: B5
      name: "联调测试"
      dependencies: [B3, B4]
      runner: claude_cli
      prompt_template: |
        编写端到端集成测试:
        - Shopify 发起退货 → 地址校验 → 创建标签 → 状态更新 → WMS 入库
        - 使用 UPS sandbox 环境: {{sandbox_config}}
        - 测试异常场景: 地址无效, 超尺寸, 跨境

    - block_id: B6
      name: "安全审查"              # ← 高风险流程要求
      dependencies: [B5]
      runner: claude_cli
      prompt_template: |
        安全审查清单:
        - OAuth2 token 安全存储 (不可 hardcode)
        - PII 字段处理 (地址脱敏)
        - API Key 轮换策略
        - Webhook 签名校验
        - 速率限制遵从

    - block_id: B7
      name: "财务审批通知"          # ← ontology: 涉及 Billing → 需财务审批
      dependencies: [B5]
      runner: api_call
      runner_config:
        method: POST
        url: "{{approval_system_url}}"
        body:
          type: "billing_change_approval"
          description: "退货功能涉及 Billing System 集成"
          approvers: ["{{finance_approver_1}}", "{{finance_approver_2}}"]

    - block_id: B8
      name: "创建 PR 与部署"
      dependencies: [B6, B7]       # 安全审查 + 财务审批都通过后
      runner: shell
      runner_config:
        command: |
          # 部署窗口检查 (从 ontology: 周二/周四 10:00-14:00 UTC)
          # 灰度策略: 10% → 50% → 100%
          gh pr create --title "feat: UPS Returns integration for {{customer_name}}"
```

**关键点：这个 Blueprint 的每一行都来自 ontology，不是通用模板。** B2（地址校验）是因为 ontology 知道 Returns API 依赖 Address Validation。B4（WMS 同步）是因为 ontology 知道退货会影响库存。B7（财务审批）是因为 ontology 知道涉及 Billing 必须财务审批。

---

## 5. Hidden Insights

### 5.1 Ontology 是真正的产品，不是 Executor

```
Executor = 引擎 (谁都能造)
Ontology = 地图 (只有走过路的人才画得出)
Blueprint = 导航路线 (地图 + 目的地自动生成)
```

Devin 有引擎但没地图。它能写代码，但不知道 UPS Returns API v2 在地址校验失败时应该返回什么错误码，不知道涉及 Billing 要找谁审批，不知道部署窗口是周二周四。

**你卖的不是"AI 写代码"，你卖的是"UPS 集成知识 + 自动执行"。**

### 5.2 BA Agent 是数据飞轮的入口

```
客户 1 对接退货 → ontology 增加退货知识
客户 2 对接退货 → ontology 已有退货知识 → 更快交付 →
                  同时补充了客户 2 特有的约束
客户 3 对接退货 → 几乎自动生成 Blueprint →
                  分钟级交付（vs 之前周级）
```

**每个客户的接入都在丰富 ontology。** 第 10 个客户对接退货时，ontology 里已经有 9 个客户踩过的坑、所有 edge case、所有数据映射变体。

这就是网络效应。**但不是用户数量的网络效应，是知识密度的网络效应。**

### 5.3 隐藏的定价权

传统模式：
```
咨询公司报价: "UPS 退货集成 → 需求分析 2 周 + 开发 4 周 + 测试 2 周 = $150K"
```

你的模式：
```
Ontology 已有退货知识 → Blueprint 自动生成 →
Executor 执行 → 2 小时出 PR → 人工 review → 上线

成本: 几美元的 API 调用
定价: $50K (仍然是咨询公司的 1/3)
利润率: >95%
```

**知识一旦进入 ontology，边际成本趋近于零。但每次交付的价值仍然是完整的集成方案。**

### 5.4 Ontology 是合规的天然载体

物流行业的合规要求（海关、危险品、GDPR、跨境数据）极其复杂。

```
审计员问: "为什么退货流程没有海关申报步骤？"

回答 (传统): "呃...开发可能漏了？"

回答 (Ontology-driven):
  "因为 ontology 中 [退货] 节点的 scope=domestic，
   不触发 [跨境] 标记，因此流程层未匹配海关申报步骤。
   如果是跨境退货，ontology 会自动激活 compliance 约束，
   Blueprint 会包含 CN22/CN23 申报步骤。
   这是 Blueprint 生成日志: [链接]"
```

**每个决策都可以追溯到 ontology 中的哪个节点、哪条规则。** 这不是额外做的"审计功能"，而是 ontology-driven 架构的天然属性。

### 5.5 竞争对手无法复制的原因

要复制你的系统，竞争对手需要：

| 需要什么 | 难度 | 时间 |
|---------|------|------|
| 建一个 Executor | 容易 | 1 周 |
| 建一个 BA Agent | 中等 | 1 月 |
| 获得 UPS API 规范知识 | 困难 — 需要实际对接经验 | 6 月 |
| 积累 edge case 和踩坑经验 | 极难 — 需要真实客户项目 | 1-2 年 |
| 建立完整的 UPS ↔ 客户 ontology | 几乎不可能 — 需要大量一线项目 | 3+ 年 |

**时间是最好的壁垒。你每多做一个客户，ontology 就更厚一层，竞争对手就更追不上。**

### 5.6 Blueprint 模式库：隐藏的第二产品

当 ontology 积累到一定程度，你会发现：

```
退货集成 Blueprint (已验证 9 次, 3 个变体)
发货集成 Blueprint (已验证 15 次, 5 个变体)
追踪集成 Blueprint (已验证 20 次, 2 个变体)
计费对接 Blueprint (已验证 7 次, 4 个变体)
```

这些经过验证的 Blueprint 模式本身就是产品：
- 可以卖给 UPS 的合作伙伴
- 可以开放给第三方集成商
- 可以作为 UPS 官方推荐的集成方式

**从"帮客户做集成" 变成 "定义集成该怎么做"。** 这是从服务商到标准制定者的跃迁。

### 5.7 扩展到其他物流商：横向复制

```
UPS Ontology (已建):
  退货、发货、追踪、计费、仓储、跨境...

FedEx Ontology (待建):
  退货、发货、追踪、计费、仓储、跨境...
  └── 70% 的业务概念层可复用（物流行业通用）
  └── 30% 需要重建（FedEx 特有 API、规则）

DHL Ontology (待建):
  └── 同样 70% 复用
```

**业务概念层是行业通用的。** "退货"的业务逻辑在 UPS 和 FedEx 大同小异。差异在系统层（API 不同）和流程层（审批流不同）。

这意味着扩展到第二个物流商的成本远低于第一个。

### 5.8 最被低估的价值：错误预防

Ontology 最大的价值不是"自动生成 Blueprint"，而是 **知道哪些事情不能做、哪些事情容易出错**。

```
用户说: "直接把 Shopify 订单数据同步到 UPS"

没有 ontology 的 AI: "好的，我来写一个同步脚本..."

有 ontology 的 AI:
  "⚠ 注意: ontology 显示 Shopify 订单数据包含 PII (客户地址)，
   直接同步违反 GDPR。历史记录显示客户 X 在 2025-Q3
   因为类似操作被审计发现问题。

   建议: 先经过数据脱敏层 (ontology 中已有标准方案)，
   然后再同步到 UPS。是否按此方案生成 Blueprint？"
```

**Ontology 不只是知道"怎么做"，更知道"什么时候不应该这么做"。** 这种预防性知识是咨询顾问最值钱的能力，现在编码进了系统里。

---

## 6. Ontology Schema 设计建议

### 6.1 节点类型

```yaml
node_types:
  # Layer 1: 业务概念
  business_concept:
    properties:
      name: string
      description: string
      domain: enum [shipping, returns, tracking, billing, customs, warehousing]
      rules: list[BusinessRule]
      compliance_tags: list[string]  # ["GDPR", "customs", "hazmat"]
      data_schema: object            # 该概念的标准数据结构

  # Layer 2: 系统
  system:
    properties:
      name: string
      owner: string                  # UPS | customer
      tech_stack: string             # "Java/Spring", "Node.js", "SAP ABAP"
      repo: string                   # git repo URL (if applicable)
      api_specs: list[APISpec]       # OpenAPI/Swagger refs
      constraints: list[Constraint]  # 变更审批、部署窗口、SLA
      environment: object            # sandbox/staging/prod URLs

  # Layer 3: 流程
  process:
    properties:
      name: string
      trigger_conditions: list[string]  # 什么条件触发这个流程
      steps: list[ProcessStep]
      risk_level: enum [low, medium, high, critical]
      required_approvals: list[string]
```

### 6.2 关系类型

```yaml
relationship_types:
  # 业务概念 ↔ 业务概念
  triggers:       # [退货] --triggers--> [退款]
  requires:       # [退货] --requires--> [退货标签]
  contains:       # [包裹] --contains--> [商品]

  # 业务概念 ↔ 系统
  implemented_by: # [退货] --implemented_by--> [Returns API v2]
  data_lives_in:  # [客户数据] --data_lives_in--> [CRM]

  # 系统 ↔ 系统
  calls:          # [电商平台] --calls--> [Returns API]
  depends_on:     # [Returns API] --depends_on--> [Address Validation API]
  syncs_with:     # [WMS] --syncs_with--> [ERP]

  # 系统 ↔ 流程
  governed_by:    # [Billing System] --governed_by--> [财务审批流程]

  # 业务概念 → 数据映射
  maps_to:        # [Shopify Order] --maps_to--> [UPS Shipment Request]
    properties:
      field_mapping: object  # {"shopify.line_items" → "ups.packages"}
      transformation: string # 转换逻辑描述
```

### 6.3 知识积累结构

```yaml
# 附着在任何节点或关系上
experience:
  - type: "known_issue"
    description: "Returns API v2 在包裹重量超过 70lbs 时返回 500 而不是 400"
    discovered_at: "2025-11-15"
    workaround: "客户端预校验重量，超过 70lbs 走 Freight Returns 流程"
    affected_customers: 3

  - type: "best_practice"
    description: "Shopify webhook 处理建议用队列异步，避免 5s 超时"
    confidence: high  # 验证过 5 次以上

  - type: "gotcha"
    description: "跨境退货标签生成需要先调 Customs API 获取 declaration ID"
    not_in_official_docs: true  # 官方文档里没有
```

**`not_in_official_docs: true` 的知识是最值钱的。** 这是只有踩过坑才知道的东西。

---

## 7. Blueprint Generator 架构

### 7.1 生成流程

```
输入:
  requirement (自然语言)
  ontology (图谱 + 文档)
  blueprint_patterns (已验证的模式库)

┌────────────────────────────────────────┐
│  Step 1: Entity Recognition & Linking  │
│  Claude + Ontology                     │
│  "Shopify 退货" →                      │
│    业务: [退货, 退货标签, 退款]          │
│    系统: [Shopify, Returns API, WMS]    │
│    合规: [PII, 跨境?]                   │
└──────────────┬─────────────────────────┘
               ▼
┌────────────────────────────────────────┐
│  Step 2: Graph Traversal               │
│  从识别的节点出发，沿关系遍历            │
│  发现: Address Validation (前置依赖)    │
│  发现: Billing (退款触发)               │
│  发现: 3 个 known_issues               │
│  发现: 2 个 best_practices             │
└──────────────┬─────────────────────────┘
               ▼
┌────────────────────────────────────────┐
│  Step 3: Constraint Aggregation        │
│  从所有涉及节点收集约束                  │
│  业务规则: 7 条                         │
│  技术约束: 4 条                         │
│  合规要求: 2 条                         │
│  流程要求: 高风险 → 全流程               │
└──────────────┬─────────────────────────┘
               ▼
┌────────────────────────────────────────┐
│  Step 4: Pattern Matching              │
│  已有"退货集成"模式 → 3 个变体           │
│  最匹配: 变体 B (Shopify + 国内)        │
│  差异: 客户没有 WMS → 跳过 B4 block     │
└──────────────┬─────────────────────────┘
               ▼
┌────────────────────────────────────────┐
│  Step 5: Blueprint Assembly            │
│  Claude 组装最终 Blueprint:             │
│  - 基于匹配的模式                       │
│  - 注入所有约束                         │
│  - 注入 known_issues 到 prompt          │
│  - 注入 field_mapping 到数据映射步骤     │
│  - 按风险等级添加审批步骤                │
│  输出: Blueprint YAML                   │
└────────────────────────────────────────┘
```

### 7.2 Claude 的角色

Claude 不是在"写 Blueprint"，而是在 **查询 ontology + 组装已有知识**：

```
Claude 做的: 理解需求 → 在 ontology 中定位 → 遍历关系 → 组装 Blueprint
Claude 不做的: 猜测 UPS API 的行为 → 编造业务规则 → 假设系统架构

知识来源: Ontology (确定性)
推理来源: Claude (灵活性)
组装输出: Blueprint (可执行)
```

**这就是为什么你的方案比 Devin 好：** Devin 100% 依赖 Claude 的推理。你的方案 80% 来自 ontology 的确定性知识，20% 来自 Claude 的推理。确定性越高，质量越稳定。

---

## 8. 实现路径

| Phase | 做什么 | 产出 | 价值 |
|-------|--------|------|------|
| **Phase 0** (已完成) | Executor as a Service | /execute, /status, /callback | 执行能力 |
| **Phase 1** | Ontology Schema 标准化 | 三层节点 + 关系类型 + 知识积累结构 | BA Agent 有标准输出格式 |
| **Phase 2** | Blueprint Generator MVP | 需求 + ontology → Blueprint YAML | 闭环：知识 → 执行 |
| **Phase 3** | Teams 集成 | Teams 消息 → BA Agent → Blueprint → Executor → Teams 回复 | 用户可用 |
| **Phase 4** | 知识飞轮 | 执行结果反馈 → ontology 自动丰富 | 越用越好 |

### Phase 2 的 MVP 实现

Blueprint Generator 本质上是一个函数：

```python
def generate_blueprint(
    requirement: str,           # 用户需求
    ontology: OntologyGraph,    # 知识图谱
    patterns: list[Blueprint],  # 已有的 Blueprint 模式
) -> Blueprint:

    # 1. Claude: 从需求中识别 ontology 实体
    entities = claude_extract_entities(requirement, ontology.node_names())

    # 2. 图遍历: 扩展影响范围
    scope = ontology.traverse(entities, max_depth=3)

    # 3. 收集约束
    constraints = ontology.collect_constraints(scope.nodes)

    # 4. 匹配已有模式
    pattern = find_best_pattern(patterns, scope)

    # 5. Claude: 组装 Blueprint
    blueprint = claude_assemble_blueprint(
        requirement=requirement,
        scope=scope,
        constraints=constraints,
        base_pattern=pattern,
        known_issues=ontology.get_experiences(scope.nodes),
    )

    return blueprint
```

**这个函数可以放在 BA Agent 里，也可以放在 Teams Bot 里，也可以是独立的 Edge Function。** 放在哪里是部署决策，不是架构决策。

---

## 9. 长期愿景

```
Year 1:
  UPS 退货/发货/追踪 ontology → Blueprint 自动生成 → 交付

Year 2:
  UPS 完整 ontology → Blueprint 模式库 →
  新客户接入从周级到小时级

Year 3:
  扩展 FedEx, DHL → 物流行业 ontology 标准 →
  "物流集成的 Stripe" (一行代码接入任何物流商)

Year 5:
  扩展到供应链 → 从物流到供应链全链路 →
  ontology 成为行业知识基础设施
```

**起点是 UPS 退货集成。终点是物流行业的知识操作系统。**

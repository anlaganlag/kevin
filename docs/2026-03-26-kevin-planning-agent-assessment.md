# Kevin Planning Agent — 深度评审与实施方案

**日期:** 2026-03-26
**评审人:** Cursor (Claude Opus) + ChatGPT o3 交叉评审
**状态:** 评审完成，待决策
**原始 Spec:** `2026-03-26-kevin-planning-agent-design.md`

---

## 一、总体判断

| 维度 | 评分 | 判断依据 |
|------|------|----------|
| **实现可行性** | 8.5/10 | ~460 行代码，1 个依赖 (pyyaml)，scope 极度克制。1-2 天可出 MVP |
| **内部业务价值** | 7/10 | Issue → PR 自动化对重复性编码任务杠杆率高，价值随 Blueprint 质量线性增长 |
| **外部产品价值** | 5/10 | 需要 HITL、并行 Block、Webhook 等 v2 能力才有外部售卖可能 |
| **自举 (Self-bootstrap) 潜力** | 6/10 | 路径存在但需 3 个里程碑版本。当前 spec 只覆盖 v1.0 |
| **MVP 交付时间** | 9/10 | 最大风险不在 runtime 代码量，而在 Blueprint 设计质量 |

**一句话结论：Kevin 的核心命题——"轻量级、CLI 原生、Blueprint 驱动的编排器能否可靠地将特定 Issue 类型转化为可验证的工程产出"——是可证伪且值得验证的。**

---

## 二、架构关键决策

### 2.1 Kevin 与 ba-toolkit 的关系：编排，不替代

**问题：** ba-toolkit 已有 `AnalysisService` 这一成熟编排器 (Celery + SSE + map-reduce)。Kevin 是第二个完全不同的编排器 (文件状态 + 子进程 agent + GitHub 触发)。两者什么关系？

**决策：Kevin 编排，不重新实现领域逻辑。**

```
正确模型:
  GitHub Issue → Kevin (编排) → Blueprint Block → Claude Code CLI → 调用 ba-toolkit API
                                                                    或在目标仓库直接编码

错误模型:
  GitHub Issue → Kevin → Claude Code CLI → "自己搞定 BA 分析"（分叉了 ba-toolkit 逻辑）
```

**具体含义：**
- `bp_coding_task.yaml` 的 B2 Block：Claude Code CLI 在目标仓库直接写代码 → 合理
- `bp_ba_requirement_analysis.yaml` 的 B3 Block：不应让 Claude Code "重新发明" feature extraction，应通过 API 调用 ba-toolkit 已有的 `AnalysisService`
- 这意味着 `agent_runner.py` 需要支持**多种执行后端**，不能只有 `claude -p`

**需要的架构调整：**

```python
# 当前 spec: 单一执行后端
subprocess.run(["claude", "-p", prompt, "--cwd", target_repo])

# 建议: Block 声明执行类型
RUNNERS = {
    "claude_cli": run_claude_block,     # Claude Code CLI (编码类任务)
    "api_call":   run_api_block,        # HTTP API 调用 (委托给已有服务)
    "shell":      run_shell_block,      # 纯 shell 命令 (测试、lint 等)
}
```

Blueprint YAML 增加 `runner` 字段：

```yaml
- block_id: B2
  name: "Implement solution"
  runner: "claude_cli"           # ← 新增
  assigned_to: builder_agent
  # ...

- block_id: B3
  name: "Run tests"
  runner: "shell"                # ← 新增
  command: "pytest tests/ --tb=short"
  # ...
```

**改动量：~30 行。影响：架构根基级。**

---

### 2.2 触发机制：GitHub Actions + Kevin CLI = 最优解

**原 spec 方案：** 手动 `python kevin.py run --issue 1`，Webhook 放到 v2。

**评审结论：GitHub Actions 触发应该是 v1.0 特性，而不是 v2。**

理由：
1. 实现成本极低 (~20 行 YAML)
2. 解决了原 spec 的三个痛点：自动触发、可观测性、团队 Auth
3. Kevin CLI 保持不变，GHA 只是一个调用入口

```yaml
# .github/workflows/kevin.yaml
name: Kevin Planning Agent
on:
  issues:
    types: [labeled]

jobs:
  kevin-run:
    if: contains(github.event.label.name, 'kevin')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          repository: centific-cn/AgenticSDLC

      - name: Checkout target repo
        uses: actions/checkout@v4
        with:
          repository: ${{ github.repository }}
          path: target-repo

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install pyyaml

      - name: Install Claude Code CLI
        run: npm install -g @anthropic-ai/claude-code

      - name: Run Kevin
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python kevin/kevin.py run \
            --issue ${{ github.event.issue.number }} \
            --repo ${{ github.repository }}

      - name: Upload state artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: kevin-run-${{ github.event.issue.number }}
          path: .kevin/runs/
```

**架构变为：**

```
GitHub Issue (贴标签: kevin + coding-task)
    │
    ▼  GitHub Actions webhook 自动触发
GHA Runner (ubuntu-latest)
    │
    ▼  执行 Kevin CLI
kevin.py run --issue N --repo owner/repo
    │
    ▼  per block
claude -p <prompt> --cwd <target-repo>  (或 API 调用 / shell 命令)
    │
    ▼  完成后
gh issue comment / gh pr create
    │
    ▼  GHA artifact upload
.kevin/runs/{run_id}/ → Actions tab 可下载查看
```

**保留 CLI 的价值：**
- 本地开发调试：`kevin.py run-block --block B2`
- dry-run 模式：`kevin.py run --dry-run`
- resume 断点续跑：`kevin.py resume --run-id xxx`

GHA 提供自动化和可观测性，CLI 提供灵活性和调试能力。两者互补，不互斥。

---

### 2.3 Claude Code CLI 的可靠性保障：验证器层

**核心风险：** `claude -p` 可以 exit 0 但实际没有完成任务（例如输出 "I couldn't do X"）。

**三层验证策略（MVP 实现前两层）：**

| 层级 | 验证器 | 实现成本 | 适用场景 |
|------|--------|----------|----------|
| L1: Git 变更检查 | Block 执行后检查 `git diff --stat`，确认有文件变更 | 5 行 Python | 所有 `claude_cli` 类型 Block |
| L2: 测试门禁 | Block 执行后运行 `pytest` / `npm test`，检查 exit code | 作为独立 `shell` 类型 Block | 所有实现类 Block 之后 |
| L3: LLM 审查 | 独立 Claude 调用审查 diff 是否满足 Block spec | ~$0.02/次，10-20s | v1.1 引入，用于高价值 Blueprint |

**建议在 Blueprint 中显式声明验证：**

```yaml
- block_id: B2
  name: "Implement solution"
  runner: "claude_cli"
  assigned_to: builder_agent
  output: "Working code with tests, committed to branch"
  validators:                          # ← 新增
    - type: "git_diff_check"
      expect: "files_changed > 0"
    - type: "command"
      run: "pytest tests/ --tb=short"
      expect: "exit_code == 0"
```

---

### 2.4 状态管理：文件制 MVP，可迁移

**原 spec 方案：** `.kevin/` 文件目录。

**评审意见：** MVP 可接受，但需明确**可观测性标准**。

当前 spec 的可观测性 = "看 Issue 评论 + 手动查 .kevin/ 目录"。这对于 GHA 运行的 Kevin 是不够的（文件在 ephemeral runner 上，运行结束就没了）。

**解决方案：**
1. GHA artifact upload（上面 workflow 已包含）
2. 每个 Block 完成后立即更新 Issue 评论（实时进度）
3. 失败时发 Slack 通知（可选，10 行代码）

**未来迁移路径：** 当需要跨 run 查询、dashboard 集成时，将 `.kevin/` 从文件换成 SQLite。这是 state.py 的内部实现变更，对 Kevin 其他模块透明。

---

### 2.5 为什么不用 Claude API？

**直接回答：Claude API 给你的是文本补全，不是 Agent。**

Kevin 的 Block B2 需要一个能够：
- 读取仓库中已有文件
- 写新文件
- 运行测试并修复错误
- 迭代式解决问题
- 执行 git commit

的 **Agent**。Claude API 返回一个字符串。要让它做到以上所有，你需要自己构建：
- 文件 I/O 层
- Tool-use 循环 (API tool_use → 执行 → 返回结果 → 下一轮)
- Git 操作封装
- 错误恢复 / 重试逻辑

这相当于用 ~2000 行代码重新实现 Claude Code CLI。**经济账算不过来。**

**成本对比：**
- Claude Code CLI：订阅制，每月固定成本
- Claude API：按 token 计费。单个 B2 Block 可能消耗 50K-100K tokens → $1-5/次
- 每天数十个 Issue × $1-5 = 显著 OpEx

**结论：Claude Code CLI 是正确抽象。API 适合"需要文本返回"的场景，不适合"需要 agent 在仓库里干活"的场景。**

---

## 三、自举 (Self-bootstrap) 路线图

**当前 spec 覆盖的是 v1.0——必要但不充分。**

自举 = Kevin 能用 Kevin 来构建和改进 Kevin。需要闭环：

```
v1.0  Kevin 执行 Blueprint（当前 spec）
  │
  ▼
v1.1  增加 bp_code_review.yaml — Kevin 创建 PR 后，独立 Agent 审查 diff
  │   增加 bp_test_verification.yaml — 实现 Block 后自动运行测试门禁
  │
  ▼
v1.2  多执行后端 — Block 可以调用 API、Shell、Claude CLI
  │   GHA 触发 + 实时进度更新
  │
  ▼
v2.0  bp_blueprint_refinement.yaml — Kevin 根据运行历史改进自身 Blueprint
  │   失败模式学习 → 调整 prompt / 验证策略
  │
  ▼
v2.1  闭环 — Kevin 根据测试失败和审查发现自动创建新 Issue
      Kevin 修自己的 bug → 完全自举
```

**v2.1 时你有一个真正的闭环系统。但 v1.0 是一切的基础，值得先做。**

---

## 四、Blueprint 是真正的产品——验证策略

### 4.1 现状

| Blueprint | 状态 | 复杂度 |
|-----------|------|--------|
| `bp_ba_requirement_analysis.1.0.0.yaml` | 已有，927 行，完备 | 高 (8 Block, HITL, 条件并行, 审计门禁) |
| `bp_coding_task.1.0.0.yaml` | spec 内联，20 行 | 极低 (3 Block, 纯顺序) |
| 其他 4 个 Blueprint | 仅名字，无内容 | 未知 |

**问题：927 行的生产 Blueprint 和 20 行的测试 Blueprint 之间差距巨大。Blueprint 编写才是真正的瓶颈。**

### 4.2 验证计划：3 个具体 Issue

在构建 Kevin runtime 之前（或同时），用这 3 个 Issue 验证 Blueprint 表达力：

#### Issue #1: 纯编码任务（验证 Claude CLI 能力）

```markdown
# kevin-test-target Issue #1
Title: "Add a /health endpoint that returns system status and uptime"
Labels: [kevin, coding-task]
Blueprint: bp_coding_task.1.0.0.yaml

预期产出:
  - B1: 需求分析 → 结构化 markdown
  - B2: 实现代码 + 测试 → git commit on feature branch
  - B3: 创建 PR with summary

验证点:
  ✓ Claude CLI 能否在空白仓库中完成从零编码?
  ✓ B2 timeout (300s) 是否够用?
  ✓ B3 能否正确读取 B2 的 git diff 并写出有意义的 PR 描述?
```

#### Issue #2: 委托给已有服务（验证多执行后端）

```markdown
# kevin-test-target Issue #2
Title: "Analyze requirements for a user notification system"
Labels: [kevin, requirement]
Blueprint: bp_ba_requirement_analysis.1.0.0.yaml (简化版)

预期产出:
  - B1: 加载上下文（shell: curl ba-toolkit API）
  - B2: 文档解析（api_call: POST /api/documents/upload）
  - B3: 特征提取（api_call: POST /api/analysis/start）
  - B4: 人工访谈（HITL — 超出 MVP scope，跳过或 mock）
  - B5: 生成 PRD（api_call: POST /api/analysis/synthesize-prd）

验证点:
  ✓ Blueprint 能否表达"调用外部 API"类型的 Block?
  ✓ Kevin 是否需要 runner 字段?（答案: 是的）
  ✓ HITL Block 如何处理?（答案: 暂时标记 skipped，v1.1 解决）
```

#### Issue #3: 代码审查（验证多 Agent 协作）

```markdown
# kevin-test-target Issue #3
Title: "Review PR #2 for code quality and test coverage"
Labels: [kevin, code-review]
Blueprint: bp_code_review.1.0.0.yaml (新建)

预期产出:
  - B1: 读取 PR diff（shell: gh pr diff 2）
  - B2: 代码审查（claude_cli: 审查 diff，写评论）
  - B3: 发布审查结果（shell: gh pr review 2 --comment --body ...)

验证点:
  ✓ Claude CLI 作为 Reviewer（与 Implementor 不同的 prompt/persona）
  ✓ Kevin 能否编排"读取 → 分析 → 反馈"类任务?
  ✓ 与 Issue #1 的输出形成闭环 (实现 → 审查)
```

### 4.3 dry-run 先行

**在写 Kevin runtime 之前**，手动 dry-run 这 3 个 Blueprint：
1. 写出每个 Block 的 prompt.md
2. 你自己扮演 Claude Code，手动执行
3. 记录：哪些 prompt 不够明确？哪些 Block 需要额外上下文？哪些 Block 需要验证器？
4. 根据发现调整 Blueprint 格式

这比直接写代码然后发现 Blueprint 格式不够用要高效得多。

---

## 五、ChatGPT o3 回复评价

ChatGPT 对 Cursor 评审的回复整体质量高，战略层面精准，但执行层面有三个空洞：

### 5.1 说对了的

| 观点 | 评价 |
|------|------|
| "Kevin 编排，不替代 ba-toolkit" | 正确答案，解决了最大架构风险 |
| "Claude CLI 需要被验证器包围" | 正确方向 |
| "自举是路线图属性，不是当前 spec" | 诚实的 scope 界定 |
| "Blueprint 设计是主要产品工作" | 核心洞察 |
| "先验证 2-3 个真实 Blueprint" | 正确的下一步 |

### 5.2 说空了的

| 空洞 | 问题 | 本文件补全 |
|------|------|-----------|
| "验证器" | 说了需要验证器，没说是哪种。Git diff check? 测试门禁? LLM 审查? | 第 2.3 节：三层验证策略 |
| "委托给已有领域引擎" | 说了要验证，没说这意味着 agent_runner 需要多执行后端 | 第 2.1 节：runner 字段设计 |
| "可观测、可恢复" | 说了文件状态可接受，没说 GHA ephemeral runner 上文件会丢 | 第 2.4 节：GHA artifact + Issue 实时更新 |

### 5.3 没问到的

**最关键的遗漏：没有追问"第一个 Issue 是什么？"** "验证 2-3 个 Blueprint" 没有具体 Issue 定义就是一个无限期漂移的 TODO。本文件第四章补全了这个缺口。

---

## 六、竞品对比与定位

| 方案 | 优势 | 劣势 | Kevin 的差异化 |
|------|------|------|---------------|
| **GitHub Actions + Claude API** | 自动触发，GitHub 原生 | API 只返回文本，不是 Agent；需自建文件/git 操作层；按 token 计费贵 | Kevin 用 Claude CLI = 免费 Agent 能力 |
| **Devin / SWE-Agent** | 全栈 AI 工程师 | 黑盒、贵、不可定制 Blueprint | Kevin = 白盒、Blueprint 可编辑、可审计 |
| **CrewAI / LangGraph** | 成熟 Agent 框架 | 重依赖、Python-only agent、无 CLI 原生执行 | Kevin = 1 个依赖、CLI 原生 |
| **Claude Code Projects** | Claude 自带项目管理 | 无编程式编排、无 Blueprint | Kevin = 可编程、可版本化 |
| **GHA + Claude Code CLI** | 自动触发 + Agent 能力 | 无 Blueprint 抽象、无 Block 编排、无 resume | **Kevin 就是这个 + Blueprint 层** |

**Kevin 的生态位：在 GHA + Claude Code CLI 之上加了 Blueprint 编排层。** 这是它存在的理由，也是它唯一需要证明的命题。

---

## 七、推荐实施顺序

```
Week 1: Blueprint 验证 (不写 Kevin 代码)
  ├─ Day 1-2: 手写 3 个 Blueprint (Issue #1, #2, #3)
  ├─ Day 3-4: 手动 dry-run，记录 prompt 和预期输出
  └─ Day 5:   根据发现调整 Blueprint YAML schema
              (确定是否需要 runner 字段、validators 字段)

Week 2: Kevin MVP Runtime
  ├─ Day 1: kevin.py + intent.py + config.py (~150 行)
  ├─ Day 2: blueprint_loader.py + state.py (~140 行)
  ├─ Day 3: agent_runner.py + prompt_template.py (~120 行)
  ├─ Day 4: github_client.py + GHA workflow (~70 行)
  └─ Day 5: 端到端测试 Issue #1 (bp_coding_task)

Week 3: 验证 + 加固
  ├─ Day 1-2: 端到端测试 Issue #3 (bp_code_review)
  ├─ Day 3: 添加 L1/L2 验证器 (git diff check + test gate)
  └─ Day 4-5: 文档 + 团队 demo
```

---

## 八、风险登记簿

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Claude Code CLI 对复杂任务超时 | 高 | 中 | per-block 可配置 timeout；拆大 Block 为小 Block |
| Claude CLI exit 0 但未完成任务 | 中 | 高 | L1 git diff check + L2 test gate |
| Blueprint 表达力不足（需要条件/循环） | 中 | 高 | Week 1 dry-run 验证；发现不足立即扩展 schema |
| 委托给 ba-toolkit API 需要 API 改造 | 低 | 中 | ba-toolkit 已有 REST API；可能需要增加 headless 分析模式 |
| GHA runner 上 Claude CLI auth 配置复杂 | 低 | 低 | ANTHROPIC_API_KEY 作为 repo secret；已有先例 |
| 团队不写 Blueprint / 写不好 | 高 | 高 | 提供 Blueprint 模板 + 验证工具 + 示例库 |

---

## 九、决策清单

以下决策需要在开始编码前确认：

- [ ] **Kevin 独立仓库 vs. ba-toolkit 子目录？** → 建议：独立仓库 `centific-cn/AgenticSDLC`
- [ ] **GHA 触发是 v1.0 还是 v2？** → 建议：v1.0（20 行 YAML，ROI 极高）
- [ ] **agent_runner 是否支持多执行后端？** → 建议：是（runner 字段，~30 行代码）
- [ ] **Blueprint 是否包含 validators 声明？** → 建议：是（L1 + L2，~20 行 schema 扩展）
- [ ] **第一个端到端测试 Issue 是什么？** → 建议：`/health` endpoint in kevin-test-target
- [ ] **bp_ba_requirement_analysis 是否通过 API 委托给 ba-toolkit？** → 建议：是，但需要 ba-toolkit 暴露 headless 分析 API

---

*本文件综合了 Cursor (Claude Opus) 初始评审、ChatGPT o3 回复、架构比较分析三轮迭代的结论。所有建议基于对 ba-toolkit 现有代码库 (`AnalysisService`, `agents/`, `tasks/`, `blueprints/`) 的实际探查。*

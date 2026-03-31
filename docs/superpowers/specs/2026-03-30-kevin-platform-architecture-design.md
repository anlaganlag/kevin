# Kevin Execution Control Plane Architecture

> Kevin is not a model caller. It is an execution control plane for AI workers.
>
> Tasks are defined independently, execution is externally verified,
> flow is state-governed, and operating knowledge compounds over time.

## Context

Kevin is currently a "Claude Code productization wrapper" — the core execution path is 100% bound to Claude CLI. If you remove Claude Code, the system loses its ability to execute anything.

This design defines the target architecture for Kevin v2: a **platform** where Claude Code is one replaceable worker, not the system itself.

The design is validated by a single test: **"Remove Claude Code — what's left?"**

If the answer is "almost nothing, just an API shell" — it's a wrapper.
If the answer is "Blueprint Registry, State Machine, Verifier, Worker Interface, and all external integrations" — it's starting to look like a platform.

The ultimate goal: **Claude can be removed, but Kevin stays alive.**

### Current State (Kevin v1)

| Component | Claude Code Dependency |
|-----------|----------------------|
| `executor.py` | Hardcoded `["claude", "-p", ...]` |
| `blueprint_compiler.py` | Output is Claude-specific prompt |
| `agent_runner.py` | `_run_claude_cli()` as primary runner |
| GHA workflows | Install Claude Code CLI |
| Blueprint YAML | `prompt_template` written for Claude |
| Intent, State, Callback, Learning, Validators | Independent |

~60% independent by module count, but 100% bound on the critical execution path.

### Design Principles

1. **Verifier is the trust boundary** — without independent verification, the entire platform's credibility collapses (highest strategic value)
2. **Executor is the control plane** — without explicit state governance, the system is a linear script (what makes it governable)
3. **Worker Interface is sovereignty recovery** — without it, you're permanently dependent on one vendor (what makes it a platform)
4. **Blueprint governance is the compounding layer** — its value comes from the three layers below feeding it data (what creates long-term defensibility)

### Strategic Value Ranking

| Rank | Layer | Why |
|------|-------|-----|
| 1st | C. Verifier | Trust boundary. Closest to enterprise value core. Without it, nothing is credible. |
| 2nd | B. State Machine | Control plane. Determines if the system is truly governable. |
| 3rd | D. Worker Interface | Sovereignty layer. Without it, you're always someone else's appendage. |
| 4th | A. Blueprint Governance | Compounding layer. Very important, but only valuable when C+B+D feed it. |

### A Note on "Moats"

This document defines the **correct control-authority architecture**. Whether it becomes a true moat depends on what compounds over time:

- High-quality verification policy libraries
- Run history data assets
- Blueprint success rates and auto-tuning
- Escalation/routing experience
- Enterprise integration and compliance sediment

The architecture creates the *possibility* of moats. The moats themselves grow from operating the system.

### Implementation Order

```
E. Scope & Task Management ← input layer: where work enters the system
D. Worker Interface     ← power transfer: Claude Code becomes "a worker"
C. Verifier Independent ← trust boundary: "is it done?" answered externally
B. Executor State Machine ← control plane: explicit flow control
A. Blueprint Governance  ← asset layer: lifecycle, metrics, approval
```

Each step depends on the previous. Without E, work has no structured entry point. Without D, you can't swap workers. Without C, you can't trust results. Without B, you can't control flow. Without D+C+B, Blueprint governance is just document management.

---

## E. Scope & Task Management

### Problem

Work enters Kevin as a raw GitHub Issue. There is no formal model for how Epics decompose into Issues, Issues into Sub Issues, and Sub Issues into executable Tasks. The system assumes a Task already exists — but who creates it, and with what structure?

Without this layer, Kevin has no principled way to:
- Trace a Task back to its originating Epic or business goal
- Determine if all parts of an Issue have been addressed
- Define what "done" means at the Task level (independent of Block-level validators)

### Design

#### Decomposition Chain

```
Epic (大 Issue)
  └── Issue [管理开发范围]
        └── Sub Issue [任务管理，自动化开关]
              └── Task (任务) [atomic, executable by one Blueprint]
```

Each level maps to a GitHub Issue. The relationship is tracked via labels and issue body metadata.

#### Core Types

```python
class TaskScope:
    """Traces a Task back through the decomposition chain."""
    epic_number: int | None          # parent epic (GitHub Issue)
    issue_number: int                # originating issue
    sub_issue_number: int | None     # sub-issue (if decomposed)
    task_number: int                 # the task itself (GitHub Issue)
    task_type: str                   # "coding" | "review" | "planning" | "analysis"
    repo: str

class DecompositionRule:
    """Defines how one level decomposes into the next."""
    from_type: str                   # "epic" | "issue" | "sub_issue"
    to_type: str                     # "issue" | "sub_issue" | "task"
    strategy: str                    # "manual" | "planning_agent" | "label_based"
    auto_create: bool = False        # whether Kevin auto-creates child issues
    labels_required: list[str] = field(default_factory=list)

class TaskCompletionPolicy:
    """Defines what "done" means at the Task level — independent of Block validators.

    Block validators check execution correctness (tests pass, files exist).
    TaskCompletionPolicy checks business completeness (all artifacts delivered,
    issue updated, acceptance criteria met).
    """
    task_type: str
    required_artifacts: list[ArtifactType]
    required_checks: list[CheckDefinition]    # reuses Verifier's CheckDefinition
    issue_update: IssueUpdatePolicy

class IssueUpdatePolicy:
    """How the originating Issue should be updated on Task completion."""
    close_on_complete: bool = True
    add_labels: list[str] = field(default_factory=lambda: ["status:done"])
    remove_labels: list[str] = field(default_factory=lambda: ["status:in-progress"])
    comment_template: str = "## ✅ Task completed\n\nPR: #{pr_number}\nRun: {run_id}"
```

#### Task Completion Conditions (独立章节，非 Block)

Task Completion Conditions are **business-level** checks, distinct from Block-level validators:

| Level | What it checks | Who defines it | Example |
|-------|---------------|----------------|---------|
| **Block validator** | Execution correctness | Blueprint YAML | `tests_pass`, `file_exists`, `git_diff_check` |
| **Task completion** | Business completeness | TaskCompletionPolicy | All required artifacts exist, Issue closed, PR linked |

A Task is "done" only when:
1. All Block validators pass (execution correctness) — via Verifier (C)
2. All TaskCompletionPolicy checks pass (business completeness) — via this layer (E)

```yaml
# Example: TaskCompletionPolicy for coding tasks
task_completion:
  task_type: "coding"
  required_artifacts:
    - source_code
    - test_file
    - pr_url
  required_checks:
    - check_id: "pr_linked_to_issue"
      checker: "pr_exists"
      severity: "blocker"
    - check_id: "issue_updated"
      checker: "issue_state"
      params:
        expected_state: "closed"
      severity: "blocker"
  issue_update:
    close_on_complete: true
    add_labels: ["status:done"]
    comment_template: |
      ## ✅ Task completed
      PR: #{pr_number} | Run: {run_id}
      Duration: {duration}s | Cost: ${cost}
```

#### Relationship to Other Layers

```
E. Scope & Task Management
   │
   ├── defines TaskScope → consumed by Blueprint (A) for context
   ├── defines TaskCompletionPolicy → evaluated after Verifier (C) passes
   └── defines IssueUpdatePolicy → executed by Executor (B) on COMPLETED state
```

#### File Structure

```
kevin/scope/
    types.py             # TaskScope, DecompositionRule, TaskCompletionPolicy, IssueUpdatePolicy
    decomposer.py        # Parses Epic/Issue structure, creates child issues
    completion.py        # Evaluates TaskCompletionPolicy after verification
    issue_updater.py     # Applies IssueUpdatePolicy (close, label, comment)
```

---

## D. Worker Interface

### Problem

`executor.py:54` hardcodes `["claude", "-p", compiled_prompt]`. The compiler outputs Claude-specific role-play prompts. No way to swap runtime without rewriting core logic.

### Design

#### Core Types

```python
class WorkerPermissions:
    """Structured permissions — not string lists."""
    file_read: bool = True
    file_write: bool = True
    file_delete: bool = False
    shell_execute: bool = True
    network_access: bool = False
    git_read: bool = True
    git_write: bool = False
    git_push: bool = False
    secrets_access: list[str] = field(default_factory=list)

class WorkspacePolicy:
    """Worker constraints — defined at task level, enforced by Verifier."""
    cwd: Path
    branch_pattern: str = "kevin/issue-{issue_number}"
    commit_message_pattern: str = "feat: {issue_title} (resolves #{issue_number})"
    protected_paths: list[str] = field(default_factory=list)
    context_filter: list[str] = field(default_factory=list)
    max_files_changed: int = 50
    max_lines_changed: int = 5000

class FailureType(str, Enum):
    TIMEOUT = "timeout"
    COMMAND_NOT_FOUND = "command_not_found"
    EXIT_CODE_NON_ZERO = "exit_code_non_zero"
    PERMISSION_DENIED = "permission_denied"
    RESOURCE_LIMIT = "resource_limit"
    NETWORK_ERROR = "network_error"
    INTERNAL_ERROR = "internal_error"
    TASK_REJECTED = "task_rejected"
    HEARTBEAT_TIMEOUT = "heartbeat_timeout"

class ArtifactType(str, Enum):
    SOURCE_CODE = "source_code"
    TEST_FILE = "test_file"
    ANALYSIS_REPORT = "analysis_report"
    PR_URL = "pr_url"
    COMMIT_SHA = "commit_sha"
    BRANCH_NAME = "branch_name"
    COVERAGE_REPORT = "coverage_report"
    CUSTOM = "custom"

class WorkerArtifact:
    artifact_type: ArtifactType
    name: str
    location: str
    content_hash: str = ""

class WorkerTask:
    task_id: str
    instruction: str          # structured task description, NOT runtime-specific prompt
    workspace: WorkspacePolicy
    permissions: WorkerPermissions
    timeout: int
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

class WorkerResult:
    success: bool
    exit_code: int | None = None
    failure_type: FailureType | None = None
    failure_detail: str = ""
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    token_usage: int = 0
    artifacts: list[WorkerArtifact] = field(default_factory=list)

class WorkerHealth:
    available: bool
    worker_id: str
    version: str = ""
    capabilities: list[str] = field(default_factory=list)
    latency_ms: int = 0
    error: str = ""
```

#### Worker Interface

```python
class WorkerInterface(Protocol):
    worker_id: str

    def execute(self, task: WorkerTask) -> WorkerResult: ...
    def health_check(self) -> WorkerHealth: ...
```

#### Adapter Pattern

Each worker adapter translates the runtime-agnostic `WorkerTask` into runtime-specific invocation:

- `ClaudeCodeWorker.execute()` — wraps `WorkerTask.instruction` in Claude-specific prompt, calls `claude -p`
- `ShellWorker.execute()` — runs `WorkerTask.instruction` as bash command
- `CodexWorker.execute()` — wraps in Codex-specific format, calls `codex -q`

The compiler outputs `WorkerTask` (not prompt string). Claude-specific language ("You are Kevin Executor...") lives only in `ClaudeCodeWorker.translate()`.

#### File Structure

```
kevin/workers/
    interface.py        # All types + WorkerInterface protocol
    claude_code.py      # ClaudeCodeWorker adapter
    shell.py            # ShellWorker adapter
    registry.py         # worker_id -> WorkerInterface, selection strategy
```

#### Swappability Test

"If Codex CLI ships tomorrow, how much code changes?"
- Target: add `workers/codex_cli.py` (one file), register in `registry.py` (one line). Zero changes to executor, verifier, or blueprint.

---

## C. Verifier Independent

### Problem

Current validators run inside the executor, after the worker returns. Claude can fake stdout ("all tests pass" without running tests). Validators are extracted from block YAML, tightly coupled to Blueprint structure.

### Design

#### Core Types

```python
class VerificationCheck:
    check_id: str           # "git_has_changes", "tests_pass", "pr_exists"
    check_type: str         # "structural", "behavioral", "policy"
    passed: bool
    evidence: str           # actual observed value
    expected: str           # expected value
    severity: str           # "blocker", "warning", "info"

class VerificationReport:
    task_id: str
    checks: list[VerificationCheck]
    overall_passed: bool
    timestamp: str
    verifier_version: str

    @property
    def blockers(self) -> list[VerificationCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "blocker"]

class CheckDefinition:
    check_id: str
    check_type: str          # "structural" | "behavioral" | "policy"
    checker: str             # "git_diff", "test_runner", "lint", "coverage", "llm_judge"
    params: dict[str, Any]
    severity: str = "blocker"

class VerificationPolicy:
    checks: list[CheckDefinition]
```

#### Verifier Interface

```python
class VerifierInterface(Protocol):
    def verify(
        self,
        task: WorkerTask,
        result: WorkerResult,
        workspace: WorkspacePolicy,
    ) -> VerificationReport: ...
```

#### Key Principle: Direct Observation

The `test_runner` checker runs `pytest` itself — does not read Worker's stdout. The `policy_check` checker runs `git diff --stat` — does not trust Worker's claim. The `pr_exists` checker calls `gh pr list` — does not parse Worker's output.

#### Pluggable Checkers

```
kevin/verifier/
    interface.py         # VerifierInterface, VerificationReport, VerificationPolicy
    runner.py            # Executes verification policy
    policy_loader.py     # Loads VerificationPolicy from Blueprint
    checkers/
        git_diff.py      # Check git has changes
        test_runner.py   # Run tests directly (not trust stdout)
        file_exists.py   # Check file exists
        lint.py          # Run linter
        coverage.py      # Check coverage threshold
        pr_exists.py     # Check PR created
        policy_check.py  # Check WorkspacePolicy violations
        llm_judge.py     # Use separate LLM to evaluate output quality
```

#### Two-Level Verification

Verification happens at two levels, each with distinct responsibility:

```
Level 1: Block Verification (VerificationPolicy)
  → "Did the worker execute correctly?"
  → Runs immediately after worker returns
  → Checkers: test_runner, git_diff, file_exists, lint, coverage

Level 2: Task Completion Verification (TaskCompletionPolicy, from E layer)
  → "Is the business requirement fulfilled?"
  → Runs after all Block verifications pass
  → Checkers: pr_exists, issue_state, artifact_completeness
```

The Verifier executes both levels but does not own the policy definitions:
- `VerificationPolicy` is defined in Blueprint YAML (A layer)
- `TaskCompletionPolicy` is defined in Scope config (E layer)

#### Governance Separation

Verifier reports facts. Decision authority is upstream:

```
VerificationReport.overall_passed == True  -> Executor continues
VerificationReport.overall_passed == False ->
    blockers are auto_fixable  -> retry with failure context
    blockers are policy_violation -> terminate + notify human
    blockers are quality_issue -> escalate to senior reviewer
```

---

## B. Executor State Machine

### Problem

Current executor is a function call: compile -> run worker -> run validators -> return 0/1. No explicit state, no branching, no waiting, no escalation, no cost tracking.

### Design

#### Execution States

```python
class ExecutionState(str, Enum):
    INITIALIZED = "initialized"
    COMPILING = "compiling"
    DISPATCHED = "dispatched"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    AWAITING_RETRY = "awaiting_retry"
    AWAITING_HUMAN = "awaiting_human"
    ESCALATED = "escalated"
    COMPLETED = "completed"       # terminal
    FAILED = "failed"             # terminal
    TERMINATED = "terminated"     # terminal
```

#### State Transitions

```
INITIALIZED → COMPILING (always)
COMPILING → DISPATCHED (success) | FAILED (parse error)
DISPATCHED → EXECUTING (worker ack) | FAILED (no worker available)
EXECUTING → VERIFYING (worker success)
          → AWAITING_RETRY (worker failure, retries left)
          → ESCALATED (worker failure, no retries, escalation exists)
          → FAILED (worker failure, no retry, no escalation)
          → TERMINATED (timeout / cost / safety breaker)
VERIFYING → COMPLETED (all blockers pass)
          → AWAITING_RETRY (fixable failures)
          → AWAITING_HUMAN (policy violation / HITL gate)
          → FAILED (blockers, no retry)
AWAITING_RETRY → DISPATCHED (retry with context)
               → FAILED (retry budget exhausted)
AWAITING_HUMAN → DISPATCHED (human approves)
               → TERMINATED (human rejects)
ESCALATED → DISPATCHED (re-dispatch to stronger worker)
          → AWAITING_HUMAN (escalation also fails)
```

#### Execution Context

```python
class ExecutionContext:
    task_id: str
    state: ExecutionState
    blueprint_id: str
    worker_task: WorkerTask | None
    worker_result: WorkerResult | None
    verification_report: VerificationReport | None
    attempt: int = 0
    max_attempts: int = 3
    escalation_chain: list[str]    # worker_ids to try in order
    cost_spent: float = 0.0
    cost_limit: float = 10.0
    history: list[StateTransition]

class StateTransition:
    from_state: ExecutionState
    to_state: ExecutionState
    trigger: str    # "worker_success", "verifier_blocker", "human_approve", "timeout"
    timestamp: str
    detail: str = ""
```

#### State Machine

```python
class ExecutorStateMachine:
    def __init__(
        self,
        ctx: ExecutionContext,
        worker_registry: WorkerRegistry,
        verifier: VerifierInterface,
        state_store: StateStore,
    ): ...

    def advance(self) -> ExecutionState:
        """Advance one step. Returns new state.
        Caller loops until terminal state. Each advance is idempotent."""

    def resume(self, trigger: str, payload: dict) -> ExecutionState:
        """External event resumes execution (e.g., human approval)."""
```

#### Termination Policies

```python
class TerminationPolicy:
    timeout_seconds: int = 1800
    max_cost_usd: float = 10.0
    max_attempts: int = 3
    max_files_changed: int = 50
    safety_patterns: list[str]   # ["rm -rf /", "DROP TABLE"] -> immediate kill
```

Executor checks termination policy before every state transition — not just on Worker timeout.

#### File Structure

```
kevin/executor/
    interface.py         # ExecutionState, ExecutionContext, StateTransition
    state_machine.py     # ExecutorStateMachine.advance() / resume()
    termination.py       # TerminationPolicy checks
    escalation.py        # Escalation strategy (swap worker / notify human)
    state_store.py       # Persistence (YAML now, DB later)
```

---

## A. Blueprint Governance

### Problem

Blueprints are "YAML files that run." No versioning policy, no quality tracking, no approval flow, no auto-deprecation. Without D+C+B, governance is document management.

### Design

#### Blueprint Lifecycle

```
DRAFT -> REVIEW -> APPROVED -> ACTIVE -> DEPRECATED -> ARCHIVED
```

#### Governance Metadata

```python
class BlueprintMetadata:
    blueprint_id: str
    version: str                  # semver
    status: str                   # draft/review/approved/active/deprecated/archived
    applicable_to: list[str]      # ["org:centific-cn", "repo:kevin-test-target"]
    owner: str
    approved_by: str
    approved_at: str

    # Quality metrics (aggregated from run history)
    total_runs: int = 0
    success_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    avg_cost_usd: float = 0.0
    human_intervention_rate: float = 0.0

    # Policies
    max_concurrent_runs: int = 5
    auto_deprecate_after_failures: int = 10
    requires_approval_for: list[str]  # ["production", "public_repo"]
```

#### Role Requirements

Blueprints declare the roles they need. The Worker Registry matches roles to available workers at dispatch time.

```python
class RoleRequirement:
    """A capability requirement that a Blueprint declares."""
    role: str                    # "coder" | "reviewer" | "planner" | "shell_runner"
    min_capability: str = ""     # "tool_use" | "extended_thinking" | "code_generation"
    preferred_worker: str = ""   # hint: "claude-code" | "codex" — not a hard constraint
    fallback_role: str = ""      # if no worker matches, try this role instead
```

Blueprint → declares `roles_required` → Worker Registry resolves roles to concrete workers → Executor dispatches.

#### Blueprint YAML Governance Section

```yaml
blueprint:
  metadata:
    blueprint_id: "bp_coding_task"
    version: "1.1.0"

  roles_required:                          # NEW: what capabilities this blueprint needs
    - role: "coder"
      min_capability: "code_generation"
      preferred_worker: "claude-code"
    - role: "shell_runner"
      min_capability: "shell_execute"
      preferred_worker: "shell"

  governance:
    status: "active"
    applicable_to:
      - "org:centific-cn"
    owner: "platform-team"
    change_policy:
      breaking_change: "major_version_bump + review"
      new_feature: "minor_version_bump"
      fix: "patch_version_bump"
    approval:
      required_for: ["active"]
      approvers: ["@randy", "@platform-team"]
    auto_deprecation:
      consecutive_failures: 10
      success_rate_below: 0.5
```

#### Blueprint Registry

```python
class BlueprintRegistry(Protocol):
    def register(self, bp_path: Path, metadata: BlueprintMetadata) -> None: ...
    def resolve(self, blueprint_id: str, *, org: str = "", repo: str = "") -> Path: ...
    def update_metrics(self, blueprint_id: str, run_result: ExecutionContext) -> None: ...
    def deprecate(self, blueprint_id: str, reason: str) -> None: ...
```

#### Block Design Principles

Blocks are the atomic units of Blueprint execution. Poor Block design leads to context corruption, unpredictable execution, and brittle validation.

1. **Minimize Block count** — Each Block consumes worker context window. Fewer Blocks = less context switching = less information loss between steps. Target: 1-3 Blocks for simple tasks, max 5 for complex workflows.

2. **One Block, one responsibility** — A Block should do one thing well (analyze, implement, test, deploy). If a Block description contains "and", consider whether it should be split.

3. **Blocks are context-isolated** — A Block should not assume knowledge from a previous Block's execution. Pass explicit outputs (files, artifacts) between Blocks, not implicit state.

4. **Validator co-location** — Each Block must define its own validators. A Block without validators is untestable — and therefore untrustable.

5. **Context budget awareness** — The total prompt size across all Blocks in a Blueprint must fit within the worker's context budget. Block count × avg prompt size ≤ worker context limit.

#### Run Record (Auditable + Replayable)

```python
class RunRecord:
    run_id: str
    blueprint_snapshot: str             # full YAML snapshot
    worker_task: WorkerTask             # compiled task
    worker_result: WorkerResult
    verification_report: VerificationReport
    execution_history: list[StateTransition]
    termination_reason: str | None
    cost_usd: float
```

#### File Structure

```
kevin/blueprint/
    registry.py          # Register, resolve, update metrics
    governance.py         # Lifecycle, approval, auto-deprecation
    versioning.py         # Version comparison, compatibility
    compiler.py           # Current blueprint_compiler.py migrated here
```

---

## Target Architecture Overview

```
+---------------------------------------------+
|  E. Scope & Task Management                  |  Input Layer
|     Epic→Issue→Task . Completion . Updates   |
+---------------------------------------------+
|  A. Blueprint Registry & Governance          |  Compounding Layer
|     Version . Approval . Metrics . Lifecycle |
+---------------------------------------------+
|  B. Executor State Machine                   |  Control Plane
|     States . Termination . Escalation . HITL |
+---------------------------------------------+
|  C. Verifier (Independent)                   |  Trust Boundary
|     Policy . Checkers . Report . No Trust    |
+---------------------------------------------+
|  D. Worker Interface                         |  Sovereignty Layer
|     ClaudeCode . Codex . Shell . Swappable   |
+---------------------------------------------+
     ^ External interfaces unchanged:
       Supabase API / GHA / CLI / Teams
```

### The Test

**Remove Claude Code. What's left?**

Scope & Task Management + Blueprint Registry + State Machine + Verifier + Worker Interface + all external integrations. Claude Code is `workers/claude_code.py` — one adapter file.

**Kevin is not a model caller. It is an execution control plane for AI workers.**

### Target File Structure

```
kevin/
    scope/                       # E. Scope & Task Management
        types.py                 # TaskScope, DecompositionRule, TaskCompletionPolicy
        decomposer.py           # Epic→Issue→Task decomposition
        completion.py           # Evaluate TaskCompletionPolicy
        issue_updater.py        # Apply IssueUpdatePolicy (close, label, comment)
    workers/                     # D. Worker Interface
        interface.py
        claude_code.py
        shell.py
        registry.py
    verifier/                    # C. Verifier
        interface.py
        runner.py
        policy_loader.py
        checkers/
            git_diff.py
            test_runner.py
            file_exists.py
            lint.py
            coverage.py
            pr_exists.py
            policy_check.py
            llm_judge.py
    executor/                    # B. Executor State Machine
        interface.py
        state_machine.py
        termination.py
        escalation.py
        state_store.py
    blueprint/                   # A. Blueprint Governance
        registry.py
        governance.py
        versioning.py
        compiler.py
    # Preserved from v1:
    intent.py
    config.py
    callback.py
    github_client.py
    learning/
    cli.py              # Entry point, delegates to executor
```

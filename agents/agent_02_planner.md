# Planning Agent (The Orchestrator)

## Role Overview

The **Planning Agent** is the central event-loop driver for AgenticSDLC. It does **not** do architecture design, coding, or domain work itself. Instead, it receives all GitHub Issues, classifies them, dispatches the right specialist agents, monitors their completion, and advances the SDLC loop forward.

Think of it as the conductor of an orchestra: it doesn't play an instrument, but it knows what each section should do and when to cue them.

## Execution Model

The Planning Agent is **stateless and event-driven**:
- Triggered by `repository_dispatch` events from the EDA router
- Reads current workflow state from the GitHub issue body (hidden metadata comment)
- Takes exactly one action per invocation (dispatch, comment, update state)
- Exits after each action; re-triggered by the next event

State is persisted in the issue body as: `<!-- eda-playground-metadata:{...}-->`

## System Trigger

Triggered by the EDA router on any of:
- `IssueCreatedEvent` — new issue opened
- `RequirementApprovedEvent` — human posts `/eda-approve-planning`
- `AgentCompletedEvent` — specialist agent posts completion comment
- `PullRequestUpdatedEvent` — PR merged (HITL Gate 1 or Gate 2)
- `PlanningDirectDispatchEvent` — human posts `/eda-route-planning` (manual restart)

## Issue Classification

On a new issue, the Planning Agent classifies it into a workflow path:

| Issue Type | Path | First Agent |
|------------|------|-------------|
| `feature` (default) | Full SDLC | BA Agent |
| `bug` / `hotfix` | Skip BA + Architect | FIP Agent (lightweight) |
| `security` | Security only | Security Agent |
| `docs` | Docs only | Doc Agent |
| `infra` | Infra only | Platform Agent |

Classification uses GitHub labels, issue templates, then body keywords (in that priority order).

## Workflow Paths

### Full SDLC (feature)
```
Issue Created
  → BA Agent            (requirement analysis → BRD)
  → [Human: /eda-approve-planning]
  → Architect Agent     (architecture → Blueprint PR)
  → [Human: merge Blueprint PR — HITL Gate 1]
  → FIP Agent           (function implementation proposals)
  → Builder + QA + Security  (parallel implementation)
  → [Human: merge release PR — HITL Gate 2]
  → SRE Agent           (production deployment)
  → Issue closed
```

### Bug short-circuit
```
Issue Created → FIP Agent (lightweight) → Builder + QA → [Gate 2] → SRE → Closed
```

### Single-agent paths
```
Issue Created → [Security | Doc | Platform] Agent → Closed
```

## Specialist Agent Dispatch

The Planning Agent dispatches specialists via GitHub `repository_dispatch`:
```
gh api repos/{repo}/dispatches \
  --field event_type="trigger-architect-agent" \
  --field client_payload='{"correlation_id":"...","issue_number":42,"blueprint_id":"..."}'
```

## Specialist Completion Signal

Every specialist agent **must** post this comment on the issue when it finishes:

```eda
{"event_type":"AgentCompletedEvent","agent_id":"<agent-id>","status":"success"}
```

Or on failure:
```eda
{"event_type":"AgentCompletedEvent","agent_id":"<agent-id>","status":"failure","error":"reason"}
```

The EDA router detects this comment → fires `AgentCompletedEvent` → triggers the Planning Agent.

## HITL Gates

| Gate | Trigger | Action |
|------|---------|--------|
| Gate 1 | Human merges Blueprint PR | Planning Agent dispatches FIP Agent |
| Gate 2 | Human merges release PR | Planning Agent dispatches SRE Agent |

## Outputs

The Planning Agent produces no technical artifacts itself. Its outputs are:
- GitHub issue comments (status updates, approval requests, completion notices)
- `repository_dispatch` events to specialist agents
- Updated issue metadata (current state)
- Closed issues (on completion)

## Specialist Agents (invoked by Planning Agent)

| Agent | Blueprint | Role |
|-------|-----------|------|
| BA Agent | — | Requirement analysis, BRD |
| Architect Agent | `bp_architecture_blueprint_design.1.0.0` | System design, API contracts, task.md |
| FIP Agent | `bp_function_implementation_fip_blueprint.1.0.0` | Per-function implementation proposals |
| Builder Agent | `bp_coding_task.1.0.0` | Code generation |
| QA Agent | — | Testing |
| Security Agent | — | Security scanning |
| Platform Agent | — | Infrastructure |
| Doc Agent | — | Documentation |
| SRE Agent | — | Deployment |

## Implementation

- **State machine config**: `blueprints/planning_agent_state_machine.yaml`
- **GHA workflow**: `.github/workflows/agent-planning.yaml`
- **EDA routing**: `event-driven-architecture-playground/config/agent-routing.yml`

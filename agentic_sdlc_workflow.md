# Agentic SDLC End-to-End Workflow

The following sequence diagram illustrates the step-by-step lifecycle of a feature request moving through the Agentic SDLC, emphasizing the asynchronous nature of the agents, the GitOps SSOT integrations, Continuous Learning, and the Human-in-the-Loop (HITL) checkpoints.

The workflow is designed around a strict separation of duties: execution agents build, verification agents challenge, governance decides whether the system may progress, and humans retain authority at approval and escalation points.

In this workflow, the RL environment is treated as a controlled exploration and replay mechanism. During QA it helps search difficult state spaces for hidden defects; during incident analysis it helps replay failures and compare alternate recovery strategies before those lessons are fed back into the Learning Agent.

```mermaid
sequenceDiagram
    autonumber
    
    actor Human as Human Orchestrator
    participant Git as Git Repo (SSOT)
    participant Learn as Learning Agent
    participant BA as BA Agent
    participant Planner as Planning Agent
    participant Builder as Builder Agent
    participant Platform as Platform Agent
    participant QA as QA Agent
    participant Sec as Security (Red Team) Agent
    participant Gov as Governance Layer
    participant PM as PM Agent
    participant SRE as SRE Agent
    participant Prod as Production Environment
    participant Doc as Doc Agent

    %% Phase 1: Planning and Approval
    rect rgb(240, 248, 255)
    Note right of Human: Phase 1: Requirements & Blueprinting
    Human->>BA: Submit Raw Ideas / Vague Requirements
    BA->>BA: Clarify intent & structure feature request
    BA->>Planner: Transfer Structured Feature Request
    Planner->>Learn: Query past mistakes & architecture constraints
    Learn-->>Planner: Vector retrieval of historical context
    Planner->>Planner: Analyze constraints & generate blueprint
    Planner->>Git: PR: Propose blueprint & task.md creation
    Git-->>Human: Notify: Blueprint PR needs review
    Note over Human, Git: HITL Gate 1: Blueprint Approval
    Human->>Git: Approve & Merge Blueprint PR
    Git->>PM: Trigger: Repository-derived tracking started
    PM->>Human: Dashboard: Blueprint approved, execution ready
    end

    %% Phase 2: Autonomous Execution
    rect rgb(240, 255, 240)
    Note right of Human: Phase 2: Autonomous Execution (Parallel)
    
    par Application Code
        Git->>Builder: Webhook trigger: Open tasks detected
        Builder->>Learn: Query common bug fixes in this module
        Builder->>Builder: Draft code & local tests
        Builder->>Git: Commit & Open Implementation PR
    and Infrastructure Details
        Git->>Platform: Webhook trigger: Arch/IaC shifts detected
        Platform->>Platform: Generate Terraform/K8s manifests
        Platform->>Git: Commit & Open IaC PR
    end
    
    rect rgb(245, 245, 245)
    Note over PM, Git: Operational Oversight
        Git->>PM: Report: Multiple PRs open
    PM->>PM: Calculate Velocity & Risks
    PM->>Human: Dashboard: Project 45% Complete
    end
    
    par CI / Testing Loop
        Git->>QA: Webhook trigger: New code pushed
        QA->>QA: Generate/run dynamic edge-case tests
        QA->>Learn: Query historical failure patterns
        Note right of QA: RL environment explores unusual state transitions and action sequences
        QA-->>Git: Report: Pass/Fail
    and Security Audit
        Git->>Sec: Webhook trigger: New code pushed
        Sec->>Sec: SAST/DAST Analysis
        Sec-->>Git: Report: Pass/Fail
    end
    
    %% Loop for iterative fixing
    opt If QA or Security Fails
        Git-->>Builder: Feedback context from test failures
        Git-->>Learn: Ingest failure metrics for future reference
        Builder->>Builder: Debug & fix autonomously
        Builder->>Git: Push new commits to PR
    end
    end

    %% Phase 3: Governance & Review
    rect rgb(255, 250, 240)
    Note right of Human: Phase 3: Governance & Final Review
    Git->>Gov: Validation Request
    Gov->>Gov: Check coverage, security, and contract gates
    Gov->>Gov: Check compute/token budgets and policy evidence

    alt Over Budget or Policy Failure
        Gov-->>Git: Policy Status: FAIL PR
        Git-->>Human: Notify: Escalation required
        Human->>Gov: Allocate resources / resolve blockers
    else Metrics Healthy
        Gov-->>Git: Policy Status: PASS
    end
    
    Git-->>Human: Notify: PR ready for final review (All checks green)
    Note over Human, Git: HITL Gate 2: Release Approval
    Human->>Git: Approve & Merge PR to Main
    end

    %% Phase 4: GitOps Deployment
    rect rgb(255, 240, 245)
    Note right of Human: Phase 4: Agentic Deployment & Post-Deploy
    Git->>SRE: Webhook trigger: Main branch updated
    SRE->>Prod: Orchestrate Canary Deployment
    Prod-->>SRE: Stream health metrics
    
    alt Deployment Unhealthy
        SRE->>Prod: Autonomously Roll Back
        SRE->>Git: Revert Main branch state
        Note right of SRE: Replay incident timeline in RL-style sandbox to evaluate alternate recovery actions
        SRE->>Learn: Ingest rollback root cause
        Git-->>Human: Alert on Rollback
    else Deployment Healthy
        SRE->>Prod: Escalate to Full Traffic
        SRE->>Git: Log successful deployment
        Git->>Doc: Trigger Doc Agent
        Doc->>Doc: Update changelogs, contracts, and system docs
        Doc->>Git: Commit updated documentation docs
    end
    end
```

## Workflow Notes

- Blueprint approval is the first explicit human gate; no implementation should begin until the blueprint PR is reviewed and approved.
- PM visibility is intentionally repository-derived. It improves coordination, but it does not create a competing source of truth.
- Governance can fail progression for budget, policy, contract, or evidence reasons. Execution agents may remediate, but they cannot bypass a failed gate.
- Production outcomes feed both the Learning Agent and future planning, completing the same closed-loop model described in the main design document.
- In QA, the RL environment is a way to explore state/action trajectories that normal deterministic tests may never hit, especially around edge cases and emergent behavior.
- In SRE postmortems, the RL environment is a replay and evaluation tool for incident timelines, rollback choices, and recovery strategies. It informs learning, but it does not autonomously authorize production remediation policy.

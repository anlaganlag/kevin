# Agentic SDLC End-to-End Workflow

The following sequence diagram illustrates the step-by-step lifecycle of a feature request moving through the Agentic SDLC, emphasizing the asynchronous nature of the agents, the GitOps SSOT integrations, Continuous Learning, and the Human-in-the-Loop (HITL) checkpoints.

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
    participant Sec as Security Agent
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
    Git->>PM: Trigger: Project Tracking Started
    PM->>Human: Dashboard: Project 0% Complete
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
    Gov->>Gov: Check test coverage gates >95%
    Gov->>Gov: Check compute/token budgets
    
    alt Over Compute Budget
        Gov-->>Git: Policy Status: FAIL PR
        Git-->>Human: Notify: Budget Exceeded, intervention required
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
        SRE->>Learn: Ingest rollback root cause
        Git-->>Human: Alert on Rollback
    else Deployment Healthy
        SRE->>Prod: Escalate to Full Traffic
        SRE->>Git: Log successful deployment
        Git->>Doc: Trigger Doc Agent
        Doc->>Doc: Auto-generate Swagger/OpenAPI & Wikis
        Doc->>Git: Commit updated documentation docs
    end
    end
```

# Agentic SDLC System Architecture

The following diagram illustrates the flow and interactions within the Agentic Software Development Lifecycle. It highlights the Git repository as the Single Source of Truth (SSOT), the specialized execution agents, the continuous learning loop, and the independent oversight of the Governance Layer.

The architecture is intentionally closed-loop. Execution agents can propose changes, verification and governance agents independently evaluate those changes, and only approved repository state becomes trusted system state. Supporting dashboards such as a GitHub Project board are useful coordination views, but they do not replace the repository as the control plane.

Within this architecture, the RL environment is best understood as a controlled exploration and replay layer. It is not a production control authority. Instead, it gives QA and SRE functions a safe place to explore system states, evaluate candidate actions, and preserve high-value trajectories for future learning.

```mermaid
graph TD
    %% Styling
    classDef human fill:#f9d0c4,stroke:#333,stroke-width:2px;
    classDef agent fill:#d4e6f1,stroke:#333,stroke-width:2px;
    classDef repo fill:#d5f5e3,stroke:#333,stroke-width:2px;
    classDef gov fill:#fcf3cf,stroke:#333,stroke-width:2px;
    classDef prod fill:#ebdef0,stroke:#333,stroke-width:2px;
    classDef learn fill:#d1f2eb,stroke:#333,stroke-width:2px;

    %% Nodes
    Human[Human Developers<br/>Orchestrators & Reviewers]:::human
    GitRepo[(Git Repository<br/>Primary SSOT)]:::repo
    GHProject[(GitHub Project Board<br/>Repository-Derived View)]:::repo
    
    subgraph Agentic_Execution_Loop ["Agentic Execution Loop"]
        BA[BA Agent<br/>Requirements Engineer]:::agent
        Planner[Planning Agent<br/>The Architect]:::agent
        Builder[Builder Agents<br/>The Software Engineers]:::agent
        Platform[Platform Agent<br/>The Infrastructure Engineer]:::agent
        QA[QA Agent<br/>The Testers]:::agent
        Security[Security (Red Team) Agent]:::agent
        PM[PM Agent<br/>The Coordinator]:::agent
    end
    
    subgraph Knowledge_Layer ["Continuous Learning Loop"]
        Learning[(Learning Agent<br/>Knowledge Base)]:::learn
        RLEnv[(RL Environment<br/>Exploration & Replay)]:::learn
    end
    
    subgraph Governance_Layer ["Governance & Auditing Layer (The Overseer)"]
        GovMetrics[Performance & Health Metrics]:::gov
        GovPolicy[Automated Policy Enforcement]:::gov
        Audit[Immutable Audit Logging]:::gov
    end
    
    subgraph Operations ["Operations & Post-Deploy"]
        SRE[SRE Agent<br/>The Operator]:::agent
        Doc[Documentation Agent<br/>Tech Writer]:::agent
    end
    
    Production[(Production Environment)]:::prod

    %% Relationships - Intent & Planning
    Human -- "1. Provides Raw Intent" --> BA
    Human -. "Views Dashboard" .-> GHProject
    BA -- "2. Clarifies & Structures Feature Requests" --> Planner
    BA -- "Creates Issues/Epics" --> GHProject
    Learning -. "Provides historical context" .-> Planner
    Planner -- "3. Generates Blueprints & task.md" --> GitRepo
    Human -. "HITL 1: Approves Blueprint" .-> GitRepo

    %% Relationships - Building & Testing
    GitRepo -- "4. Triggers Tasks via Tickets/PRs" --> Builder
    GitRepo -- "4. Triggers IaC Changes" --> Platform
    Learning -. "Provides fix patterns" .-> Builder
    
    Builder -- "5. Submits Code PRs" --> GitRepo
    Platform -- "5. Submits IaC PRs" --> GitRepo
    
    GitRepo -- "6. Triggers Dynamic Testing" --> QA
    GitRepo -- "6. Triggers SAST/DAST" --> Security
    QA -. "Explores state/action paths" .-> RLEnv
    QA -- "7. Submits Results/Fails PR" --> GitRepo
    Security -- "7. Submits Sec Review/Fails PR" --> GitRepo
    
    %% Relationships - Governance Oversight (Independent)
    Planner -. "Logs Actions" .-> Audit
    Builder -. "Logs Actions" .-> Audit
    Platform -. "Logs Actions" .-> Audit
    QA -. "Logs Actions" .-> Audit
    Security -. "Logs Actions" .-> Audit
    
    Production -. "Health / Cost Signals" .-> GovMetrics
    GitRepo -- "Validates PR constraints (Coverage, Budgets, Contracts)" --> GovPolicy
    GovMetrics -. "Runtime Evidence" .-> GovPolicy
    GovPolicy -- "Enforces Hard Gates" --> GitRepo

    %% Relationships - Deployment
    Human -. "HITL 2: Approves Consolidated PR" .-> GitRepo
    GitRepo -- "8. Main Branch Update" --> SRE
    SRE -- "9. Canary Deploy / Rollback" --> Production
    Production -- "Production Metrics" --> SRE
    SRE -. "Replays incidents / recovery policies" .-> RLEnv
    
    %% Post Deploy
    GitRepo -- "Successful Deploy" --> Doc
    Doc -- "Updates API/Architecture Docs" --> GitRepo

    %% Monitoring & Coordination
    GitRepo -. "Monitor status & velocity" .-> PM
    PM -. "Status Dashboard / Alerts" .-> Human
    PM -. "Updates Derived Coordination View" .-> GHProject
    GovPolicy -. "Budget Alerts" .-> PM

    %% Continuous Learning Ingestion
    SRE -- "Feedback on failures" --> Learning
    QA -- "Failed edge cases" --> Learning
    Security -- "Discovered Vulnerabilities" --> Learning
    RLEnv -- "Trajectories / replay lessons" --> Learning
```

## Architecture Notes

- The repository remains the only authoritative system state; `GHProject` is shown as a coordination aid derived from repository activity.
- The `Security (Red Team) Agent` is modeled as an independent challenger to proposed changes, not as part of the build path.
- The Governance Layer consumes both repository evidence and runtime signals so promotion decisions are based on proof rather than agent intent.
- The Learning Agent closes the loop by feeding historical failures, vulnerabilities, and remediation patterns back into future planning and execution.
- The RL environment supports two main use cases: QA exploration of deep or unusual state transitions, and SRE replay of incidents to evaluate alternate recovery strategies in a safe sandbox.
- RL-derived trajectories are learning artifacts, not production authority. They inform future tests, postmortems, and planning, but they do not bypass governance or human approval.

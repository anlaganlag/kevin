# Agentic SDLC System Architecture

The following diagram illustrates the flow and interactions within the Agentic Software Development Lifecycle. It highlights the Git repository as the Single Source of Truth (SSOT), the specialized execution agents, the continuous learning loop, and the independent oversight of the Governance Layer.

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
    GitRepo[(Git Repository<br/>Single Source of Truth)]:::repo
    
    subgraph Agentic_Execution_Loop ["Agentic Execution Loop"]
        BA[BA Agent<br/>Requirements Engineer]:::agent
        Planner[Planning Agent<br/>The Architect]:::agent
        Builder[Builder Agents<br/>The Software Engineers]:::agent
        Platform[Platform Agent<br/>The Infrastructure Engineer]:::agent
        QA[QA Agent<br/>The Testers]:::agent
        Security[Red Team Agent<br/>Security]:::agent
        PM[PM Agent<br/>The Coordinator]:::agent
    end
    
    subgraph Knowledge_Layer ["Continuous Learning Loop"]
        Learning[(Learning Agent<br/>Knowledge Base)]:::learn
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
    BA -- "2. Clarifies & Structures Feature Requests" --> Planner
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
    QA -- "7. Submits Results/Fails PR" --> GitRepo
    Security -- "7. Submits Sec Review/Fails PR" --> GitRepo
    
    %% Relationships - Governance Oversight (Independent)
    Planner -. "Logs Actions" .-> Audit
    Builder -. "Logs Actions" .-> Audit
    Platform -. "Logs Actions" .-> Audit
    QA -. "Logs Actions" .-> Audit
    Security -. "Logs Actions" .-> Audit
    
    GitRepo -- "Validates PR constraints (Coverage, Budgets)" --> GovPolicy
    GovPolicy -- "Enforces Hard Gates" --> GitRepo

    %% Relationships - Deployment
    Human -. "HITL 2: Approves Consolidated PR" .-> GitRepo
    GitRepo -- "8. Main Branch Update" --> SRE
    SRE -- "9. Canary Deploy / Rollback" --> Production
    Production -- "Production Metrics" --> SRE
    
    %% Post Deploy
    GitRepo -- "Successful Deploy" --> Doc
    Doc -- "Updates API/Architecture Docs" --> GitRepo

    %% Monitoring & Coordination
    GitRepo -. "Monitor status & velocity" .-> PM
    PM -. "Status Dashboard / Alerts" .-> Human
    GovPolicy -. "Budget Alerts" .-> PM

    %% Continuous Learning Ingestion
    SRE -- "Feedback on failures" --> Learning
    QA -- "Failed edge cases" --> Learning
    Security -- "Discovered Vulnerabilities" --> Learning
```

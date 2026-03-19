# Agentic SDLC: The Future of Autonomous Software Engineering

Welcome to the **Agentic Software Development Lifecycle (Agentic SDLC)** project. This repository defines a next-generation framework for building, testing, and deploying software using a coordinated swarm of specialized AI agents.

By treating the **Git Repository** as the mandatory **Single Source of Truth (SSOT)**, this lifecycle enables autonomous execution while maintaining absolute human control through advanced **GitOps** and **Human-in-the-Loop (HITL)** checkpoints.

---

## 🏛️ System Architecture

![System Architecture](./architecture.png)

The Agentic SDLC is built on four distinct layers that work in a continuous feedback loop:

1.  **Intent & Planning Layer**: Translates human ideas into structured technical blueprints and micro-tasks.
2.  **Autonomous Execution Loop**: Parallelized agents building, testing, and auditing code.
3.  **Governance & Auditing Layer**: Independent "Zero-Trust" enforcement of quality and budget policies.
4.  **Operations & Learning Layer**: Handling deployment, automated documentation, and continuous knowledge ingestion.

> [!TIP]
> View the full [Architecture Documentation](./agentic_sdlc_architecture.md) for detailed Mermaid diagrams and relationship maps.

---

## 🤖 The Agent Roster

Meet the specialized agents that drive the lifecycle:

| Agent | Role | Key Responsibility |
| :--- | :--- | :--- |
| **BA Agent** | Requirements Engineer | Translates raw intent into Epics, Features, and User Stories. |
| **Planning Agent** | The Architect | Generates technical blueprints and hierarchical `task.md` lists. |
| **Builder Agent** | Software Engineer | Writes application code and local unit tests autonomously. |
| **QA Agent** | The Tester | Generates and executes dynamic edge-case and integration tests, including RL-style exploration in bounded test sandboxes. |
| **Security (Red Team) Agent** | Red Team | Performs continuous SAST/DAST and vulnerability analysis as an independent challenger. |
| **PM Agent** | The Coordinator | Maintains repository-derived coordination views and orchestrates execution visibility. |
| **Platform Agent** | Infra Engineer | Manages IaC (Terraform/K8s) and cloud environment consistency. |
| **Governance Layer** | The Overseer | Enforces budget/coverage hard-gates and maintains audit logs. |
| **SRE Agent** | The Operator | Orchestrates canary deployments, autonomous rollbacks, and replay-informed incident learning. |
| **Learning Agent** | Knowledge Base | Ingests failures, successes, and reusable exploration/replay lessons into a retrievable context loop. |
| **Doc Agent** | Tech Writer | Auto-generates Swagger/OpenAPI, machine-readable contracts, and project docs. |

---

## 🚀 Core Philosophies

### 1. GitOps as SSOT
Nothing happens outside of Git. Every agent action, from requirement commits to infrastructure shifts, is captured as a PR or Issue. Supporting dashboards can exist, but they are repository-derived coordination views rather than competing sources of truth.

### 2. Human-in-the-Loop (HITL)
While the agents are autonomous, they are not unsupervised. Hard gates at **Phase 1 (Blueprinting)** and **Phase 3 (Final Release)** ensure that no code reaches production without human sign-off.

### 3. Continuous Learning
The **Learning Agent** monitors every failure (failed tests, security vulnerabilities, or rollbacks) and updates a retrievable knowledge layer with reusable lessons. That includes not only failures and fixes, but also high-value RL-style test trajectories and incident replay insights that can inform future planning and execution.

### 4. Bounded Exploration
The system supports RL-style exploration and replay in two places: QA test sandboxes and SRE incident postmortems. These environments are used to discover edge cases and evaluate recovery choices, but they remain bounded by governance, compute, and human approval controls.

---

## 🗺️ End-to-End Workflow

The lifecycle follows a strict sequence of handoffs managed by the PM Agent.

1.  **Inception**: Human provides intent ➔ BA Agent structures it.
2.  **Blueprinting**: Planning Agent drafts architecture ➔ **(HITL Check 1)**.
3.  **Execution**: Builder, Platform, QA, and Security agents work in parallel, with QA optionally exploring deeper state spaces through bounded RL-style testing.
4.  **Governance**: Final policy validation and budget check.
5.  **Release**: Human approval ➔ **(HITL Check 2)** ➔ SRE Agent deploys, monitors, and can feed incident replay lessons back into the learning loop.

> [!NOTE]
> Explore the [Workflow Documentation](./agentic_sdlc_workflow.md) for a complete sequence diagram.

---

## 📂 Project Structure

```bash
.
├── agents/             # Comprehensive profiles for every AI agent.
├── requirements/       # (Managed by BA Agent) Structured BRDs and Stories.
├── agentic_sdlc_concept.md
├── agentic_sdlc_architecture.md
├── design_doc.md
└── agentic_sdlc_workflow.md
```

---
© 2026 Centific-CN / Agentic SDLC Project. All rights reserved.

# Learning Agent (The Knowledge Base)

## Role Overview
The **Learning Agent** is the long-term memory of the Agentic SDLC. It prevents the system from repeating past mistakes by building a knowledge base of all successes, failures, and reusable operating lessons encountered by other agents across the repository's history.

Its role now extends beyond static retrieval. It also captures the useful outputs of RL-style exploration and replay, such as high-value failure trajectories, reproducible edge-case sequences, and effective recovery policies discovered during incident analysis.

## System Trigger
Operates on two models:
1. **Passive / Git-mediated**: Monitors CI/CD events — failed PRs, blocked checks, and merged commits — through Git webhooks.
2. **Active / On-demand**: Called directly by the Planning Agent (before blueprinting) and the Builder Agent (before writing code) to retrieve relevant historical context via a RAG query interface.

## Inputs (from Single Source of Truth)
- **CI Failure Logs**: Deep analysis of why the QA or Security agents blocked various PRs.
- **Production Rollback Data**: Ingests root cause analysis (RCA) from the SRE Agent regarding production anomalies.
- **Merge Commits**: Analyzes the "happy path" code that successfully passed all gates.
- **Human Corrections**: Intentional refactors by humans to fix agent-introduced technical debt.
- **QA Exploration Artifacts**: RL-environment trajectories, discovered state/action sequences, and edge-case repro paths that exposed useful defects.
- **SRE Replay Findings**: Incident replays, alternate recovery evaluations, and rollback-policy lessons produced during postmortem analysis.

## Outputs (to Single Source of Truth)
- **Knowledge Synthesis**: Updates a retrievable knowledge store with patterns of what works, what breaks, and what recovery or testing strategies have repeatedly proven useful.
- **Context Injection**: Provides retrieved snippets of past failures or recommended patterns when queried by other agents.
- **Trajectory Memory**: Preserves useful exploration and replay episodes as reusable context for QA, Planning, Builder, and SRE workflows.
- **Git Action**: None directly, but acts as a retrieval-augmented context source for all other agents.

## Interaction with Other Agents
- **Planner & Builder Agents**: Injects "lessons learned" into their context windows at the start of new tasks.
- **QA & Security Agents**: Learns from the edge cases and failure patterns they discover, refining the tests and safeguards it can surface later.
- **SRE Agent**: Monitors rollbacks and replay-derived incident lessons to identify unstable architectural or operational patterns.

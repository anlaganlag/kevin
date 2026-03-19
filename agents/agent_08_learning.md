# Learning Agent (The Knowledge Base)

## Role Overview
The **Learning Agent** is the long-term memory of the Agentic SDLC. It prevents the system from repeating past mistakes by building a vectorized knowledge base of all successes and failures encountered by other agents across the repository's history.

## System Trigger
Operates on two models:
1. **Passive / Git-mediated**: Monitors CI/CD events — failed PRs, blocked checks, and merged commits — through Git webhooks.
2. **Active / On-demand**: Called directly by the Planning Agent (before blueprinting) and the Builder Agent (before writing code) to retrieve relevant historical context via a RAG query interface.

## Inputs (from Single Source of Truth)
- **CI Failure Logs**: Deep analysis of why the QA or Security agents blocked various PRs.
- **Production Rollback Data**: Ingests root cause analysis (RCA) from the SRE Agent regarding production anomalies.
- **Merge Commits**: Analyzes the "happy path" code that successfully passed all gates.
- **Human Corrections**: Intentional refactors by humans to fix agent-introduced technical debt.

## Outputs (to Single Source of Truth)
- **Knowledge Synthesis**: Updates a vectorized index (often stored in a hidden `.learning` directory or an external vector DB) with patterns of "what works" and "what breaks."
- **Context Injection**: Provides retrieved snippets of past failures or recommended patterns when queried by other agents.
- **Git Action**: None directly, but acts as a retrieval-augmented generation (RAG) source for all other agents.

## Interaction with Other Agents
- **Planner & Builder Agents**: Injects "lessons learned" into their context windows at the start of new tasks.
- **QA & Security Agents**: Learns from the edge cases they discover, refining the tests it suggests to the Builder.
- **SRE Agent**: Closely monitors rollbacks to identify unstable architectural patterns.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AgenticSDLC** is a next-generation framework for autonomous software engineering using coordinated AI agents. The project treats Git Repository as the Single Source of Truth (SSOT) and implements GitOps with Human-in-the-Loop (HITL) checkpoints.

**Important Context**: This is a design documentation and architecture project, not an implemented system. The codebase contains specifications, agent definitions, and architectural documentation for a proposed framework.

## Architecture Fundamentals

### Five-Layer EDA Architecture

The system is built on an Event-Driven Architecture with five layers (from bottom to top):

1. **Infra Dependency Layer (EEF)**: Static + dynamic constraints that shape all agent behavior
2. **Standard Interfaces Layer**: Issues, Tasks, Commits, Pipelines, Artifacts
3. **Event-Driven Architecture (EDA)**: Event bus, routing, pub/sub
4. **Agent Orchestration Layer**: Ralph Loop event processing framework
5. **Governance & Audit Layer**: Cross-cutting oversight (monitors all layers)

### The Ralph Loop

Universal 5-step event processing framework:
1. **Planner Agent → Confirm Primary Agent**: Based on Issue labels + complex rules
2. **Primary Agent → Load Rules + Context**: From Infra Layer + Learning Agent
3. **Primary Agent → Coordinate Sub-Agents**: Parse Blueprint Block dependency graph
4. **Confirm Completion + Deliver Output**: Update GitHub Issues + Generate Artifacts
5. **Audit Agents → Generate Audit Report**: Governance Layer → Decision (Pass/Fail)

### Core Entities

- **Blueprint**: End-to-end executable plan composed of reusable blocks (not just feature dev - also bug fix, incident response, data analysis)
- **Event**: Internal EDA message with type-specific payload (independent from GitHub Issues)
- **Issue**: GitHub entity representing requirement/task/bug based on labels
- **Task**: Independent GitHub Issue (atomic work unit, not checkbox)
- **Artifact**: Traceable work product with unified structure
- **Commit**: Dual role as code delivery载体 AND event trigger

### Governance Model

**Critical**: Governance & Audit operates as a cross-cutting concern with multiple monitoring points:
- Real-time agent execution monitoring
- Event validation and routing
- Interface compliance checks
- Infrastructure constraint enforcement
- Final gate enforcement (Ralph Step 5)

**Separation of Concerns**:
- Execution Agents → Create changes
- Audit Agents → Report facts (no decisions)
- Governance Layer → Make decisions
- Humans → Resolve ambiguity

## Repository Structure

```
AgenticSDLC/
├── agents/              # AI Agent definitions and profiles (11 agents)
├── .claude/             # Claude Code project configuration
├── requirements/        # Managed by BA Agent (when implemented)
├── design_doc.md        # Comprehensive design documentation (v2.0)
├── agentic_sdlc_architecture.md  # Mermaid diagrams, architecture views
├── agentic_sdlc_concept.md        # High-level concept
└── agentic_sdlc_workflow.md       # End-to-end workflow sequences
```

## Agent Roster

| Agent | Type | Primary Responsibility |
|-------|------|----------------------|
| BA Agent | Strategy | Requirement analysis and structuring |
| Planning Agent | Architecture | Blueprint design and task decomposition |
| Builder Agent | Implementation | Code generation and unit tests |
| Platform Agent | Infrastructure | IaC management and infra sync |
| QA Agent | Verification | Testing and RL-style exploration |
| Security Agent | Security | Security auditing and vulnerability management |
| SRE Agent | Operations | Deployment and incident response |
| PM Agent | Coordination | Progress tracking and visibility |
| Doc Agent | Documentation | Documentation generation |
| Learning Agent | Knowledge | Historical context and patterns |
| Governance Agent | Governance | Gate enforcement and decisions |

## Key Architectural Patterns

### Primary Agent Selection Logic

Complex rules based on Issue labels, type, and metadata:
- Label priority: `security` → SecurityAgent, `infrastructure` → PlatformAgent, etc.
- Issue type defaults: `requirement` → BA_Agent, `task` → PlanningAgent
- Composite rules handle complex scenarios with multiple agents

### Blueprint Block Composition

Blueprints are assembled from reusable blocks:
- Development: `block_code_analysis`, `block_unit_test`, `block_code_review`
- Verification: `block_security_scan`, `block_qa_validation`, `block_contract_check`
- Deployment: `block_build`, `block_canary_deploy`, `block_rollback`
- Documentation: `block_api_doc`, `block_changelog`, `block_diagram_update`
- Operations: `block_monitoring`, `block_incident_response`, `block_postmortem`

### Hybrid Coordination Model

Combines dependency graph execution with event-driven communication:
- Blueprint Blocks have dependency relationships
- Primary Agent publishes Events to drive sub-agent execution
- Sub-Agents execute autonomously and publish completion Events
- Parallel execution when dependencies are satisfied

## Human-in-the-Loop Checkpoints

**HITL Gate 1**: Blueprint Approval
- Human reviews and approves technical architecture before implementation
- Located at end of Blueprint Design phase

**HITL Gate 2**: Release Approval
- Human reviews consolidated reports before merge to main
- Final review after all governance gates pass

## Document References

When working with different aspects:

- **Agent Definitions**: `agents/agent_*.md` - Individual agent specifications
- **System Architecture**: `agentic_sdlc_architecture.md` - Mermaid diagrams, dual-view architecture
- **Workflow Sequences**: `agentic_sdlc_workflow.md` - Complete sequence diagrams
- **Complete Design**: `design_doc.md` - Full v2.0 design document with all details

## Git Workflow

- All changes require feature branches
- PRs must reference relevant agent definitions
- Maintain clear commit messages linking to agents
- Repository is the SSOT - GitHub Projects are derived views only

## Development Considerations

When proposing changes or enhancements:

1. **Maintain the five-layer architecture** - Don't collapse layers
2. **Preserve event-driven design** - Events are internal entities, separate from Issues
3. **Respect governance separation** - Audit agents report facts, Governance decides
4. **Keep cross-cutting governance** - Oversight happens at multiple points, not just end
5. **Support blueprint composition** - Blueprints are assembled from reusable blocks
6. **Maintain HITL gates** - No autonomous progression past human checkpoints

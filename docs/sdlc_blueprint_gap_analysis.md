# SDLC Full-Chain Blueprint Coverage & GAP Analysis

> Based on AgenticSDLC v2.0 Design Document — Ralph Loop 5-step framework
> Date: 2026-03-29

## 1. Overview: Existing Blueprints (10 Total)

| # | Blueprint ID | Type | Agent | Blocks | Core Responsibility |
|---|---|---|---|---|
| 1 | `bp_planning_agent.1.0.0` | **orchestrator** | Planning Agent | N/A (stateless) | Central SDLC orchestrator: intent recognition → agent dispatch → state machine progression |
| 2 | `bp_ba_requirement_analysis.1.0.0` | feature | BA Agent + Learning | B1-B8 (8) | Document parsing → feature extraction → interview Q&A → PRD/user story generation |
| 3 | `bp_architecture_blueprint_design.1.0.0` | architecture | Planning + Learning + Doc + Security | B1-B8 (8) | Load context → requirement analysis → architecture design → API contracts → task breakdown → security review → create PR |
| 4 | `bp_function_implementation_fip_blueprint.1.0.0` | implementation | Planning + Builder(multi-role) + Platform + QA | B1-B12 (12) | Function-level implementation proposal: multi-expert parallel design → architecture compliance check → task breakdown |
| 5 | `bp_backend_coding_tdd_automation.1.0.0` | implementation | Builder + Security + QA | B1-B12 (12) | TDD red-green-refactor dual-cycle → code review → security review → test quality review → final validation |
| 6 | `bp_frontend_feature_ui_design.1.0.0` | feature | Frontend + Learning + QA + Security + Doc | B1-B11 (11) | UX requirement analysis → component architecture → code generation → Storybook → accessibility → security scan → visual regression baseline → PR |
| 7 | `bp_coding_task.1.0.0` | feature | Builder | B1-B3 (3) | Lightweight coding: analyze requirements → implement solution + create PR |
| 8 | `bp_code_review.1.0.0` | verification | Builder | B1-B3 (3) | Read PR context → review code → post review comments |
| 9 | `bp_test_feature_comprehensive_testing.1.0.0` | test | QA + Builder + Planning + Platform | B1-B21 (21) | Comprehensive testing: test strategy → test env setup → unit/integration/e2e design → synthetic data → RL-style exploration → adversarial testing → performance testing → QA sign-off |
| 10 | `bp_deployment_monitoring_automation.1.0.0` | deployment | Platform + Security + QA + SRE | B1-B12 (12) | Validate request → check pipeline → validate infra → check quotas → security/quality/monitoring validation → execute deployment → monitor → validate → audit trail |

---

## 2. SDLC Full-Chain Blueprint Map (Aligned to design_doc.md)

### Core Development Lifecycle (Feature Development Blueprint — design_doc Section 6.2.1)

| SDLC Phase | Ralph Loop Step | Blueprint Needed | Status | Notes |
|---|---|---|---|---|
| **Requirement Analysis** | Step 1-2 | BA Requirement Analysis | ✅ EXISTS | `bp_ba_requirement_analysis.1.0.0` |
| **HITL Gate 0** (Approve requirement) | — | — | ✅ In Planning Agent | Human approves PRD/BRD before architecture |
| **Architecture Design** | Step 2-3 | Architecture Blueprint Design | ✅ EXISTS | `bp_architecture_blueprint_design.1.0.0` |
| **HITL Gate 1** (Approve blueprint) | — | — | ✅ In Planning Agent | Human approves architecture before implementation |
| **Function Implementation Proposal** | Step 3 | FIP Generator | ✅ EXISTS | `bp_function_implementation_fip_blueprint.1.0.0` |
| **HITL Gate 1.5** (Approve FIP) | — | — | ✅ In Planning Agent | Human approves FIP before coding |
| **Backend Implementation (TDD)** | Step 3 | Backend Coding TDD | ✅ EXISTS | `bp_backend_coding_tdd_automation.1.0.0` |
| **Frontend Implementation** | Step 3 | Frontend UI Design | ✅ EXISTS | `bp_frontend_feature_ui_design.1.0.0` |
| **Lightweight Coding** | Step 3 | Coding Task (simple) | ✅ EXISTS | `bp_coding_task.1.0.0` |
| **Code Review** | Step 3-4 | Code Review | ✅ EXISTS | `bp_code_review.1.0.0` |
| **Comprehensive Testing** | Step 3-4 | Test Automation | ✅ EXISTS | `bp_test_feature_comprehensive_testing.1.0.0` |
| **HITL Gate 2** (Release approval) | — | — | ✅ In Planning Agent | Human approves release before deployment |
| **Deployment & Monitoring** | Step 4-5 | Deployment Automation | ✅ EXISTS | `bp_deployment_monitoring_automation.1.0.0` |

### Bug Fix Lifecycle (Bug Fix Blueprint — design_doc Section 6.2.2)
| SDLC Phase | Blueprint Needed | Status | Notes |
|---|---|---|---|
| **Bug Triage & Analysis** | `bp_bugfix_triage.1.0.0` | ❌ MISSING | Plan → analyze → reproduce → assess severity |
| **Fix Design** | `bp_bugfix_design.1.0.0` | ❌ MISSING | Lightweight fix design for non-critical bugs |
| **Fix Implementation** | `bp_coding_task.1.0.0` (with bug label) | ⚠️ PARTIAL | Existing coding task blueprint can handle bug fixes |
| **Fix Verification** | `bp_code_review.1.0.0` / `bp_test_feature_comprehensive_testing.1.0.0` | ⚠️ PARTIAL | Existing blueprints can verify fixes |

### Incident Response Lifecycle (Incident Response Blueprint — design_doc Section 6.2.3)
| SDLC Phase | Blueprint Needed | Status | Notes |
|---|---|---|---|
| **Initial Response & Assessment** | `bp_incident_response.1.0.0` | ❌ MISSING | SRE-driven: detect → assess → triage → escalate |
| **Incident Fix** | `bp_coding_task.1.0.0` or `bp_backend_coding_tdd_automation.1.0.0` | ⚠️ PARTIAL | Existing blueprints can handle the fix |
| **Postmortem & Learning** | `bp_postmortem_analysis.1.0.0` | ❌ MISSING | Replay analysis → root cause → lessons learned → runbook update |

### Data Analysis Lifecycle (Data Analysis Blueprint — design_doc Section 6.2.4)
| SDLC Phase | Blueprint Needed | Status | Notes |
|---|---|---|---|
| **Analysis Question Clarification** | `bp_data_analysis.1.0.0` | ❌ MISSING | BA Agent: clarify scope → define metrics → design queries |
| **Data Query & Analysis** | `bp_data_analysis.1.0.0` | ❌ MISSING | Learning Agent: query historical data → generate insights |
| **Report Generation** | `bp_data_analysis_report.1.0.0` | ❌ MISSING | Doc Agent: generate analysis report → visualizations |

### Cross-Cutting Concerns (Governance — design_doc Section 4.6 + 7)
| Concern | Blueprint Needed | Status | Notes |
|---|---|---|---|
| **Security Scanning (SAST/DAST)** | `bp_security_scan.1.0.0` | ❌ MISSING | SecurityAgent: SAST + DAST + dependency scan + secret detection. Referenced as TODO in Planning Agent |
| **Documentation Generation** | `bp_documentation_generation.1.0.0` | ❌ MISSING | DocAgent: API docs + changelogs + architecture diagrams. Referenced as TODO in Planning Agent |
| **Governance Audit** | `bp_governance_audit.1.0.0` | ❌ MISSING | Ralph Loop Step 5: parallel audit agents → gate checks → pass/fail decision |
| **Compliance Audit** | `bp_compliance_audit.1.0.0` | ❌ MISSING | API contract compliance + license compliance + data protection |
| **Cost Audit** | `bp_cost_audit.1.0.0` | ❌ MISSING | Token budget + compute resource + storage cost verification |

### Infrastructure Lifecycle
| SDLC Phase | Blueprint Needed | Status | Notes |
|---|---|---|---|
| **Infrastructure as Code** | `bp_infrastructure_iac.1.0.0` | ❌ MISSING | PlatformAgent: Terraform/K8s manifest generation + validation |
| **Infrastructure Change** | `bp_deployment_monitoring_automation.1.0.0` | ⚠️ PARTIAL | Existing deployment blueprint handles infra changes |

### Refactoring Lifecycle
| SDLC Phase | Blueprint Needed | Status | Notes |
|---|---|---|---|
| **Refactoring Analysis** | `bp_refactoring_automation.1.0.0` | ❌ MISSING | Analyze code smells → design refactoring plan → ensure no behavioral change |
| **Refactoring Implementation** | `bp_coding_task.1.0.0` | ⚠️ PARTIAL | Existing coding task blueprint can execute refactoring |

---

## 3. Summary Statistics
| Category | Count | Percentage |
|---|---|---|
| **Total Blueprints in SDLC** | ~27 | 100% |
| ✅ **Already Created** | 10 | ~37% |
| ⚠️ **Partial Coverage** (existing BP can partially serve) | 5 | ~19% |
| ❌ **Missing / New Blueprint Needed** | 12 | ~44% |

---

## 4. Missing Blueprints ( Prioritized )
### P0 — Critical Path G SDLC Chain breaksage without these)
| Priority | Blueprint ID | Type | Agent | Justification |
|---|---|---|---|---|
| **P0** | `bp_security_scan.1.0.0` | security | SecurityAgent | Explicitly listed as TODO in `bp_planning_agent`. Security gate is a hard gate in governance. Runs in parallel with builder during implementation. |
| **P0** | `bp_documentation_generation.1.0.0` | documentation | DocAgent | Explicitly listed as TODO in `bp_planning_agent`. Required for every feature delivery. |
| **P0** | `bp_governance_audit.1.0.0` | governance | GovernanceAgent | Implements Ralph Loop Step 5 (the entire governance layer is missing). Critical for zero-trust model. |

### P1 — Important for Complete SDLC coverage
| Priority | Blueprint ID | Type | Agent | Justification |
|---|---|---|---|---|
| **P1** | `bp_bugfix_triage.1.0.0` | bugfix | PlanningAgent | Bug fix is the 2nd most common SDLC workflow after feature development. |
| **P1** | `bp_incident_response.1.0.0` | incident | SREAgent | Production incident response is time-critical. Enables RL-style replay. |
| **P1** | `bp_postmortem_analysis.1.0.0` | operations | Learning + SRE + Doc | Learning feedback loop: feeds lessons back into future runs. |
### P2 — Nice to have, lower business impact
| Priority | Blueprint ID | Type | Agent | Justification |
|---|---|---|---|---|
| **P2** | `bp_data_analysis.1.0.0` | analysis | BA + Learning + Doc | Data analysis lifecycle per design_doc Section 6.2.4. |
| **P2** | `bp_infrastructure_iac.1.0.0` | infra | PlatformAgent | Terraform/K8s manifest generation and validation. |
| **P2** | `bp_refactoring_automation.1.0.0` | refactor | Planning + Builder | Code health maintenance via systematic refactoring. |
| **P2** | `bp_compliance_audit.1.0.0` | governance | ComplianceAuditAgent | Part of governance layer (Step 5). |
| **P2** | `bp_cost_audit.1.0.0` | governance | CostAuditAgent | Part of governance layer (Step 5). |
---

## 5. Architectural Observations
1. **Ralph Loop Step 5 is unimplemented**: The entire governance audit pipeline (4 parallel audit agents → gate checks → pass/fail decision) described in design_doc.md Sections 4.6 and 7 is not backed by any Blueprint. This is the most significant gap — the "zero-trust" model has no automated enforcement.

2. **Security scanning is a the critical path gap**: `bp_planning_agent.1.0.0:210` explicitly marks `security-agent` blueprint as `null # TODO`. The security gate is defined as a hard gate (zero critical/high vulnerabilities), but no automated security scanning exists.
3. **Documentation is a the critical path gap**: `bp_planning_agent.1.0.0:231` marks `doc-agent` as `null # TODO`. Every feature deployment should produce updated API docs, changelogs, and architecture diagrams.
4. **Learning feedback loop is incomplete**: The Learning Agent participates in B1 (load_context) of several blueprints, but the postmortem/lesson-harvesting side is missing. Without `bp_postmortem_analysis`, lessons from incidents and failures don't feed back into future runs.
5. **Blueprint type taxonomy needs extension**: Current types (`orchestrator`, `feature`, `architecture`, `implementation`, `verification`, `test`, `deployment`) don't cover `bugfix`, `incident`, `security`, `documentation`, `governance`, `infra`, `analysis`, `refactor`.
6. **Intent map in Kevin needs updates**: `kevin/config.py:DEFAULT_INTENT_MAP` only maps to 8 blueprints but 10 exist. Missing entries for `architecture`, `function_implementation`, `test`, and all future blueprints.

# Tester Use Cases

## Overview

This document describes the key scenarios a Tester encounters when using the Agentic SDLC platform embedded in Microsoft Teams. The platform's AI agents run autonomously in the background — Testers do not trigger or manage agents directly. Instead, the bot proactively notifies Testers at critical decision points, and the Tester's role is to review, approve, or redirect agent output.

---

## User Role Summary

| Attribute | Detail |
|---|---|
| Role | Tester (QA Engineer) |
| Primary channel | `#qa-automation` Teams channel |
| Primary interaction mode | Receiving bot notifications → reviewing output → approving or requesting changes |
| What agents handle automatically | Test scenario generation, test script creation, parallel execution, defect ticket creation, report generation |
| What the Tester decides | Whether generated scenarios are correct, whether test results are accepted, whether defects should be escalated |

---

## UC-T-01: Review and Approve Auto-Generated Test Scenarios

### Scenario Title
Approving AI-generated test scenarios before execution begins.

### User Goal
Ensure the test scenarios generated from a new requirement reflect actual testing intent before any scripts are executed.

### Trigger Condition
The Requirements Agent and Test Generation Agent have automatically processed a newly merged requirement (e.g., a Jira story or PRD update). The bot proactively posts a notification card in the `#qa-automation` channel without any action from the Tester.

### Context
The Tester is going about their normal workday. They did not initiate anything — the platform detected a new requirement and completed scenario generation in the background. The bot's notification is the first indication the Tester has that anything happened.

### User Actions
1. Tester sees a bot notification card in the Teams channel.
2. Tester reads the summary (how many scenarios were generated, which requirement they came from).
3. Tester clicks **View Scenarios** to expand the full list.
4. Tester reviews each scenario — title, coverage area, and pass/fail criteria.
5. Tester either:
   - Clicks **Approve All** to proceed to execution, or
   - Clicks **Request Changes** on specific scenarios to flag them for agent revision, or
   - Clicks **Reject** on scenarios that are entirely incorrect.
6. The bot confirms the action and updates the card with the Tester's decision and timestamp.

### Expected Result
- Approved scenarios are automatically handed to the Executor Agent for test script generation and execution.
- Scenarios flagged for changes are revised by the agent and re-submitted for review.
- The Tester spends under 5 minutes on this task; the agent handles everything else.

---

## UC-T-02: Review Defect Report After Test Execution Completes

### Scenario Title
Reviewing auto-created defect tickets following a completed test run.

### User Goal
Understand which tests failed, verify that the defect tickets created by the Defect Agent are accurate, and triage them appropriately.

### Trigger Condition
The Executor Agent completes a test run. The Validator Agent verifies the results and the Defect Agent auto-creates Jira tickets for all confirmed failures. The Reporting Agent compiles a defect summary. The bot then proactively posts a completion and defect summary card in the channel.

### Context
The Tester did not start or monitor the test run — it ran headlessly overnight or triggered by a CI/CD pipeline event. The bot's card is the first the Tester sees of the results.

### User Actions
1. Tester opens Teams and sees the test run completion card.
2. Tester reads the top-level summary: pass/fail counts, number of defects logged, severity breakdown.
3. Tester clicks **Review Defects** to open the defect list.
4. Tester scrolls through the defect list, filtering by severity if needed.
5. For each defect, the Tester can:
   - Click **View Detail** to see the failed step, error message, and auto-attached screenshot.
   - Click **Confirm & Assign** to assign the ticket to a developer.
   - Click **Mark as Flake** to flag environment-related false positives.
   - Click **Mark as Duplicate** if an identical issue was already filed.
6. Once all defects are triaged, the Tester clicks **Done Triaging**.

### Expected Result
- Jira is updated with triage decisions in real time.
- Developers receive assignment notifications via Teams DM.
- The platform's defect backlog reflects accurate, human-verified data.
- The Tester's total effort: reviewing and classifying — no manual Jira creation required.

---

## UC-T-03: Confirm Final Test Results and Sign Off on a Release Cycle

### Scenario Title
Signing off on a completed test cycle before a release is approved.

### User Goal
Give a final quality sign-off that confirms the release candidate has met the agreed test coverage and defect resolution criteria.

### Trigger Condition
All scheduled test runs for the current release cycle are complete, all P1/P2 defects are resolved, and the Reporting Agent has generated the final test summary report. The bot proactively sends a sign-off request card to the Tester.

### Context
This is the final gate before the release pipeline proceeds. The Tester must explicitly confirm before the system advances. This is a deliberate human gate — the agents do not proceed without it.

### User Actions
1. Tester receives a bot notification: *"All test runs for Release v2.4.0 are complete. A sign-off is required to proceed."*
2. Tester clicks **View Release Summary** to open the final report.
3. Tester reviews:
   - Total scenarios executed vs. planned.
   - Pass rate and trend vs. previous releases.
   - Open defect count by severity (P1/P2 must be zero).
   - Coverage gaps (if any requirements were not covered).
4. Tester is satisfied with results and clicks **Approve Release** — or clicks **Block Release** if open issues remain.
5. If approving: Tester adds an optional sign-off comment and confirms.
6. The bot posts the sign-off confirmation to the channel, timestamped and attributed.

### Expected Result
- The release pipeline receives the approval signal and proceeds.
- The sign-off event is recorded in the audit log with the Tester's identity and timestamp.
- If the release is blocked, the bot notifies the relevant team members and explains what is unresolved.

---

## UC-T-04: Ask the Bot About Test Coverage for a Specific Feature

### Scenario Title
Querying the bot for on-demand information about test coverage.

### User Goal
Quickly understand whether a specific feature or requirement is adequately covered by existing test scenarios, without leaving Teams.

### Trigger Condition
Tester-initiated. The Tester wants to check coverage before a code review or planning meeting and types a question directly to the bot.

### Context
Unlike the other use cases, this one is initiated by the Tester — not pushed by the bot. This represents the conversational query capability of the platform.

### User Actions
1. Tester types in the Teams channel: *"@QA Bot — what's the test coverage for the MFA login flow?"*
2. The bot responds within seconds with a structured summary:
   - Number of scenarios covering the feature.
   - Last execution date and pass rate.
   - Any open defects linked to this feature.
   - Link to the full coverage report.
3. Tester reads the response and follows up: *"Are there any scenarios for MFA with expired tokens?"*
4. The bot checks and responds: *"No scenario covers this case. Would you like me to generate one?"*
5. Tester clicks **Yes, Generate** — the agent creates a new scenario and returns it for review.

### Expected Result
- The Tester gets coverage information in under 30 seconds without switching tools.
- The bot can generate missing scenarios on demand.
- New scenarios follow the same approval flow as UC-T-01.

---

## Open Questions

> The following items require confirmation from the Product Manager before finalizing interaction design.

1. **Approval authority:** Can any Tester in the channel approve scenarios and sign off on releases, or is this restricted to a designated QA Lead role?
2. **Scenario editing:** In UC-T-01, can Testers manually edit the text of a scenario, or can they only approve, reject, or request agent-driven changes?
3. **Defect triage scope:** In UC-T-02, are "Mark as Flake" and "Mark as Duplicate" final decisions, or do they require secondary confirmation from a lead?
4. **Sign-off blocking criteria:** In UC-T-03, are the P1/P2 zero-defect criteria hard-coded, or can they be configured per project/release?
5. **Bot query scope:** In UC-T-04, what data sources does the bot have access to for answering coverage questions — only the current cycle, or historical data across all releases?
6. **Notification channel:** Are all bot notifications posted to a shared channel, or are some (e.g., sign-off requests) also sent as direct messages to specific individuals?

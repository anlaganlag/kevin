# Developer Use Cases

## Overview

This document describes the key scenarios a Developer encounters when using the Agentic SDLC platform embedded in Microsoft Teams. The platform's AI agents run continuously in the background, monitoring builds, analyzing failures, and preparing fix suggestions — without requiring the Developer to trigger or manage any of it. The bot contacts the Developer only when their attention or decision is needed.

---

## User Role Summary

| Attribute | Detail |
|---|---|
| Role | Developer (Software Engineer) |
| Primary channel | `#dev-pipeline` Teams channel + personal DMs |
| Primary interaction mode | Receiving bot notifications → reading failure context → acting on suggestions |
| What agents handle automatically | Build monitoring, failure log analysis, root cause inference, fix suggestion generation, rerun scheduling, defect correlation |
| What the Developer decides | Whether to act on a fix suggestion, whether to trigger a rerun, whether a defect is their responsibility |

---

## UC-D-01: Receive a Build Failure Notification and Act on a Fix Suggestion

### Scenario Title
Responding to an AI-analyzed build failure with a suggested fix.

### User Goal
Understand why a build failed and apply a fix quickly, without spending time manually reading through logs.

### Trigger Condition
A CI/CD pipeline build fails after the Developer merges a pull request. The platform's Executor Agent detects the failure, the Validator Agent confirms it is not an environment flake, and an AI analysis agent generates a root cause summary and fix suggestion. The bot proactively posts a notification card — both in the shared `#dev-pipeline` channel and as a direct message to the Developer who owns the commit.

### Context
The Developer has just merged code and moved on to their next task. The build failure is detected and analyzed automatically. By the time the Developer checks Teams, a full diagnosis is already available — they do not need to pull logs or run anything manually first.

### User Actions
1. Developer sees a bot DM: *"Build failed for your commit [abc1234] on branch `feature/mfa-flow`. Root cause identified. [View Details]"*
2. Developer clicks **View Details** to open the failure card.
3. Developer reads:
   - Which build step failed and the plain-language reason.
   - The specific file, line, and function implicated.
   - The AI-generated fix suggestion (e.g., corrected code snippet or configuration change).
4. Developer evaluates the suggestion:
   - Clicks **Apply Fix** to let the agent raise a draft PR with the suggested change, or
   - Clicks **I'll Fix Manually** to dismiss the suggestion and handle it themselves, or
   - Clicks **This is Wrong** to reject the suggestion and provide feedback.
5. If **Apply Fix** is chosen: the agent creates a draft PR and the bot posts a link to it.
6. Developer reviews the draft PR and merges or adjusts it.

### Expected Result
- The Developer understands the failure within seconds of opening the notification.
- Applying a fix takes fewer than 3 clicks.
- The bot does not require the Developer to manually search logs, Jira, or CI dashboards.

---

## UC-D-02: Trigger a Selective Rerun After Fixing a Flaky Test

### Scenario Title
Retrying only the failed test cases after a known environment issue is resolved.

### User Goal
Confirm that a previous failure was environmental (not a code defect) by re-running only the affected test scripts against a stable environment.

### Trigger Condition
A test run completed with failures. The Tester or DevOps Engineer has marked some failures as environment-related flakes. The bot notifies the Developer whose code was under test that a rerun is available and recommended.

### Context
The Developer's code is being held up because tests failed for reasons unrelated to their changes (e.g., a network timeout in the test environment). They want to unblock the pipeline without waiting for the full test suite to re-run from scratch.

### User Actions
1. Developer sees a bot notification: *"3 test failures on your branch `feature/checkout-v2` have been marked as environment flakes. A targeted rerun is available. [Trigger Rerun]"*
2. Developer reads the short summary: which scripts failed, why they were classified as flakes, and which environment will be used for the rerun.
3. Developer clicks **Trigger Rerun**.
4. The bot confirms: *"Rerun scheduled for 3 scripts. You'll be notified when complete — usually within 5 minutes."*
5. Developer continues their work. When results arrive, the bot posts: *"Rerun complete — all 3 scripts passed. Your pipeline is unblocked. [View Results]"*
6. Developer clicks **View Results** to confirm, then proceeds.

### Expected Result
- The Developer unblocks their pipeline with a single click.
- They are not required to understand the test infrastructure or manually configure what to rerun.
- The entire process takes under 2 minutes of active attention.

---

## UC-D-03: Receive and Act on a Defect Assignment

### Scenario Title
Responding to a defect ticket automatically assigned by the Defect Agent.

### User Goal
Quickly understand the defect context, assess whether the root cause is within their code, and either acknowledge ownership or escalate.

### Trigger Condition
A test execution failure has been confirmed as a genuine defect. The Defect Agent created a Jira ticket and, based on Git blame and component ownership metadata, assigned it to a specific Developer. The bot delivers an assignment notification as a direct message.

### Context
The Developer was not monitoring the test run. The assignment arrives unsolicited. The Developer's first response is to determine whether the defect genuinely belongs to them and to understand the failure context with minimal investigation effort.

### User Actions
1. Developer receives a Teams DM: *"A defect has been assigned to you: [PROJ-512] — Checkout total mismatch on discount stacking. Priority: High. [View Defect]"*
2. Developer clicks **View Defect**.
3. The defect detail card shows:
   - Plain-language description of the failure.
   - The specific test step that failed.
   - A screenshot or log snippet taken at the point of failure.
   - The file(s) and commit(s) the agent identified as likely culprits.
   - A link to the full Jira ticket.
4. Developer decides:
   - Clicks **Acknowledge** if the defect is theirs — status updates to `In Progress` in Jira.
   - Clicks **Reassign** if it belongs to another team — opens a people picker.
   - Clicks **Dispute** if they believe the root cause analysis is incorrect — triggers an agent re-analysis with a comment.
5. After acknowledging, the Developer resolves the issue, then clicks **Request Retest** to notify the Tester.

### Expected Result
- The Developer understands the defect without visiting Jira, the CI dashboard, or the test runner.
- Ownership decisions (acknowledge / reassign / dispute) take one click.
- The Tester is automatically notified when the Developer marks the fix as ready.

---

## UC-D-04: Ask the Bot About the Status of a Specific Build or Test Run

### Scenario Title
Querying the bot for real-time pipeline status during active development.

### User Goal
Get a quick status update on a specific branch's build and test run without leaving Teams or opening external dashboards.

### Trigger Condition
Developer-initiated. The Developer is waiting on a pipeline result and wants to check progress proactively by asking the bot.

### Context
The Developer is mid-task and wants a quick status check. They don't want to switch context to a CI dashboard. The bot serves as the single conversational interface to all pipeline information.

### User Actions
1. Developer types in the channel: *"@Dev Bot — what's the status of the build for `feature/mfa-flow`?"*
2. The bot responds immediately with a structured status card:
   - Branch name and latest commit.
   - Current pipeline stage (e.g., Build → Test → Deploy).
   - Stage-level pass/fail status.
   - Estimated time to completion (if in progress).
   - Any blocking issues detected.
3. Developer reads the response and follows up: *"When did the last test run finish?"*
4. Bot responds: *"Last run completed 43 minutes ago. 2 failures — both assigned to you. [View Defects]"*
5. Developer clicks **View Defects** to jump directly into the defect flow (UC-D-03).

### Expected Result
- The Developer gets pipeline status in under 10 seconds without switching tools.
- The bot can answer follow-up questions in the same conversation thread.
- The bot links to relevant actions rather than just reporting information.

---

## Open Questions

> The following items require confirmation from the Product Manager before finalizing interaction design.

1. **Apply Fix permissions:** Can all Developers use the "Apply Fix" action, or is it gated by repository permissions? What happens if the Developer does not have write access to the branch?
2. **Rerun authorization:** In UC-D-02, can any Developer trigger a rerun of any branch, or only their own? Is there a rate limit?
3. **Defect assignment logic:** In UC-D-03, what happens when the agent cannot determine an owner (e.g., no clear Git blame match)? Is it assigned to a team queue or left unassigned?
4. **Bot query scope:** In UC-D-04, can the Developer query status for any branch or only branches they own or have contributed to?

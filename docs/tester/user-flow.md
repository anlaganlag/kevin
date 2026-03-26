# Tester User Flows

## Overview

This document details the step-by-step interaction flows for each Tester use case. Each flow begins from the moment the Tester opens Microsoft Teams and ends when the task is complete. Flows are described at the level of individual steps — what the bot says, what the user sees, and how the user responds — so that the intended user experience is unambiguous.

All flows follow the same fundamental pattern:
**Bot notifies → Tester reads → Tester acts → System confirms**

The Tester never starts a flow themselves (except UC-T-04). Every other flow is initiated by a bot notification.

---

## Flow 1: Review and Approve Auto-Generated Test Scenarios (UC-T-01)

### Flow Summary

| Attribute | Detail |
|---|---|
| Initiator | Bot (proactive notification) |
| Channel | `#qa-automation` |
| Estimated time | 3–8 minutes |
| Outcome | Scenarios approved for execution, or revision requested |

### Steps

**1. Tester opens Teams and sees a new bot message in `#qa-automation`.**

The bot has posted a notification card. The Tester has not taken any prior action — this is the first indication that something has happened.

Bot card content:
```
🔔  New Test Scenarios Ready for Review
────────────────────────────────────────
Requirement:   PROJ-210 — New Checkout Flow (v2)
Generated:     14 test scenarios
Coverage:      Functional, Edge Cases, Regression
────────────────────────────────────────
Review and approve to begin test execution.

[ View Scenarios ]   [ Approve All ]
```

---

**2. Tester clicks "View Scenarios" to read the full list before approving.**

The card expands (or a detail panel opens) to show all 14 scenarios in a table:

| # | Scenario Title | Type | Priority |
|---|---|---|---|
| 1 | Guest checkout — success path | Functional | High |
| 2 | Checkout with expired credit card | Edge Case | High |
| 3 | Apply discount code at checkout | Functional | Medium |
| ... | ... | ... | ... |

Each scenario row has two inline actions: **Approve** and **Flag for Revision**.

---

**3. Tester reads through the scenario list.**

The Tester skims the list. Most scenarios look correct. They notice scenario #7 — *"Checkout with two simultaneous discount codes"* — is not applicable to this release because the multi-discount feature is out of scope.

---

**4. Tester clicks "Flag for Revision" on scenario #7.**

A short input field appears inline:
```
Why should this scenario be revised?
[ Discount stacking is out of scope for this release.    ]
[ Submit ]
```
The Tester types a reason and clicks **Submit**. Scenario #7 is now marked `⚠ Flagged`.

---

**5. Tester clicks "Approve All" for the remaining 13 scenarios.**

A confirmation prompt appears:
```
Approve 13 scenarios?
Scenario #7 will be excluded and sent back for revision.
[ Cancel ]  [ Confirm Approval ]
```

The Tester clicks **Confirm Approval**.

---

**6. The card updates to reflect the decision.**

```
✓  13 scenarios approved by Sarah Lee · 26 Mar 2026, 09:14 UTC
⚠  1 scenario flagged for revision — agent will re-generate and resubmit.

Test execution will begin shortly.
[ View Execution Status ]
```

---

**7. Tester optionally clicks "View Execution Status" to monitor progress.**

The bot opens the execution monitor view (or links to it) — showing the live run status. The Tester can close this and return to other work; they will be notified when execution completes.

---

## Flow 2: Review Defect Report After Test Execution (UC-T-02)

### Flow Summary

| Attribute | Detail |
|---|---|
| Initiator | Bot (proactive notification after run completes) |
| Channel | `#qa-automation` |
| Estimated time | 5–15 minutes depending on defect count |
| Outcome | All defects triaged; Jira updated; developers notified |

### Steps

**1. Tester opens Teams the next morning. The bot has posted a run completion card overnight.**

```
✅  Test Run Complete — RUN-2024-0091
────────────────────────────────────────────────
Environment:   Staging
Duration:      18m 42s   |   Completed: 02:14 UTC

  Passed    41   ████████████████████  84%
  Failed     6   ████░░░░░░░░░░░░░░░   12%
  Skipped    2   ██░░░░░░░░░░░░░░░░░░   4%

  Defects logged:  6   (1 Critical · 3 High · 2 Medium)
────────────────────────────────────────────────
[ Review Defects ]   [ View Full Report ]
```

---

**2. Tester clicks "Review Defects".**

The bot posts (or expands to show) the defect list card:

```
🐛  Defects — RUN-2024-0091
──────────────────────────────────────────────────────────
  ● CRIT   PROJ-501   Payment gateway timeout — Staging data set
  ● HIGH   PROJ-502   Cart total wrong with stacked discounts
  ● HIGH   PROJ-503   MFA prompt skipped on second login
  ● HIGH   PROJ-504   Order confirmation email not sent
  ● MED    PROJ-505   Product image missing on mobile checkout
  ● MED    PROJ-506   Filter reset doesn't clear URL params
──────────────────────────────────────────────────────────
[ Filter by Severity ]   [ Done Triaging ]
```

---

**3. Tester clicks into PROJ-501 (Critical) first.**

The defect detail card opens:

```
PROJ-501 — Payment gateway timeout on Staging dataset
────────────────────────────────────────────────────────
Severity:    Critical   |   Status: New
Failed Step: Step 6 — "Place Order" button click
Error:       Gateway connection timed out after 30s
             (STRIPE_CONNECT_TIMEOUT)
Screenshot:  [thumbnail — click to expand]
Likely cause: Stripe SDK timeout not configured (defaults to 30s)
────────────────────────────────────────────────────────
[ Confirm & Assign ]   [ Mark as Flake ]   [ Mark as Duplicate ]
[ Open in Jira ]
```

---

**4. Tester reviews the detail and determines this is a genuine defect.**

Tester clicks **Confirm & Assign**. A people picker appears:
```
Assign to:  [ Search developer...       ▼ ]
[ Assign ]
```
Tester selects Alex Chen. Clicks **Assign**.

The bot confirms:
```
✓  PROJ-501 assigned to Alex Chen. He has been notified via DM.
```

---

**5. Tester opens PROJ-503 (MFA prompt skipped on second login).**

After reviewing the detail, the Tester recognizes this has already been filed in a previous sprint.

Tester clicks **Mark as Duplicate**:
```
Link to existing ticket:  [ PROJ-477       ]
[ Confirm Duplicate ]
```
Tester enters `PROJ-477` and confirms. Jira is updated automatically.

---

**6. Tester works through remaining defects.**

After reviewing all 6 defects, the triage breakdown is:
- 4 confirmed and assigned to developers
- 1 marked as duplicate
- 1 marked as flake (PROJ-506 — confirmed to be a browser rendering issue in the test environment, not a product defect)

---

**7. Tester clicks "Done Triaging".**

The bot posts a triage summary to the channel:

```
✓  Defect triage complete — Sarah Lee · 26 Mar 2026, 09:38 UTC
────────────────────────────────────────────────────────────
  Assigned:   4   defects → developers notified
  Duplicate:  1   → linked to PROJ-477
  Flake:      1   → closed, not a product defect
────────────────────────────────────────────────────────────
[ View Jira Board ]   [ View Full Report ]
```

---

## Flow 3: Sign Off on a Release Cycle (UC-T-03)

### Flow Summary

| Attribute | Detail |
|---|---|
| Initiator | Bot (proactive — triggered when all criteria are met) |
| Channel | `#qa-automation` + DM to Tester |
| Estimated time | 5–10 minutes |
| Outcome | Release approved or blocked, audit record created |

### Steps

**1. Tester receives a bot DM and a channel card simultaneously.**

DM:
```
Hi Sarah — all test runs for Release v2.4.0 are complete.
Your sign-off is required to proceed with deployment.
[ View Release Summary ]
```

Channel card:
```
🔔  Release Sign-Off Required — v2.4.0
────────────────────────────────────────
All planned test cycles are complete.
A QA sign-off is required before deployment proceeds.
Awaiting:  Sarah Lee (QA Lead)
[ View Release Summary ]
```

---

**2. Tester clicks "View Release Summary".**

The full release summary report opens:

```
📋  Release Test Summary — v2.4.0
────────────────────────────────────────────────────────
  Total scenarios planned:    62
  Scenarios executed:         62   (100%)
  Overall pass rate:          94.1%   ↑ vs. v2.3.0 (91.2%)

  Open Defects by Severity:
    P1 (Blocker):    0   ✓
    P2 (Critical):   0   ✓
    P3 (High):       2   (both deferred to v2.5.0)
    P4 (Medium):     5   (all triaged)

  Coverage gaps:    0
  Flakes excluded:  3
────────────────────────────────────────────────────────
  Recommendation:  ✅  Ready for release

[ Approve Release ]   [ Block Release ]
```

---

**3. Tester reviews the summary.**

P1 and P2 defects are zero. Two P3 defects have been formally deferred. Tester is satisfied.

---

**4. Tester clicks "Approve Release".**

A confirmation dialog appears:
```
Approve Release v2.4.0?
This will authorize the deployment pipeline to proceed.

Optional comment:
[ All criteria met. P3 defects deferred per agreement. ]

[ Cancel ]   [ Confirm Approval ]
```

Tester adds a comment and clicks **Confirm Approval**.

---

**5. The bot posts the sign-off confirmation to the channel.**

```
✅  Release v2.4.0 Approved
────────────────────────────────────────────────────────
Approved by:   Sarah Lee (QA Lead)
Date:          26 Mar 2026, 10:02 UTC
Comment:       All criteria met. P3 defects deferred per agreement.

Deployment pipeline has been authorized to proceed.
────────────────────────────────────────────────────────
[ View Audit Log ]   [ View Full Report ]
```

The Tester's job is done. The deployment pipeline proceeds automatically.

---

## Flow 4: Query the Bot for Coverage Information (UC-T-04)

### Flow Summary

| Attribute | Detail |
|---|---|
| Initiator | Tester (typed query) |
| Channel | `#qa-automation` |
| Estimated time | Under 2 minutes |
| Outcome | Coverage information retrieved; optional new scenario generated |

### Steps

**1. Tester types a question in the Teams channel.**

```
@QA Bot what's the test coverage for the MFA login flow?
```

---

**2. Bot responds within a few seconds.**

```
📊  Coverage Summary — MFA Login Flow
────────────────────────────────────────────────────────
  Scenarios covering this feature:   8
  Last executed:                     25 Mar 2026, 14:00 UTC
  Pass rate (last run):              87.5%   (7/8 passed)

  Open defects linked to this feature:
    PROJ-503 — MFA prompt skipped on second login (High)

  [ View All Scenarios ]   [ View Coverage Report ]
```

---

**3. Tester follows up with a more specific question.**

```
Are there any test cases for MFA with expired tokens?
```

---

**4. Bot checks and responds.**

```
No scenario currently covers MFA with expired tokens.

Would you like me to generate one?
[ Yes, Generate Scenario ]   [ No thanks ]
```

---

**5. Tester clicks "Yes, Generate Scenario".**

The bot shows a brief loading state:
```
⟳  Generating scenario — this takes about 30 seconds…
```

---

**6. Bot posts the generated scenario for review.**

```
📝  New Scenario Generated
────────────────────────────────────────────────────────
Title:     MFA login attempt with expired token
Type:      Edge Case
Priority:  High

Preconditions:
  - User has MFA enabled
  - OTP token has expired (> 30s old)

Steps:
  1. User enters valid username and password
  2. MFA prompt appears
  3. User enters an expired OTP code
  4. System should reject the token and display an error

Expected result:
  Login is rejected. User sees "Token expired — please request a new code."
────────────────────────────────────────────────────────
[ Approve ]   [ Request Changes ]   [ Reject ]
```

---

**7. Tester reviews and clicks "Approve".**

The scenario is added to the test suite and queued for the next execution cycle. The bot confirms:
```
✓  Scenario approved and added to the MFA login test suite.
   It will be included in the next scheduled run.
```

---

## Open Questions

> The following items require confirmation from the Product Manager before implementation.

1. **Partial approval in Flow 1:** If a Tester flags some scenarios for revision and approves the rest, should execution begin immediately for approved scenarios while awaiting revised ones, or should the entire batch wait?
2. **Flow 2 — flake classification:** Can a Tester mark a defect as a flake unilaterally, or does this require a second approval (e.g., from a DevOps Engineer or lead)?
3. **Flow 3 — sign-off delegation:** If the designated QA Lead is unavailable, can another Tester provide the sign-off? If yes, how is the fallback person determined?
4. **Flow 4 — scenario generation placement:** When a Tester generates an ad-hoc scenario via chat (Flow 4), which test suite does it belong to? Is it added to a pending bucket or attached to a specific requirement?
5. **Audit trail access:** Is the audit log (referenced in Flow 3) visible to all channel members, or restricted to QA Leads and admins?

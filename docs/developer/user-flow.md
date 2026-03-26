# Developer User Flows

## Overview

This document details the step-by-step interaction flows for each Developer use case. Each flow begins from the moment the Developer receives a bot notification (or sends a query) and ends when the task is resolved. Flows are described at the level of individual steps — what the bot sends, what the Developer sees on screen, and exactly how they respond.

All flows except UC-D-04 are bot-initiated. The Developer does not need to watch dashboards, open CI tools, or check Jira unprompted — the bot surfaces the right information at the right moment.

---

## Flow 1: Respond to a Build Failure with an AI-Suggested Fix (UC-D-01)

### Flow Summary

| Attribute | Detail |
|---|---|
| Initiator | Bot (proactive DM + channel notification) |
| Channel | DM to Developer + `#dev-pipeline` |
| Estimated time | 2–5 minutes |
| Outcome | Fix applied via agent-generated draft PR, or developer takes manual ownership |

### Steps

**1. Developer receives a Teams direct message from the bot.**

The DM arrives within seconds of the build failure being analyzed:

```
⚠️  Build Failed — Your Commit
────────────────────────────────────────────────────────
Branch:    feature/mfa-flow
Commit:    abc1234 — "Add OTP expiry validation"
Stage:     Unit Tests
────────────────────────────────────────────────────────
The AI has analyzed the failure and identified a likely fix.

[ View Details ]
```

A parallel notification is posted in `#dev-pipeline` so the team is also aware.

---

**2. Developer clicks "View Details".**

The full failure analysis card expands:

```
🔍  Build Failure Analysis
────────────────────────────────────────────────────────
What failed:
  Unit test: test_otp_expiry_check
  Error:     AssertionError — expected False, got True

Why it failed:
  The expiry check in `auth/otp.py` uses `>=` instead of `>`,
  causing valid tokens at exactly t=30s to be rejected.

File:     auth/otp.py
Line:     47
Function: is_token_valid()

────────────────────────────────────────────────────────
💡  Suggested Fix:

  - if token_age >= OTP_EXPIRY_SECONDS:
  + if token_age > OTP_EXPIRY_SECONDS:

────────────────────────────────────────────────────────
[ Apply Fix (Draft PR) ]   [ I'll Fix Manually ]   [ This is Wrong ]
```

---

**3. Developer reads the analysis.**

The failure explanation is clear and specific. The Developer agrees with the suggested fix — a one-character operator change.

---

**4. Developer clicks "Apply Fix (Draft PR)".**

A brief loading indicator appears:
```
⟳  Creating draft PR with suggested fix…
```

---

**5. Bot posts the draft PR confirmation.**

```
✅  Draft PR Created
────────────────────────────────────────────────────────
PR Title:   Fix OTP expiry boundary condition in is_token_valid()
Branch:     fix/abc1234-otp-expiry-boundary
Target:     feature/mfa-flow
Changes:    1 file · 1 line changed

[ Open PR in GitHub ]   [ View Diff ]
```

---

**6. Developer clicks "Open PR in GitHub" to review the change.**

The Developer reviews the one-line diff, confirms it is correct, and merges the PR. The build re-runs automatically.

---

**7. Bot notifies the Developer when the rebuild passes.**

```
✅  Build Passed — feature/mfa-flow
────────────────────────────────────────────────────────
Fix verified. All unit tests passing.
Pipeline proceeding to next stage.
[ View Pipeline Status ]
```

---

## Flow 2: Trigger a Selective Rerun After a Flaky Test Failure (UC-D-02)

### Flow Summary

| Attribute | Detail |
|---|---|
| Initiator | Bot (proactive notification) |
| Channel | DM to Developer + `#dev-pipeline` |
| Estimated time | Under 2 minutes of active effort; 5–10 minutes total wait |
| Outcome | Targeted rerun completes; pipeline unblocked |

### Steps

**1. Developer sees a bot DM.**

```
ℹ️  Flaky Test Failures Detected — Your Branch
────────────────────────────────────────────────────────
Branch:    feature/checkout-v2
3 test failures have been classified as environment flakes
by the QA team. Your code is not implicated.

A targeted rerun is available to unblock your pipeline.

[ View Flake Details ]   [ Trigger Rerun ]
```

---

**2. Developer clicks "View Flake Details" before triggering the rerun.**

```
📋  Flake Classification Summary
────────────────────────────────────────────────────────
  TC-042   checkout_network_timeout      → DNS resolution failure (test infra)
  TC-051   cart_sync_delay_check         → Redis connection refused (test infra)
  TC-067   payment_gateway_handshake     → SSL cert mismatch (staging cert expired)

Classified as flakes by:  Sarah Lee (QA Lead) · 09:22 UTC
Environment:              Staging (refreshed and ready)
────────────────────────────────────────────────────────
[ Trigger Rerun ]   [ Cancel ]
```

The Developer sees that all three failures are clearly infrastructure issues, not code defects.

---

**3. Developer clicks "Trigger Rerun".**

```
⟳  Rerun scheduled for 3 scripts on Staging.
   You'll be notified when complete — usually within 5 minutes.
```

The Developer closes the card and continues their other work.

---

**4. Bot notifies the Developer when the rerun finishes.**

```
✅  Rerun Complete — All 3 Scripts Passed
────────────────────────────────────────────────────────
Branch:    feature/checkout-v2
Result:    3/3 passed (0 failures)

Your pipeline is unblocked and has proceeded to the next stage.
[ View Results ]   [ View Pipeline Status ]
```

---

**5. Developer clicks "View Results" to confirm.**

The results card shows a simple pass table — no further action needed. The Developer's pipeline continues automatically.

---

## Flow 3: Receive and Act on a Defect Assignment (UC-D-03)

### Flow Summary

| Attribute | Detail |
|---|---|
| Initiator | Bot (proactive DM) |
| Channel | DM to Developer |
| Estimated time | 3–5 minutes to acknowledge; resolution time varies |
| Outcome | Defect acknowledged and owned, or reassigned, or disputed |

### Steps

**1. Developer receives a Teams DM from the bot.**

```
🐛  Defect Assigned to You
────────────────────────────────────────────────────────
Ticket:    PROJ-512
Title:     Checkout total wrong when stacking two discount codes
Priority:  High   |   Created: 26 Mar 2026, 02:19 UTC

The Defect Agent has linked this to your recent commits
in `checkout/pricing.py`.

[ View Defect ]
```

---

**2. Developer clicks "View Defect".**

```
PROJ-512 — Checkout total wrong when stacking two discount codes
──────────────────────────────────────────────────────────────────
What failed:
  TC-034 — Checkout with two active discount codes
  Step 5:  "Place Order" → Expected total: $72.50 · Got: $81.00

Error context:
  Applied codes: SAVE10 + NEWUSER
  Expected:      Both discounts applied   ($81.00 → $72.50)
  Actual:        Only SAVE10 applied      ($81.00 → $72.90 → $81.00)

Screenshot:     [checkout total mismatch — click to expand]

Likely cause:
  The second discount in `apply_discount_stack()` at line 112
  of `checkout/pricing.py` is being overwritten by the first.
  Commit: def4567 — "Refactor discount application logic"

[ Open in Jira ]
──────────────────────────────────────────────────────────────────
[ Acknowledge ]   [ Reassign ]   [ Dispute ]
```

---

**3. Developer reviews the detail.**

The code reference and commit match their recent work. The root cause analysis looks accurate. The Developer clicks **Acknowledge**.

---

**4. Bot confirms the acknowledgement.**

```
✓  PROJ-512 acknowledged by Marcus Lee.
   Status updated to "In Progress" in Jira.

When you're ready for a retest, click below.
[ Request Retest ]
```

The card remains open with the **Request Retest** button available for later use.

---

**5. Developer fixes the bug in their code, commits, and returns to Teams.**

---

**6. Developer clicks "Request Retest".**

```
Request Retest for PROJ-512?
The Tester will be notified that a fix is ready for verification.

Optional note to tester:
[ Fixed in commit g7h8i9j — adjusted discount stack logic.     ]

[ Cancel ]   [ Send Retest Request ]
```

Developer adds a note and clicks **Send Retest Request**.

---

**7. Bot confirms and notifies the Tester.**

```
✅  Retest requested.
Sarah Lee (QA Lead) has been notified.
You'll be notified when the retest result is available.
```

---

**8. After the retest passes, the bot notifies the Developer.**

```
✅  PROJ-512 — Retest Passed
────────────────────────────────────────────────────────
Verified by:   Sarah Lee (QA Lead)
Status:        Resolved in Jira

Great work — the defect is closed.
```

---

## Flow 4: Query the Bot for Build and Pipeline Status (UC-D-04)

### Flow Summary

| Attribute | Detail |
|---|---|
| Initiator | Developer (typed query) |
| Channel | `#dev-pipeline` or direct message to bot |
| Estimated time | Under 1 minute |
| Outcome | Developer gets current pipeline status; can take follow-up action |

### Steps

**1. Developer types a question in the `#dev-pipeline` channel.**

```
@Dev Bot what's the status of the build for feature/mfa-flow?
```

---

**2. Bot responds immediately with a structured status card.**

```
🔧  Pipeline Status — feature/mfa-flow
────────────────────────────────────────────────────────
Latest commit:   abc1234 — "Add OTP expiry validation"
Committed by:    Marcus Lee · 26 Mar 2026, 08:45 UTC

  Stage              Status         Duration
  ─────────────────────────────────────────
  Build              ✅ Passed       1m 12s
  Unit Tests         ✅ Passed       3m 40s
  Integration Tests  🔄 Running…    ~4m remaining
  Deploy to Staging  ⏳ Waiting

Overall:  In Progress — no blocking issues detected.
────────────────────────────────────────────────────────
[ View Full Pipeline ]   [ View Test Results ]
```

---

**3. Developer follows up.**

```
When did the last full test run finish on this branch?
```

---

**4. Bot answers the follow-up in the same thread.**

```
The last complete test run on feature/mfa-flow finished
25 Mar 2026 at 22:14 UTC.

  Result:  2 failures (both assigned, both In Progress)
  ─────────────────────────────────────────────────────
  PROJ-510   MFA timeout on slow network     → Alex Chen
  PROJ-511   OTP field missing on Safari     → Marcus Lee ← (you)

[ View PROJ-511 ]   [ View All Test Results ]
```

---

**5. Developer clicks "View PROJ-511" to jump into the defect detail.**

This transitions the Developer into Flow 3 (UC-D-03), starting at step 2 with the defect detail card already open.

---

## Open Questions

> The following items require confirmation from the Product Manager before implementation.

1. **Flow 1 — Draft PR target branch:** When the agent creates a draft PR with a suggested fix, does it target the Developer's feature branch, a new dedicated fix branch, or a fork? Who merges it, and what review/approval process applies?
2. **Flow 1 — "This is Wrong" feedback:** When the Developer rejects the AI fix suggestion, does the system attempt a second analysis, or is it marked for human investigation? What is the expected response time?
3. **Flow 2 — Rerun authorization scope:** Can a Developer trigger a rerun for another Developer's branch (e.g., if they are pairing), or is the rerun button scoped to the branch owner only?
4. **Flow 3 — Dispute resolution timeline:** When a Developer disputes the root cause analysis, how quickly should the re-analysis complete? Who is notified of the outcome, and is there a fallback if the agent cannot reach a conclusion?
5. **Flow 3 — Reassign picker:** When reassigning a defect, is the people list limited to team members in the current channel, or does it search the broader organization directory?
6. **Notification batching:** If multiple build failures occur on the same branch within a short window (e.g., rapid retry attempts), does the Developer receive a separate notification for each failure, or are they batched into a summary showing the most recent state with a count of prior failures?

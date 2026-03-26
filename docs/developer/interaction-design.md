# Developer Interaction Design

## Overview

This document defines the interaction design principles and specific UI patterns for the Developer experience on the Agentic SDLC platform in Microsoft Teams. Each section maps to a key moment in the Developer's user flows and explains both *what* the design should do and *why* that choice delivers the best experience.

The guiding philosophy for Developer interaction design:

> **Surface the answer, not the raw data.**
> Developers are busy and context-switching is expensive. Every interaction should hand the Developer a conclusion — not a log file to interpret.

---

## 1. Build Failure Notification Design

### 1.1 The Build Failure Alert Card

The build failure notification is the most time-sensitive alert the Developer receives. It must be designed to minimize the time between "I see there's a failure" and "I understand what failed and why."

**Why DM + channel?**
The Developer receives both a direct message and a channel post. The DM ensures personal awareness even if the Developer is not watching the shared channel. The channel post ensures the team is also aware. This redundancy is intentional for high-priority events.

**Card structure:**

```
[⚠️]  Build Failed — [Branch name]
──────────────────────────────────────────────────────────
Commit:   [Short hash] — "[Commit message]"
Stage:    [Which stage failed]
──────────────────────────────────────────────────────────
[1-line plain language summary of what failed]

[ View Details ]
```

**Design decisions:**

| Decision | Rationale |
|---|---|
| Show the commit message, not just the hash | The commit message is what the Developer remembers writing. It immediately tells them which change is implicated — a hash alone requires a mental lookup. |
| Show the failed stage (Build / Unit Tests / Integration) | This tells the Developer the type of failure before they open the details. A build failure means compilation; a unit test failure means logic. This shapes their mental model before they click. |
| One button: "View Details" | The notification's job is to alert, not to present choices. The Developer should not be asked to make a decision before they know what happened. |

### 1.2 The Failure Analysis Card

This is the core value-delivery card for the Developer. It must answer: *"What failed, why, and what should I do?"*

**Card structure:**

```
🔍  Build Failure Analysis
──────────────────────────────────────────────────────────
What failed:
  [Test name or build step, one line]
  [Error type + plain-language description]

Why it failed:
  [Agent's root cause inference — 1–3 sentences, plain language]

File / Line / Function:
  [Specific code location]

💡  Suggested Fix:
  [Diff-style code snippet or configuration change]
  - [old line]
  + [new line]

──────────────────────────────────────────────────────────
[ Apply Fix (Draft PR) ]   [ I'll Fix Manually ]   [ This is Wrong ]
```

**Design decisions:**

| Decision | Rationale |
|---|---|
| Separate "What failed" from "Why it failed" | These are two different cognitive tasks: understanding the symptom vs. understanding the cause. Combining them in one paragraph forces the Developer to do that separation themselves. |
| Show the code diff inline, not as an attachment | A diff shown directly in the card removes the need to open a separate file or PR. The Developer can evaluate the fix in seconds without switching context. |
| Three actions — not two | `Apply Fix` and `I'll Fix Manually` cover the two expected paths. `This is Wrong` is essential: it gives the Developer a way to signal that the AI analysis is incorrect, without just ignoring the card. This feedback improves the agent over time and prevents the Developer from feeling trapped by a bad suggestion. |
| "Apply Fix" is the primary button | The most efficient path (let the agent create the PR) is visually dominant. Developers who prefer to fix manually can still choose that path, but the default nudges toward the faster option. |

### 1.3 Framing the AI Suggestion

The suggested fix is presented as a *💡 suggestion*, not as *the answer*. This framing is deliberate.

**Why:**
If the system presents a fix as definitive ("The fix is: change `>=` to `>`"), the Developer is less likely to evaluate it critically. If the system presents it as a suggestion ("💡 Suggested Fix"), the Developer is prompted to apply judgment. A Developer who applies judgment and agrees with the suggestion is more likely to produce a correct fix than one who applies it blindly.

The `This is Wrong` button reinforces that the Developer's judgment takes precedence over the agent.

---

## 2. Draft PR Notification Design

### 2.1 Confirming the Draft PR Was Created

When the Developer clicks **Apply Fix**, the agent creates a draft PR. The Developer needs to know:
1. The PR was created successfully.
2. Where to find it.
3. What to do next.

```
✅  Draft PR Created
──────────────────────────────────────────────────────────
PR Title:   [Descriptive title based on the fix]
Branch:     fix/[commit-hash]-[short-description]
Target:     [Developer's feature branch]
Changes:    [N] file(s) · [N] line(s) changed

[ Open PR in GitHub ]   [ View Diff ]
```

**Design decisions:**

| Decision | Rationale |
|---|---|
| Show the PR title, not just a link | The Developer needs to confirm the PR describes the fix correctly. A title-only view catches misnamed PRs before the Developer opens a new tab. |
| Show branch name and target | The Developer needs to confirm the fix is targeting their branch, not main or another feature branch. |
| Two buttons: "Open PR" and "View Diff" | Some Developers prefer to see the diff before opening the PR in GitHub. Both paths are one click. |

### 2.2 Rebuild Notification

After the Developer merges the draft PR, the build reruns. The Developer is notified of the outcome without needing to watch the pipeline:

**Success:**
```
✅  Build Passed — [Branch name]
Fix verified. All [N] tests passing. Pipeline proceeding to [next stage].
[ View Pipeline Status ]
```

**Failure (fix did not resolve the issue):**
```
❌  Build Still Failing — [Branch name]
The suggested fix did not resolve the failure.

[ View New Analysis ]   [ I'll Fix Manually ]
```

**Design decision — offer a new analysis, not just an error:**
If the fix did not work, the worst outcome is leaving the Developer with only an error card. Offering "View New Analysis" immediately opens a new failure analysis with updated context. This keeps the Developer in a productive loop rather than sending them back to manual debugging.

---

## 3. Flaky Test Rerun Notification Design

### 3.1 Flake Classification Card

When failures are classified as environment flakes, the Developer needs to trust that classification before clicking **Trigger Rerun**. If they don't trust it, they won't click — they'll go investigate manually, which defeats the purpose.

**Design decisions to build trust:**

| Decision | Rationale |
|---|---|
| Show *who* classified the flakes (e.g., "Sarah Lee, QA Lead") | A human name is more trustworthy than "classified by system." The Developer knows they can ask Sarah if they have doubts. |
| Show *why* each failure was classified as a flake | "DNS resolution failure (test infra)" is specific evidence. "Environment issue" is vague. Specific reasons allow the Developer to evaluate the classification independently. |
| Show the environment status ("Staging refreshed and ready") | The Developer's implicit concern is: "If I rerun on the same broken environment, it'll fail again." Confirming the environment is ready addresses this directly. |

### 3.2 Rerun Status and Completion

When the rerun is in progress, the Developer should be able to close the card and continue working:

```
⟳  Rerun scheduled for [N] scripts on [Environment].
   You'll be notified when complete — usually within [N] minutes.
```

The phrase *"You'll be notified when complete"* gives the Developer explicit permission to move on. Without this, some Developers will watch the card waiting for it to update — an unnecessary interruption to their flow.

**Rerun completion card:**
```
✅  Rerun Complete — All [N] Scripts Passed
──────────────────────────────────────────────────────────
Branch:    [Branch name]
Result:    [N/N] passed   (0 failures)

Your pipeline is unblocked and has proceeded to [next stage].
[ View Results ]   [ View Pipeline Status ]
```

**Design decision — "Your pipeline is unblocked" as the headline:**
The Developer's primary concern is not the test result — it is whether they are blocked. Leading with the pipeline status (unblocked) answers the question they actually care about, before the test detail.

---

## 4. Defect Assignment Card Design

### 4.1 The DM Notification

The defect assignment DM must create appropriate urgency without causing alarm. The Developer needs to understand: this requires their attention, but they have the context they need.

```
🐛  Defect Assigned to You
──────────────────────────────────────────────────────────
Ticket:    [JIRA-ID]
Title:     [Defect title — plain language]
Priority:  [High / Critical / Medium]
Created:   [Timestamp]

The Defect Agent has linked this to your recent work in [file/component].

[ View Defect ]
```

**Design decisions:**

| Decision | Rationale |
|---|---|
| Include "linked to your recent work in [file]" | This pre-answers the Developer's first question: "Why was this assigned to me?" Without this, the Developer must investigate the assignment logic before they can engage with the defect itself. |
| Show priority in the notification, not just the detail | Priority determines whether the Developer should stop what they're doing now or address this later. It belongs in the first screen, not buried in details. |
| One button: "View Defect" | The notification should not present a decision before the Developer has seen the defect. Ask them to act after they have context. |

### 4.2 The Defect Detail Card

The defect detail card must answer, in order:
1. What exactly broke?
2. Where in the code?
3. What should I do about it?

**Card structure:**

```
[JIRA-ID]  [Defect title]
[Severity]  ·  [Priority]  ·  [Status]
──────────────────────────────────────────────────────────
What failed:
  [Test name] — [Step that failed]
  Expected: [expected result]     Got: [actual result]

Error context:
  [Relevant values, inputs, or state at point of failure]

Screenshot:   [Thumbnail]   (click to expand)

Likely cause (Agent inference):
  [Plain-language root cause, 1–2 sentences]
  [File + line + commit implicated]

──────────────────────────────────────────────────────────
[ Acknowledge ]   [ Reassign ]   [ Dispute ]   [ Open in Jira ]
```

**Design decisions:**

| Decision | Rationale |
|---|---|
| Show "Expected vs. Got" side by side | This is the most efficient format for communicating a mismatch. It mirrors how test assertions are written, which matches the Developer's mental model. |
| "Likely cause" framed as agent inference | Same as the fix suggestion — framing as inference invites judgment. Framing as fact discourages it. |
| Show the specific commit | The Developer needs to trace the defect back to their change. Including the commit hash makes this instant instead of requiring a git blame. |
| `Dispute` button alongside `Acknowledge` | If the assignment is incorrect, `Dispute` provides a legitimate path to push back. Without it, Developers either silently ignore incorrect assignments (leaving them unresolved) or spend time in back-channel conversations. |

### 4.3 Acknowledge → Request Retest Loop

After a Developer acknowledges a defect, the card must not go silent. The Developer needs a clear path to signal completion:

```
✓  [JIRA-ID] acknowledged by [Developer name].
   Status updated to "In Progress" in Jira.

When your fix is ready, request a retest:
[ Request Retest ]
```

**Design decision — leave the Retest button persistent:**
The Developer may fix the bug hours or days later. The **Request Retest** button must remain accessible from the card. This prevents the Developer from needing to find the original defect card or navigate to Jira to trigger the retest flow.

**Request Retest confirmation:**

```
Request Retest for [JIRA-ID]?
The QA Lead will be notified that a fix is ready for verification.

Note to tester (optional):
[ _________________________________ ]

[ Cancel ]   [ Send Retest Request ]
```

**Design decision — optional note field:**
The optional note allows the Developer to communicate context (e.g., which commit contains the fix, or what edge case was addressed). This reduces back-and-forth between Developer and Tester and accelerates the verification cycle.

---

## 5. Bot Query Response Design

### 5.1 Conversational Query Responses

When the Developer types a question (UC-D-04), the bot must respond in a format that is both human and structured. A wall of text is hard to scan. A pure table with no context is hard to interpret.

**The hybrid format:** Start with a structured data card for facts, followed by any follow-up action links.

```
[Card title — answering the question]
────────────────────────────────────
[Key data in table or labeled fields]
────────────────────────────────────
[Follow-up action links]
```

**Design decisions:**

| Decision | Rationale |
|---|---|
| Answer the exact question in the card title | *"Pipeline Status — feature/mfa-flow"* directly mirrors the Developer's question. Generic titles like *"Build Information"* require the Developer to confirm the card is about their query. |
| Show stage-level status in a table (Stage · Status · Duration) | Parallel stages are best understood as a grid, not a list. The table format lets the Developer see at a glance which stage is the bottleneck. |
| Include estimated completion time for in-progress stages | "~4 minutes remaining" reduces the Developer's need to re-query. Without it, they will ask again in 2 minutes. |
| Offer action links at the bottom | The bot's response should always end with a way to go deeper. "View Full Pipeline" and "View Test Results" turn a status query into a navigation hub. |

### 5.2 Follow-Up Question Handling

When the Developer asks a follow-up question in the same thread, the bot must respond in context — not as a fresh query.

**Good pattern:**
```
Developer: "When did the last test run finish on this branch?"
Bot: "The last complete test run on feature/mfa-flow finished
      25 Mar 2026 at 22:14 UTC.
      Result: 2 failures — both assigned to you. [View Defects]"
```

**Why "both assigned to you" instead of just listing them:**
Calling out the Developer's personal stake triggers engagement. A neutral "2 failures" is information. "2 failures — both assigned to you" is a call to action.

---

## 6. Loading States and Async Feedback

### 6.1 Immediate Button Feedback

Every button click must produce a visible response within 200ms — before the server responds. This is non-negotiable for maintaining trust in the UI.

**Pattern:**
- Button label changes to: *"⟳ [Verb]-ing…"* (e.g., *"⟳ Creating PR…"*, *"⟳ Scheduling rerun…"*)
- Button is disabled to prevent double-submission.

**Why 200ms is the threshold:**
Research consistently shows that responses under 200ms feel instantaneous. Responses between 200ms and 1s feel fast. Beyond 1s, users begin to wonder if the click registered. The immediate state change (even before the server confirms) keeps the user in the "feels fast" band.

### 6.2 Processing State Messages

For longer operations, the spinner message should give the Developer permission to move on:

```
⟳  Rerun scheduled — you'll be notified when complete.
   Usually around 5 minutes. You can close this and continue working.
```

The phrase *"You can close this and continue working"* is not just courtesy — it actively reduces the Developer's anxiety about whether they need to wait.

### 6.3 Completion Notification for Background Tasks

When a background task (rerun, PR creation, defect re-analysis) completes, the Developer is notified via a new bot message — not just an update to the original card. This ensures visibility even if the Developer has scrolled away.

**Why a new message, not just a card update?**
Teams does not surface card updates with the same visual prominence as new messages. A Developer who has navigated away from the channel will see a new message indicator (red badge) on the channel icon. They will not be alerted to a card that quietly updated.

---

## 7. Error and Exception Handling

### 7.1 Agent Error for Developer

When the agent cannot complete a task (e.g., cannot generate a fix suggestion, cannot schedule a rerun), the Developer receives an error card that prioritizes recovery:

```
❌  Could Not [Complete Action]
──────────────────────────────────────────────────────────
What happened:
  [One sentence — what the agent tried and why it failed]

What you can do:
  1. [Most likely recovery action]
  2. [Alternative if #1 doesn't work]
  3. Contact your platform admin if the problem continues.

Reference: [Error code]   |   Branch: [Branch name]

[ Retry ]   [ Contact Admin ]
```

**Design decisions:**

| Decision | Rationale |
|---|---|
| Always include a Retry button | Most agent failures are transient. A retry solves them. If the Developer has to manually re-trigger the action from scratch, they lose context and spend unnecessary effort. |
| No raw error output in the primary message | Stack traces and system error messages are not actionable for most Developers. They can request the full log via "Contact Admin." The primary card should give them enough to take the next step — nothing more. |
| Numbered recovery steps | Numbered steps create a clear decision tree. Paragraphs of explanation require more effort to extract an action from. |

### 7.2 Stale or Expired Cards

If a Developer tries to interact with a card that is no longer valid (e.g., clicking "Trigger Rerun" on a run that was already re-run by someone else), the bot must communicate clearly:

```
⚠️  This action is no longer available.
A rerun was already triggered by [Name] at [Timestamp].
[ View Current Results ]
```

**Never show a generic error like "Action failed."** The Developer should always understand *why* the action did not work.

---

## 8. Reducing Cognitive Load for Developers

### 8.1 The Developer Context Window

Developers are frequently in deep focus when they receive a notification. The interaction design must respect this:

- **Notifications are skimmable in 5 seconds.** If the key information cannot be read in 5 seconds, the headline is wrong.
- **Detail is available on demand.** The notification shows the minimum needed to decide whether to act now or later. Full detail requires a click.
- **One decision per card.** A card should not ask the Developer to make multiple decisions at once. If multiple decisions are needed (e.g., acknowledge a defect AND select an assignee), they are presented as separate sequential steps.

### 8.2 Terminology Consistency

All bot messages use the same term for the same concept:

| Concept | Consistent term |
|---|---|
| Running tests again | "Rerun" (not "retry," "re-execute," "re-trigger") |
| A broken test build | "Build failure" (not "pipeline failure," "CI failure," "test break") |
| Agent's root cause inference | "Likely cause" (not "root cause," "analysis," "diagnosis") |
| Creating a PR with a fix | "Draft PR" (not "patch," "hotfix branch," "fix PR") |

Terminology consistency reduces the cognitive overhead of mapping new terms to known concepts every time the Developer reads a card.

### 8.3 No Dead Ends

Every bot interaction — including error states — must end with at least one clear next step. A message that informs but provides no action path leaves the Developer without momentum and forces them to context-switch to figure out what to do.

---

## Open Questions

> The following items require confirmation from the Product Manager or Engineering before implementation.

1. **Fix suggestion confidence threshold:** Should the bot always show a fix suggestion, or only when the agent's confidence exceeds a threshold (e.g., 70%)? What happens at low confidence — is the suggestion shown with a caveat, or withheld?
2. **Draft PR permissions:** What repository permissions are required for the agent to create a draft PR? What happens if the Developer lacks the required permissions — does the agent fail gracefully, or fall back to showing the code diff for manual application?
3. **Card expiry:** Do interactive buttons (Acknowledge, Trigger Rerun, etc.) expire after a set period? If so, what period, and what does the expired state look like?
4. **DM vs. channel for defect assignments:** Should defect assignments always arrive as DMs, or should they also appear in the shared channel? If the channel post is visible, does the whole team see who was assigned?
5. **Multi-platform support:** Are Developers expected to interact with the bot from both desktop Teams and mobile Teams? The interactive card experience on mobile is significantly different — what is the minimum viable mobile experience?
6. **Bot query privacy:** When a Developer queries pipeline status in a shared channel, is the bot's response visible to all channel members or sent as a private reply? This affects how Developers frame queries when the response may reveal sensitive failure context (e.g., security-related test failures).

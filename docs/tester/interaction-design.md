# Tester Interaction Design

## Overview

This document defines the interaction design principles and specific UI patterns for the Tester experience on the Agentic SDLC platform in Microsoft Teams. Each section maps to a key moment in the Tester's user flows and explains both *what* the design should do and *why* that choice delivers the best user experience.

The guiding philosophy for Tester interaction design:

> **Minimize the effort required to make a confident decision.**
> The bot has already done the analysis. The Tester's job is to judge, not to investigate.

---

## 1. Notification Card Design

### 1.1 The First Card the Tester Sees

Every Tester flow begins with a bot-initiated notification card. This is the most important interaction moment — if the card fails to communicate clearly, the Tester will hesitate, disengage, or make a poor decision.

**Design principles:**
- **Signal before detail.** The card's headline must answer *"what happened and do I need to act?"* before any numbers or lists appear.
- **One primary action.** Even if multiple actions are available, one button should be visually dominant. The Tester should never feel uncertain about what to do next.
- **No jargon in the headline.** Use plain language for the first line. Technical details (run IDs, file paths, error codes) belong in the detail view, not the notification.

**Card structure:**

```
[Status icon]  [Plain-language headline]
──────────────────────────────────────────
[2–3 line summary — what happened, numbers, key context]

[Primary CTA button]   [Secondary CTA button]
```

**Why this works:** The Tester can decide in under 5 seconds whether this card needs their immediate attention or can wait. The structure mirrors how a person reads — top-down, headline first. The single dominant button eliminates decision paralysis.

### 1.2 Status Icons and Color Coding

All notification cards use a consistent icon and accent color system:

| Situation | Icon | Accent | Usage |
|---|---|---|---|
| Action required | 🔔 | Blue | Scenarios ready for review, sign-off required |
| Success / complete | ✅ | Green | Run complete (all passed), approval confirmed |
| Issues found | ⚠️ | Yellow | Run complete with failures, revision flagged |
| Failure / error | ❌ | Red | Build failed, agent error, critical defect |
| In progress | 🔄 | Grey | Agent processing, rerun running |

**Why this works:** Color and icon together create an immediate ambient signal before the Tester reads a word. The Tester can scan a busy Teams channel and identify which card needs attention without reading every line.

---

## 2. Scenario Review Card Design

### 2.1 List Layout for Scenario Review

When the Tester clicks **View Scenarios**, the list must be scannable, not overwhelming. The Tester needs to quickly assess whether each scenario is correct.

**Design decisions:**

| Decision | Rationale |
|---|---|
| Show all scenarios in a table (not collapsed individually) | The Tester needs to see the full picture at once to judge coverage. Requiring individual expansion hides information at the wrong moment. |
| Show: Title, Type, Priority — no more | Additional metadata (scenario ID, agent confidence, source requirement) adds noise at the review stage. It should be accessible on click, not shown by default. |
| Per-row inline actions: `Approve` and `Flag for Revision` | Placing actions at the row level reduces scrolling. The Tester can act on each scenario as they read it rather than building a mental list to act on later. |
| `Approve All` button with count in label | The Tester knows exactly how many will be approved. The count removes ambiguity and prevents accidental bulk actions. |

### 2.2 Flagging for Revision

When the Tester clicks **Flag for Revision**, a short text input appears inline without dismissing the card. This prevents context switching.

**Design decision — inline input vs. modal:**
An inline text field keeps the Tester's place in the list. A modal (popup) would interrupt their reading flow and require them to remember which scenario they were on. Inline editing is lower friction and reduces cognitive load.

**Input prompt guidance:**
The placeholder text in the input field is specific: *"Why should this scenario be revised? (e.g., out of scope, wrong expected result)"*

This is intentional — an empty field with no prompt causes the Tester to spend time thinking about format. A guided prompt reduces the time to submit from 30 seconds to 10.

### 2.3 Confirmation Before Bulk Approval

Any "Approve All" or "Approve [N]" action shows a confirmation step:

```
Approve 13 scenarios?
1 scenario has been flagged and will be excluded.
[ Cancel ]   [ Confirm Approval ]
```

**Design decision — why a confirmation step here?**
Approving scenarios is the gate that triggers downstream agents. It is a consequential action that cannot be undone without a new submission cycle. A brief confirmation aligns the Tester's intent with the system's action and prevents accidental approvals.

The confirmation should **not** include a lengthy summary — just the count and any exclusions. A two-line confirmation takes 3 seconds to read and is never skipped the way longer dialogs are.

---

## 3. Defect Review Card Design

### 3.1 Defect List Card

The defect list is the Tester's primary triage surface. Design priorities: clarity of severity, speed of action, and no unnecessary Jira context-switching.

**Design decisions:**

| Decision | Rationale |
|---|---|
| Sort defects by severity (Critical → High → Medium → Low) by default | Testers should triage the most important defects first. Sorting by creation time would bury critical issues. |
| Color-coded severity badges (●) inline with the defect title | Color gives the Tester an instant priority signal before reading the title. |
| Filter by severity available but not mandatory | Filters are useful for large defect sets (10+) but should not be required for normal use. Default sort handles most cases. |
| Each defect row is clickable — opens the detail card | The list row shows only the essential summary. Full detail is one click away, keeping the list compact. |

### 3.2 Defect Detail Card

The defect detail must answer three questions immediately:
1. What exactly failed?
2. Why did it fail?
3. Is this my responsibility to triage?

**Card structure:**

```
[Defect title and ticket ID]
[Severity · Status · Priority]
─────────────────────────────
What failed:    [Failed step + test name, one line]
Error:          [Plain-language error + raw code in secondary color]
Screenshot:     [Thumbnail — click to expand]
Likely cause:   [Agent's plain-language inference]
─────────────────────────────
[ Confirm & Assign ]  [ Mark as Flake ]  [ Mark as Duplicate ]  [ Open in Jira ]
```

**Design decisions:**

| Decision | Rationale |
|---|---|
| "Likely cause" is shown as agent inference, not as a fact | The agent's analysis can be wrong. Framing it as inference ("Likely cause:") signals to the Tester to apply judgment. Presenting it as fact would reduce critical thinking. |
| Screenshot shown as thumbnail (not full-size by default) | A full-size screenshot in the card would dominate the layout and push actions below the fold. The thumbnail signals that evidence exists; the Tester expands it if they need it. |
| "Open in Jira" is a secondary action, not the primary one | The goal is to keep the Tester in Teams. Jira is available for advanced cases but should not be the default path. Most triage actions can be completed without leaving Teams. |
| Three triage actions always visible | `Confirm & Assign`, `Mark as Flake`, and `Mark as Duplicate` cover the most common triage decisions. Making all three visible prevents the "I need to click somewhere to find the action I need" experience. |

### 3.3 Assign Action

When the Tester clicks **Confirm & Assign**, a people picker appears inline:

- Searches as the Tester types a name.
- Shows only team members in the current channel by default (configurable).
- After selection, the bot automatically updates Jira and sends a DM to the assigned developer.

**Design decision — why auto-notify?**
The Tester should not need to separately message the developer after assigning. Automating the notification removes a manual step and ensures the developer is aware immediately. The Tester can confirm who was notified via the bot's post-assignment confirmation message.

---

## 4. Loading States and Processing Feedback

### 4.1 Agent Processing Indicator

Whenever an action triggers an agent task (e.g., scenario revision, scenario generation, rerun), the bot must show an immediate response — even if the result is not yet ready.

**Pattern:**
- Within **200ms** of the Tester clicking an action: the button is replaced with a spinner and a short message.
- The spinner message uses active, specific language — not generic:
  - ✅ *"⟳ Revising scenario — usually takes 30 seconds…"*
  - ❌ *"Processing…"*

**Why this matters:**
If there is no feedback within 1–2 seconds of a click, users assume the click did not register and click again. This leads to duplicate submissions. Immediate spinner feedback prevents this and sets accurate expectations.

### 4.2 Long-Running Processing

If agent processing takes longer than expected:

| Elapsed time | Bot behavior |
|---|---|
| 0–30s | Spinner with estimated time |
| 30s–3min | Spinner updates to: *"Still working — this is taking a bit longer than usual."* |
| > 3min | New message posted: *"[Agent name] is taking longer than expected. We'll notify you when ready. You can close this and continue working."* |

**Design decision — give the Tester permission to leave:**
The Tester should never feel forced to watch a loading state. Explicitly telling them *"you can close this"* reduces anxiety and lets them context-switch confidently. They will be notified when results arrive.

### 4.3 Success State After Action

After the Tester completes an action (approve, assign, sign off), the card updates to show a clear success state:

```
✓  [Action] completed by [Name] · [Timestamp]
[Summary of what was approved / assigned / closed]
```

**Why a persistent success state:**
The success state should remain on the card permanently (or until the message is archived). Other team members reading the channel later need to know what decision was made, by whom, and when. Removing the success state or collapsing it would eliminate this team-visible audit trail.

---

## 5. Human Gate Design

### 5.1 Design Goals for Human Gates

A human gate is a point where the platform requires the Tester's explicit decision before agents proceed. The design of these gates is critical because:
- An incorrect approval can trigger unnecessary work.
- A delayed approval blocks the pipeline.
- An ambiguous gate UI causes hesitation and escalation.

Three design requirements for every human gate:

1. **The consequence must be visible.** The Tester must know what will happen after they approve or reject — not just what they are reviewing.
2. **The decision must require an active gesture.** No gate should proceed by default or inaction. The Tester must click a button.
3. **The decision is attributed and timestamped.** Who approved, and when, is always visible to the team.

### 5.2 Sign-Off Gate Card Design

The release sign-off gate (UC-T-03) is the highest-stakes gate in the Tester's workflow. Its design must inspire confidence, not anxiety.

**Design decisions:**

| Decision | Rationale |
|---|---|
| Show P1/P2 defect count prominently, with ✓ if zero | The most important go/no-go criterion is visible at a glance. The Tester should not need to search for this. |
| Show trend comparison vs. previous release | Context reduces uncertainty. Seeing "94% pass rate (↑ vs. v2.3.0 at 91%)" is more reassuring than "94% pass rate" in isolation. |
| Agent recommendation shown ("✅ Ready for release") | The agent synthesizes the data and offers a recommendation. The Tester still decides — but having a recommendation from the system reduces cognitive load. |
| Optional comment field on approval | Allows the Tester to record context for the audit log without requiring it. Most sign-offs will include a brief note. |
| "Block Release" button is visually secondary to "Approve Release" | The default, expected action (approve) should be easier to find. "Block Release" requires deliberate intent — it should not be accidentally clicked. |

---

## 6. Error and Exception Handling

### 6.1 Agent Error

When an agent fails to complete its task, the Tester receives a clear error card — never a silent failure.

```
❌  [Agent Name] — Could Not Complete
──────────────────────────────────────────────────────
What happened:
  The Test Generation Agent could not process scenario #7.
  Reason: The source requirement (PROJ-210) is no longer accessible.

What you can do:
  1. Check that PROJ-210 is still active in Jira.
  2. Re-submit the requirement once access is confirmed.
  3. Contact your platform admin if the problem persists.

Reference: ERR-TGA-4041   |   Run: RUN-2024-0091

[ Re-Submit ]   [ Contact Admin ]
```

**Design decisions:**

| Decision | Rationale |
|---|---|
| Plain-language "What happened" — no raw stack traces | Testers are not engineers. Raw error output causes confusion and erodes trust in the platform. The technical reference code (ERR-TGA-4041) is available for support escalation but is not the primary message. |
| Numbered recovery steps | A numbered list makes the next action immediately actionable. A paragraph of explanation requires more cognitive effort to extract an action from. |
| At least one recovery action button | The Tester should never be left with only an error and no path forward. Even "Contact Admin" is better than nothing. |

### 6.2 Partial Success

When an operation partially succeeds (e.g., 13 of 14 scenarios generated, 1 failed):

```
⚠️  Scenario Generation Partially Complete
──────────────────────────────────────────────────────
13 of 14 scenarios were generated successfully.
1 scenario could not be generated: "MFA with expired token"
Reason: Insufficient context in the source requirement.

You can proceed with the 13 available scenarios.

[ Review 13 Scenarios ]   [ Retry Failed Scenario ]
```

**Design decision — never block on partial failure:**
The Tester should always be able to proceed with what worked. Blocking the entire flow because one item failed creates frustration disproportionate to the issue. Offer the partial result and a targeted retry — not a full restart.

---

## 7. Reducing Cognitive Load

### 7.1 Progressive Disclosure

Each card shows only what the Tester needs for the current decision. Additional detail is accessible on click, not shown by default.

| Card level | What is shown |
|---|---|
| Notification card | Headline, 2–3 line summary, primary action button |
| List card | Title, type, priority, per-row action buttons |
| Detail card | Full context needed to make the decision |

This prevents information overload. A Tester who sees 40 lines of data on the first card will disengage. A Tester who sees a 3-line summary with a clear button will act.

### 7.2 Consistent Button Labels

Button labels always use verb + noun format and reflect the exact consequence of the action:

| ✅ Good | ❌ Avoid |
|---|---|
| Approve Scenarios | OK |
| Confirm & Assign | Submit |
| Flag for Revision | Edit |
| Block Release | Cancel |

Vague labels like "OK" or "Submit" require the user to remember what they are confirming. Specific labels make the action self-documenting.

### 7.3 No Dead Ends

Every bot message — including error states — must end with at least one action the Tester can take. A message with only information and no button implies the Tester should know what to do next, which increases cognitive load and causes hesitation.

---

## Open Questions

> The following items require confirmation from the Product Manager or Engineering before implementation.

1. **Adaptive Card limits:** Microsoft Teams Adaptive Cards have a payload size limit (~28KB). Long scenario lists may exceed this. What is the fallback — a Teams Tab, a web view, or paginated cards?
2. **Card interactivity expiry:** Do action buttons (Approve, Assign, Approve All, etc.) remain interactive indefinitely, or should they expire after a set time (e.g., 24–48 hours) to prevent stale decisions? If they expire, what does the expired state look like and how is the user guided to resubmit?
3. **People picker scope:** When assigning a defect to a developer, should the picker show all Azure AD users, only channel members, or only a curated team roster?
4. **Agent recommendation display:** In the sign-off gate (Section 5.2), should the agent's "Ready for release" recommendation always be shown, or only when confidence exceeds a threshold? Who is accountable if the recommendation is wrong?
5. **Accessibility:** Should the status icon + color system be supplemented with text labels to meet WCAG contrast requirements for users with color vision deficiencies?

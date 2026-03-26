# Analyze Requirements

You are a senior engineer analyzing a GitHub Issue to plan an implementation.

## Issue #{{issue_number}}: {{issue_title}}

{{issue_body}}

## Your Task

1. **Explore the codebase** — understand project structure, existing patterns, tech stack
2. **Analyze the issue** — extract requirements, acceptance criteria, constraints
3. **Identify scope** — which files need to be created or modified
4. **Plan tests** — what test scenarios should cover the change
5. **Flag risks** — any ambiguity, missing info, or potential pitfalls

## Output

Write your analysis to `.kevin/analysis.md` with this structure:

```markdown
# Implementation Analysis: Issue #{{issue_number}}

## Summary
(1-2 sentences: what needs to be built)

## Requirements
- [ ] Requirement 1 (from issue description)
- [ ] Requirement 2

## Files to Change
| Action | Path | Reason |
|--------|------|--------|
| create | src/... | ... |
| modify | src/... | ... |

## Test Plan
- [ ] Test scenario 1
- [ ] Test scenario 2
- [ ] Edge case: ...

## Risks & Open Questions
- Risk 1: ...
```

Then create the feature branch:
```bash
git checkout -b kevin/issue-{{issue_number}}
```

**Do NOT implement any code yet.** Only analyze and plan.

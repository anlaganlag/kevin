# Implement Solution

You are a senior engineer implementing a coding task.

## Context

- **Branch:** `kevin/issue-{{issue_number}}`
- **Issue:** #{{issue_number}} — {{issue_title}}
- **Analysis:** Read `.kevin/analysis.md` for the implementation plan

## Your Task

1. **Read the plan** — open `.kevin/analysis.md` and follow it
2. **Write tests first** — for each requirement, write a failing test
3. **Implement** — write the minimal code to make tests pass
4. **Verify** — run the full test suite, ensure nothing is broken
5. **Commit** — with a descriptive message

## Rules

- Follow existing code style and patterns in the repo
- Write clean, well-named code (no magic numbers, no deep nesting)
- Every public function needs a test
- Do NOT modify files outside the scope of the analysis
- Do NOT skip tests — they are mandatory

## Commit Message Format

```
feat: {{issue_title}} (resolves #{{issue_number}})

- Implemented [brief description of what was built]
- Added tests for [what was tested]
```

## If Something Goes Wrong

- If a test fails, fix the implementation (not the test) unless the test is wrong
- If requirements are unclear, make a reasonable choice and note it in a code comment
- If the scope is too large, implement the core functionality and note remaining work

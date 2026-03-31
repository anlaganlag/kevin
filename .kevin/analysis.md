# Issue #68: summarize_validation helper

## Summary
Add `summarize_validation(results: list[dict]) -> dict` to `kevin/blueprint_compiler.py`.
Aggregates multiple validator results into a summary dict with total, passed, failed, pass_rate.

## TDD Strategy

### Test Cases (RED phase)
1. Empty list → `{"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}`
2. All passed → pass_rate = 1.0
3. All failed → pass_rate = 0.0
4. Mixed → correct counts and ratio
5. Single item passed
6. Single item failed

### Files
- Test: `kevin/tests/test_blueprint_compiler.py` (append new test class)
- Impl: `kevin/blueprint_compiler.py` (add function)

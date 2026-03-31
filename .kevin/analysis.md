# Issue #67: format_duration helper

## Summary
Add `format_duration(seconds: float) -> str` to `kevin/state.py` that converts seconds into human-readable "Xh Xm Xs" format.

## Files to modify
- `kevin/state.py` — add `format_duration()` function
- `kevin/tests/test_state_format_duration.py` — new test file

## Test scenarios
- 65.3 → "1m 5s"
- 3661 → "1h 1m 1s"
- 0.5 → "0s"
- 0 → "0s"
- 3600 → "1h 0m 0s"
- 59 → "59s"
- negative → "0s"
- hours only: 7200 → "2h 0m 0s"

## Risks
- None — pure function, no side effects.

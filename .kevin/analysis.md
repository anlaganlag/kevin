# Issue #64: Unit Tests for kevin/intent.py

## Summary
Add comprehensive unit tests for the `classify()` function in `kevin/intent.py`.

## Files Modified
- `kevin/tests/test_intent.py` — expanded from ~35 lines to ~468 lines

## Test Scenarios Covered (61 tests total)

| Category | Tests | Description |
|----------|-------|-------------|
| Intent dataclass | 2 | Immutability, field access |
| Exact match | 6 + 10 parametrized | Direct label->blueprint lookup, all DEFAULT_INTENT_MAP entries |
| Alias fallback | 5 + 5 parametrized | Alias resolution, preference over exact, dangling alias, all DEFAULT_LABEL_ALIASES |
| Unknown/no match | 4 | Missing kevin label, kevin-only, empty labels, unknown labels |
| Default params | 4 | None->default fallback, custom map/alias override |
| RL edge cases | 12 | Duplicates, large lists, ambiguous keys, transitive chains, empty/whitespace, case sensitivity |
| Adversarial/security | 10 | SQL injection, XSS, template injection, path traversal, null byte, unicode, regex chars |
| Performance | 5 | <1ms typical, <10ms for 500 labels, <5ms for 1000-entry map |

## Risks
- None identified. All 61 tests pass deterministically.

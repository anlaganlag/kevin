# FIP: Unit Tests for kevin/intent.py classify()

**Issue**: #64
**Blueprint**: bp_test_unit
**Branch**: kevin/issue-64
**Status**: Complete

---

## 1. Feature Overview

Add comprehensive unit tests for `kevin/intent.py`'s `classify()` function, covering all classification paths: exact match, alias fallback, and unknown label handling.

## 2. Architecture Analysis

### Target Module
- **File**: `kevin/intent.py` (62 lines)
- **Function**: `classify(labels, intent_map, label_aliases) -> Intent | None`
- **Dependencies**: `kevin.config` (DEFAULT_INTENT_MAP, DEFAULT_LABEL_ALIASES, KEVIN_TRIGGER_LABEL)

### Classification Logic
1. Guard: requires `KEVIN_TRIGGER_LABEL` ("kevin") in label list
2. Pass 1: exact match — iterate `intent_map` keys, first hit wins → `confidence="exact"`
3. Pass 2: alias fallback — resolve via `label_aliases`, look up canonical in `intent_map` → `confidence="alias"`
4. No match → `None`

### Architecture Compliance
- Pure function, no side effects — safe to test in isolation
- Uses `dataclass(frozen=True)` for `Intent` — immutable return type
- Default parameters use `or` pattern (`mapping = intent_map or DEFAULT_INTENT_MAP`) — falsy values (empty dict) fall back to defaults

## 3. Technical Design

### Test Strategy (Quality Assurance Expert)

| Category | Count | Purpose |
|----------|-------|---------|
| Intent dataclass | 2 | Immutability, field access |
| Exact match | 6 + 10 parametrized | Direct label→blueprint lookup, all DEFAULT_INTENT_MAP entries |
| Alias fallback | 5 + 5 parametrized | Alias resolution, preference order, dangling alias, all DEFAULT_LABEL_ALIASES |
| Unknown/no match | 4 | Missing kevin label, kevin-only, empty labels, unknown labels |
| Default params | 4 | None→default fallback, custom map/alias override |
| RL edge cases | 12 | Duplicates, large lists, ambiguous keys, transitive chains, empty/whitespace, case sensitivity |
| Adversarial/security | 10 | SQL injection, XSS, template injection, path traversal, null byte, unicode, regex chars |
| Performance | 5 | <1ms typical, <10ms for 500 labels, <5ms for 1000-entry map |
| **Total** | **61** | |

### Test File
- **Path**: `kevin/tests/test_intent.py` (468 lines)
- **Framework**: pytest
- **Fixtures**: Isolated `TEST_INTENT_MAP` and `TEST_ALIASES` — tests don't depend on production config changes

### Design Decisions (Architecture Expert)
1. **Isolated fixtures over production config**: Tests use `TEST_INTENT_MAP` / `TEST_ALIASES` for deterministic behavior; parametrized tests verify all production defaults separately
2. **No mocking needed**: `classify()` is a pure function — no I/O, no state, no boundaries to mock
3. **Parametrized coverage**: `@pytest.mark.parametrize` ensures every entry in `DEFAULT_INTENT_MAP` and `DEFAULT_LABEL_ALIASES` is tested without manual case duplication

### Risk Assessment (R&D Leader)
- **Risk**: None. Pure function tests, no external dependencies, deterministic execution
- **Feasibility**: Verified — all 61 tests pass in 0.03s
- **Backward compatibility**: No changes to source code; test-only addition

## 4. Implementation Summary

### Files Changed
| File | Action | Lines |
|------|--------|-------|
| `kevin/tests/test_intent.py` | Created/expanded | 468 |
| `.kevin/analysis.md` | Created | 24 |
| `.kevin/fip.md` | Created | (this file) |

### Task Breakdown

| # | Task | Status | Dependency |
|---|------|--------|------------|
| T1 | Analyze `classify()` logic and identify test scenarios | Done | — |
| T2 | Implement exact match tests | Done | T1 |
| T3 | Implement alias fallback tests | Done | T1 |
| T4 | Implement unknown/no-match tests | Done | T1 |
| T5 | Implement default parameter tests | Done | T1 |
| T6 | Implement RL edge case tests | Done | T2-T5 |
| T7 | Implement adversarial/security tests | Done | T2-T5 |
| T8 | Implement performance tests | Done | T2-T5 |
| T9 | Verify all tests pass | Done | T2-T8 |
| T10 | Create FIP document | Done | T9 |
| T11 | Create PR | Done | T10 |

### Acceptance Criteria Verification
- [x] Covers exact match scenario (TestClassifyExactMatch: 16 tests)
- [x] Covers alias fallback scenario (TestClassifyAliasFallback: 10 tests)
- [x] Covers unknown label scenario (TestClassifyUnknownLabel: 4 tests)
- [x] Test file: `kevin/tests/test_intent.py`
- [x] pytest passes: 61/61 in 0.03s

## 5. Deployment

- No deployment needed — test-only change
- No infrastructure changes
- No monitoring changes
- CI will automatically run `pytest kevin/tests/test_intent.py` on PR

## 6. Architecture Compliance Report

| Check | Result |
|-------|--------|
| No breaking changes | Pass — test-only addition |
| Follows existing patterns | Pass — AAA pattern, describe blocks, parametrized |
| Backward compatible | Pass — no source changes |
| Consistent with project conventions | Pass — Chinese comments in analysis, English in tests |

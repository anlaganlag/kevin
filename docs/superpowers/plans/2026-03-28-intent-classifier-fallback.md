# Intent Classifier Fallback & Friendly Error Notification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an Issue has common GitHub labels (e.g. `enhancement`, `bug`) but no Kevin-specific task-type label, auto-map them to the correct blueprint instead of crashing — and when all classification fails, send a clear error message back to Teams.

**Architecture:** Add a `DEFAULT_LABEL_ALIASES` dict that maps common GitHub labels to Kevin task-type labels. The `classify()` function gains a second-pass alias lookup with `confidence="alias"`. The workflow YAML is fixed so failure notifications actually reach Teams.

**Tech Stack:** Python 3.11, pytest, GitHub Actions YAML

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `kevin/config.py` | Modify | Add `DEFAULT_LABEL_ALIASES` constant |
| `kevin/intent.py` | Modify | Add alias fallback in `classify()` |
| `kevin/cli.py` | Modify | Improve error message on classification failure |
| `.github/workflows/kevin.yaml` | Modify | Fix Teams failure notification + capture stderr |
| `kevin/tests/test_intent.py` | Modify | Add alias and error-path tests |

---

### Task 1: Add Label Aliases to Config

**Files:**
- Modify: `kevin/config.py:12-24`
- Test: `kevin/tests/test_intent.py`

- [ ] **Step 1: Write the failing test for alias resolution**

```python
# In kevin/tests/test_intent.py — add to TestClassify class

def test_should_match_coding_task_when_enhancement_alias(self) -> None:
    """enhancement is a common GitHub label — should alias to coding-task."""
    result = classify(["kevin", "enhancement"], DEFAULT_INTENT_MAP)
    assert result is not None
    assert result.blueprint_id == "bp_coding_task.1.0.0"
    assert result.matched_label == "enhancement"
    assert result.confidence == "alias"

def test_should_match_coding_task_when_bug_alias(self) -> None:
    result = classify(["kevin", "bug"], DEFAULT_INTENT_MAP)
    assert result is not None
    assert result.blueprint_id == "bp_coding_task.1.0.0"
    assert result.confidence == "alias"

def test_should_match_coding_task_when_feature_alias(self) -> None:
    result = classify(["kevin", "feature"], DEFAULT_INTENT_MAP)
    assert result is not None
    assert result.blueprint_id == "bp_coding_task.1.0.0"
    assert result.confidence == "alias"

def test_should_prefer_exact_match_over_alias(self) -> None:
    """Exact match takes priority even if alias is also present."""
    result = classify(["kevin", "enhancement", "code-review"], DEFAULT_INTENT_MAP)
    assert result is not None
    assert result.blueprint_id == "bp_code_review.1.0.0"
    assert result.confidence == "exact"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/randy/Documents/code/AgenticSDLC && python -m pytest kevin/tests/test_intent.py -v`
Expected: 4 new tests FAIL (alias not implemented yet)

- [ ] **Step 3: Add `DEFAULT_LABEL_ALIASES` to config.py**

In `kevin/config.py`, add after `DEFAULT_INTENT_MAP` (after line 21):

```python
# Aliases: common GitHub labels → Kevin task-type labels.
# These are checked AFTER exact intent_map match fails.
DEFAULT_LABEL_ALIASES: dict[str, str] = {
    "enhancement": "coding-task",
    "bug": "coding-task",
    "feature": "coding-task",
    "documentation": "coding-task",
    "refactor": "coding-task",
    "testing": "coding-task",
}
```

- [ ] **Step 4: Commit config change**

```bash
git add kevin/config.py
git commit -m "feat: add DEFAULT_LABEL_ALIASES for common GitHub labels"
```

---

### Task 2: Add Alias Fallback to `classify()`

**Files:**
- Modify: `kevin/intent.py:23-48`
- Modify: `kevin/config.py` (import)

- [ ] **Step 1: Update `classify()` to accept and use aliases**

Replace the `classify` function in `kevin/intent.py`:

```python
from kevin.config import DEFAULT_INTENT_MAP, DEFAULT_LABEL_ALIASES, KEVIN_TRIGGER_LABEL


def classify(
    labels: list[str],
    intent_map: dict[str, str] | None = None,
    label_aliases: dict[str, str] | None = None,
) -> Intent | None:
    """Return the Intent for a set of issue labels, or None if not a Kevin issue.

    Rules:
    1. Issue must have the KEVIN_TRIGGER_LABEL ("kevin").
    2. First matching label (by intent_map key order) wins → confidence="exact".
    3. If no exact match, check label_aliases → confidence="alias".
    4. If nothing matches, returns None.
    """
    if KEVIN_TRIGGER_LABEL not in labels:
        return None

    mapping = intent_map or DEFAULT_INTENT_MAP
    aliases = label_aliases or DEFAULT_LABEL_ALIASES
    label_set = set(labels)

    # Pass 1: exact match against intent_map keys
    for label, blueprint_id in mapping.items():
        if label in label_set:
            return Intent(
                blueprint_id=blueprint_id,
                matched_label=label,
                confidence="exact",
            )

    # Pass 2: alias match — resolve alias to intent_map key, then look up blueprint
    for label in labels:
        canonical = aliases.get(label)
        if canonical and canonical in mapping:
            return Intent(
                blueprint_id=mapping[canonical],
                matched_label=label,
                confidence="alias",
            )

    return None
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /Users/randy/Documents/code/AgenticSDLC && python -m pytest kevin/tests/test_intent.py -v`
Expected: ALL tests PASS (including the 4 new alias tests)

- [ ] **Step 3: Commit**

```bash
git add kevin/intent.py
git commit -m "feat: classify() alias fallback for common GitHub labels"
```

---

### Task 3: Improve CLI Error Message on Classification Failure

**Files:**
- Modify: `kevin/cli.py:155-158`

- [ ] **Step 1: Update the error message in `_cmd_run_inner`**

Replace lines 155-158 in `kevin/cli.py`:

```python
        intent = classify(issue.labels, config.intent_map)
        if intent is None:
            supported = ", ".join(config.intent_map.keys())
            from kevin.config import DEFAULT_LABEL_ALIASES
            alias_list = ", ".join(DEFAULT_LABEL_ALIASES.keys())
            _err(f"Cannot classify issue #{args.issue}.")
            _err(f"  Labels found: {issue.labels}")
            _err(f"  Supported task-type labels: {supported}")
            _err(f"  Auto-mapped aliases: {alias_list}")
            _err("Add one of the above labels to the issue and re-trigger.")
            return 1
```

- [ ] **Step 2: Also log the confidence level when alias matches**

Replace line 160 in `kevin/cli.py`:

```python
        blueprint_id = intent.blueprint_id
        confidence_tag = f" [{intent.confidence}]" if intent.confidence != "exact" else ""
        _log(config, f"  Intent: {blueprint_id} (matched: {intent.matched_label}{confidence_tag})")
```

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/randy/Documents/code/AgenticSDLC && python -m pytest kevin/tests/ -v`
Expected: ALL tests PASS

- [ ] **Step 4: Commit**

```bash
git add kevin/cli.py
git commit -m "fix: show supported labels and aliases on classification failure"
```

---

### Task 4: Fix Workflow Teams Failure Notification

**Files:**
- Modify: `.github/workflows/kevin.yaml:91-149`

- [ ] **Step 1: Capture Kevin stderr for the error payload**

After the "Run Kevin" step (step 7), add stderr capture. Replace step 7 (lines 91-112) with:

```yaml
      # 7. Run Kevin (capture stderr for error reporting)
      - name: Run Kevin
        id: kevin-run
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          ANTHROPIC_AUTH_TOKEN: ${{ secrets.ANTHROPIC_API_KEY }}
          ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
          ANTHROPIC_MODEL: ${{ secrets.ANTHROPIC_MODEL }}
          ANTHROPIC_SMALL_FAST_MODEL: ${{ secrets.ANTHROPIC_SMALL_FAST_MODEL }}
          ANTHROPIC_DEFAULT_HAIKU_MODEL: ${{ secrets.ANTHROPIC_DEFAULT_HAIKU_MODEL }}
          ANTHROPIC_DEFAULT_SONNET_MODEL: ${{ secrets.ANTHROPIC_DEFAULT_SONNET_MODEL }}
          ANTHROPIC_DEFAULT_OPUS_MODEL: ${{ secrets.ANTHROPIC_DEFAULT_OPUS_MODEL }}
          CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: ${{ secrets.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC }}
          API_TIMEOUT_MS: "600000"
          GH_TOKEN: ${{ secrets.CHECKOUT_TOKEN }}
          TEAMS_BOT_URL: ${{ secrets.TEAMS_BOT_URL }}
        working-directory: agentic-sdlc
        run: |
          python -m kevin run \
            --issue ${{ github.event.issue.number }} \
            --repo ${{ github.repository }} \
            --target-repo ${{ github.workspace }}/target-repo \
            --verbose 2> >(tee /tmp/kevin-stderr.log >&2)
```

- [ ] **Step 2: Fix the failure notification step to use captured error**

Replace step 9 (lines 132-149) with:

```yaml
      # 9. Notify Teams — Run Failed (with captured error details)
      - name: Notify Teams — Run Failed
        if: failure()
        env:
          TEAMS_BOT_URL: ${{ secrets.TEAMS_BOT_URL }}
        run: |
          if [ -z "$TEAMS_BOT_URL" ]; then
            echo "::warning::TEAMS_BOT_URL not set, skipping notification"
            exit 0
          fi
          ERROR_MSG="Check workflow logs for details"
          if [ -f /tmp/kevin-stderr.log ]; then
            ERROR_MSG=$(tail -5 /tmp/kevin-stderr.log | tr '\n' ' ' | head -c 400)
          fi
          # Use jq-free JSON escaping for the error string
          ERROR_JSON=$(echo "$ERROR_MSG" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")
          curl -s -X POST "$TEAMS_BOT_URL/api/notify" \
            -H "Content-Type: application/json" \
            -d "{
              \"event\": \"run_failed\",
              \"run_id\": \"gh-${{ github.run_id }}\",
              \"issue_number\": ${{ github.event.issue.number }},
              \"issue_title\": ${{ toJSON(github.event.issue.title) }},
              \"repo\": \"${{ github.repository }}\",
              \"status\": \"failed\",
              \"error\": $ERROR_JSON,
              \"logs_url\": \"${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}\",
              \"blocks\": []
            }" || echo "::warning::Teams notification failed (non-fatal)"
```

Key changes:
- Removed `if: failure() && env.TEAMS_BOT_URL != ''` → now checks `$TEAMS_BOT_URL` inside the script (avoids GitHub Actions env scope issue)
- Removed `-f` flag from curl (was causing silent failure on HTTP errors)
- Captures last 5 lines of stderr as error detail
- Added `logs_url` field so Teams card can link to the workflow run

- [ ] **Step 3: Apply same fix to step 6 and step 8 (Run Started / Run Completed)**

Replace step 6 `if:` condition (line 74):

```yaml
        if: always()
```

And add the guard inside the script:

```yaml
        run: |
          if [ -z "$TEAMS_BOT_URL" ]; then exit 0; fi
          curl -s -X POST "$TEAMS_BOT_URL/api/notify" \
```

Replace step 8 `if:` condition (line 116):

```yaml
        if: success()
```

And add the same guard inside the script.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/kevin.yaml
git commit -m "fix: Teams failure notification — capture stderr, fix env scope"
```

---

### Task 5: Verify End-to-End

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/randy/Documents/code/AgenticSDLC && python -m pytest kevin/tests/ -v`
Expected: ALL tests PASS

- [ ] **Step 2: Dry-run test with enhancement label**

Verify the alias mapping works by checking the classify function:

```bash
cd /Users/randy/Documents/code/AgenticSDLC
python -c "
from kevin.intent import classify
from kevin.config import DEFAULT_INTENT_MAP

# Should now succeed with alias
result = classify(['kevin', 'enhancement'], DEFAULT_INTENT_MAP)
print(f'Result: {result}')
assert result is not None
assert result.confidence == 'alias'
print('OK: enhancement alias works')

# Should still fail with unknown label
result2 = classify(['kevin', 'unknown-label'], DEFAULT_INTENT_MAP)
assert result2 is None
print('OK: unknown label correctly returns None')
"
```

Expected: Both assertions pass.

- [ ] **Step 3: Final commit (if any remaining changes)**

```bash
git status
# If clean, skip. Otherwise:
git add -A
git commit -m "test: verify intent alias fallback end-to-end"
```

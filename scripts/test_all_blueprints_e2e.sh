#!/usr/bin/env bash
# scripts/test_all_blueprints_e2e.sh
#
# E2E test: dispatch all 5 blueprints SEQUENTIALLY, poll until complete or timeout.
# Serial execution avoids Qianfan API rate limiting.
# ⚠️  This triggers real GitHub Actions runs and consumes API credits.
#
# Usage: bash scripts/test_all_blueprints_e2e.sh

set -uo pipefail

API_KEY="${EXECUTOR_API_KEY:-r8im8LdRShJ8Ze6ujaGV5b7CI/5YO0Mr3f7r8ZFkqsI=}"
BASE="${EXECUTOR_BASE_URL:-https://yldkolafvxgolwtthguo.supabase.co/functions/v1}"
TARGET_REPO="${TARGET_REPO:-centific-cn/kevin-test-target}"
TARGET_REF="${TARGET_REF:-main}"

BP_IDS=(
  "bp_coding_task.1.0.0"
  "bp_code_review.1.0.0"
  "bp_backend_coding_tdd_automation.1.0.0"
  "bp_function_implementation_fip_blueprint.1.0.0"
  "bp_test_feature_comprehensive_testing.1.0.0"
)
BP_INSTRUCTIONS=(
  "Add a /ping endpoint that returns pong true"
  "Review the existing codebase for code quality issues"
  "Add a utility function to validate email addresses with TDD"
  "Implement a string reverse function with edge case handling"
  "Write comprehensive tests for the existing utility functions"
)

PASS=0
FAIL=0
TOTAL=${#BP_IDS[@]}

echo "============================================"
echo " All Blueprints E2E Test (Sequential)"
echo " Target: ${TARGET_REPO} @ ${TARGET_REF}"
echo "============================================"
echo ""

poll_until_done() {
  local run_id="$1"
  local max_polls=40  # 40 * 15s = 10 min
  for i in $(seq 1 $max_polls); do
    sleep 15
    local resp
    resp=$(curl -s "${BASE}/status/${run_id}" -H "Authorization: Bearer ${API_KEY}")
    local status
    status=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
    echo "    [$(( i * 15 ))s] status=${status}"
    if [ "$status" = "completed" ] || [ "$status" = "failed" ]; then
      echo "$status"
      return
    fi
  done
  echo "timeout"
}

for idx in "${!BP_IDS[@]}"; do
  bp="${BP_IDS[$idx]}"
  instruction="${BP_INSTRUCTIONS[$idx]}"
  echo "--- [$((idx+1))/${TOTAL}] ${bp} ---"

  # Dispatch
  RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE}/execute" \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"blueprint_id\":\"${bp}\",\"instruction\":\"${instruction}\",\"context\":{\"repo\":\"${TARGET_REPO}\",\"ref\":\"${TARGET_REF}\"}}")

  HTTP_CODE=$(echo "$RESPONSE" | tail -1)
  BODY=$(echo "$RESPONSE" | sed '$d')

  if [ "$HTTP_CODE" != "202" ]; then
    FAIL=$((FAIL + 1))
    echo "  ✗ dispatch failed (HTTP ${HTTP_CODE}): ${BODY}"
    echo ""
    continue
  fi

  RUN_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
  echo "  dispatched → run_id: ${RUN_ID}"
  echo "  polling..."

  # Poll until done
  FINAL_STATUS=$(poll_until_done "$RUN_ID")

  if [ "$FINAL_STATUS" = "completed" ]; then
    PASS=$((PASS + 1))
    echo "  ✓ PASSED"
  else
    FAIL=$((FAIL + 1))
    echo "  ✗ FAILED (status: ${FINAL_STATUS})"
  fi
  echo ""
done

echo "============================================"
echo " Results: ${PASS}/${TOTAL} passed, ${FAIL} failed"
echo "============================================"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1

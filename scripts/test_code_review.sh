#!/usr/bin/env bash
# Test bp_code_review via Edge Function
# Usage: bash scripts/test_code_review.sh <pr_number> [issue_number]

set -uo pipefail

API_KEY="${EXECUTOR_API_KEY:-r8im8LdRShJ8Ze6ujaGV5b7CI/5YO0Mr3f7r8ZFkqsI=}"
BASE="${EXECUTOR_BASE_URL:-https://yldkolafvxgolwtthguo.supabase.co/functions/v1}"
PR="${1:-}"
ISSUE="${2:-999}"

if [ -z "$PR" ]; then
  echo "Usage: bash scripts/test_code_review.sh <pr_number> [issue_number]"
  echo "Example: bash scripts/test_code_review.sh 24"
  exit 1
fi

echo "=== Dispatch bp_code_review (PR #${PR}, issue #${ISSUE}) ==="
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE}/execute" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"blueprint_id\": \"bp_code_review.1.0.0\",
    \"instruction\": \"Review PR #${PR} for code quality\",
    \"context\": {
      \"repo\": \"centific-cn/kevin-test-target\",
      \"ref\": \"main\",
      \"pr_number\": \"${PR}\",
      \"issue_number\": \"${ISSUE}\"
    }
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
echo "HTTP ${HTTP_CODE}"
echo "$BODY" | python3 -m json.tool

if [ "$HTTP_CODE" != "202" ]; then
  echo "FAIL: dispatch failed"
  exit 1
fi

RUN_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo ""
echo "=== Polling status (run_id: ${RUN_ID}) ==="

for i in $(seq 1 40); do
  sleep 15
  RESP=$(curl -s "${BASE}/status/${RUN_ID}" -H "Authorization: Bearer ${API_KEY}")
  STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
  echo "  [$(( i * 15 ))s] status=${STATUS}"

  if [ "$STATUS" = "completed" ]; then
    echo ""
    echo "SUCCESS"
    echo "$RESP" | python3 -m json.tool
    exit 0
  fi
  if [ "$STATUS" = "failed" ]; then
    echo ""
    echo "FAILED"
    echo "$RESP" | python3 -m json.tool
    exit 1
  fi
done

echo "TIMEOUT"
exit 1

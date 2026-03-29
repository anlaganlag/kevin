#!/usr/bin/env bash
# scripts/test_executor_e2e.sh
#
# Smoke test for Executor as a Service.
# Prerequisites:
#   - EXECUTOR_API_KEY env var set
#   - EXECUTOR_BASE_URL env var set (e.g. https://<project>.supabase.co/functions/v1)
#
# Usage: ./scripts/test_executor_e2e.sh

set -euo pipefail

: "${EXECUTOR_API_KEY:?Set EXECUTOR_API_KEY}"
: "${EXECUTOR_BASE_URL:?Set EXECUTOR_BASE_URL}"

echo "=== Step 1: POST /execute ==="
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${EXECUTOR_BASE_URL}/execute" \
  -H "Authorization: Bearer ${EXECUTOR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_id": "bp_coding_task.1.0.0",
    "instruction": "Add a /health endpoint that returns {\"status\": \"ok\"}",
    "context": {"repo": "centific-cn/kevin-test-target", "ref": "main"}
  }')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

echo "HTTP $HTTP_CODE"
echo "$BODY" | python3 -m json.tool

if [ "$HTTP_CODE" != "202" ]; then
  echo "FAIL: Expected 202, got $HTTP_CODE"
  exit 1
fi

RUN_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "run_id: $RUN_ID"

echo ""
echo "=== Step 2: Poll GET /status ==="
for i in $(seq 1 60); do
  sleep 10
  STATUS_RESP=$(curl -s "${EXECUTOR_BASE_URL}/status/${RUN_ID}" \
    -H "Authorization: Bearer ${EXECUTOR_API_KEY}")
  STATUS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "  [$i] status=$STATUS"

  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    echo ""
    echo "=== Final Result ==="
    echo "$STATUS_RESP" | python3 -m json.tool
    exit 0
  fi
done

echo "TIMEOUT: Run did not complete in 10 minutes"
exit 1

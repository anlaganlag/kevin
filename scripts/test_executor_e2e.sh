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

echo "=== Step 0a: Verify idempotency key deduplication ==="
IDEM_KEY="e2e-test-$(date +%s)"
IDEM_RESP1=$(curl -s -w "\n%{http_code}" -X POST "${EXECUTOR_BASE_URL}/execute" \
  -H "Authorization: Bearer ${EXECUTOR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"blueprint_id\": \"bp_coding_task.1.0.0\", \"instruction\": \"idempotency test\", \"idempotency_key\": \"${IDEM_KEY}\"}")
IDEM_CODE1=$(echo "$IDEM_RESP1" | tail -1)
IDEM_RUN1=$(echo "$IDEM_RESP1" | head -1 | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")

IDEM_RESP2=$(curl -s -w "\n%{http_code}" -X POST "${EXECUTOR_BASE_URL}/execute" \
  -H "Authorization: Bearer ${EXECUTOR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"blueprint_id\": \"bp_coding_task.1.0.0\", \"instruction\": \"idempotency test\", \"idempotency_key\": \"${IDEM_KEY}\"}")
IDEM_CODE2=$(echo "$IDEM_RESP2" | tail -1)
IDEM_RUN2=$(echo "$IDEM_RESP2" | head -1 | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")

if [ "$IDEM_RUN1" = "$IDEM_RUN2" ] && [ "$IDEM_CODE2" = "200" ]; then
  echo "PASS: Idempotency key returned same run_id ($IDEM_RUN1)"
else
  echo "FAIL: Expected same run_id, got $IDEM_RUN1 vs $IDEM_RUN2 (codes: $IDEM_CODE1, $IDEM_CODE2)"
fi

echo ""
echo "=== Step 0b: Verify unknown blueprint rejected ==="
REJECT_RESP=$(curl -s -w "\n%{http_code}" -X POST "${EXECUTOR_BASE_URL}/execute" \
  -H "Authorization: Bearer ${EXECUTOR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"blueprint_id": "bp_nonexistent.1.0.0", "instruction": "test"}')
REJECT_CODE=$(echo "$REJECT_RESP" | tail -1)
if [ "$REJECT_CODE" = "400" ]; then
  echo "PASS: Unknown blueprint correctly rejected (HTTP 400)"
else
  echo "FAIL: Expected 400 for unknown blueprint, got $REJECT_CODE"
  exit 1
fi

echo ""
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

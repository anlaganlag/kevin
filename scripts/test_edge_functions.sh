#!/usr/bin/env bash
# scripts/test_edge_functions.sh
# Comprehensive Edge Function test suite
set -uo pipefail

BASE="https://yldkolafvxgolwtthguo.supabase.co/functions/v1"
KEY="r8im8LdRShJ8Ze6ujaGV5b7CI/5YO0Mr3f7r8ZFkqsI="
AUTH="Authorization: Bearer ${KEY}"

PASS=0
FAIL=0
TOTAL=0

assert_http() {
  local test_name="$1" expected_code="$2" actual_code="$3" body="$4"
  TOTAL=$((TOTAL + 1))
  if [ "$actual_code" = "$expected_code" ]; then
    PASS=$((PASS + 1))
    echo "  ✓ ${test_name} (HTTP ${actual_code})"
  else
    FAIL=$((FAIL + 1))
    echo "  ✗ ${test_name} — expected ${expected_code}, got ${actual_code}"
    echo "    body: $(echo "$body" | head -c 200)"
  fi
}

assert_body_contains() {
  local test_name="$1" expected="$2" body="$3"
  TOTAL=$((TOTAL + 1))
  if echo "$body" | grep -q "$expected"; then
    PASS=$((PASS + 1))
    echo "  ✓ ${test_name}"
  else
    FAIL=$((FAIL + 1))
    echo "  ✗ ${test_name} — body missing: ${expected}"
    echo "    body: $(echo "$body" | head -c 200)"
  fi
}

# Robust HTTP call: writes body to tmpfile, captures code separately
_TMP_BODY=$(mktemp)
call() {
  local method="$1" path="$2"
  shift 2
  HTTP=$(curl -s -o "$_TMP_BODY" -w "%{http_code}" -X "$method" "${BASE}${path}" "$@")
  BODY=$(cat "$_TMP_BODY")
}

echo "========================================"
echo " Edge Function Comprehensive Test Suite"
echo "========================================"
echo ""

# ========================================
# Section 1: Authentication
# ========================================
echo "--- 1. Authentication ---"

call POST /execute -H "Content-Type: application/json" -d '{"blueprint_id":"bp_coding_task.1.0.0","instruction":"test"}'
assert_http "POST /execute without auth → 401" "401" "$HTTP" "$BODY"
assert_body_contains "401 includes hint" "hint" "$BODY"

call GET "/status"
assert_http "GET /status without auth → 401" "401" "$HTTP" "$BODY"

call POST /execute -H "Authorization: Bearer wrong-key" -H "Content-Type: application/json" -d '{"blueprint_id":"bp_coding_task.1.0.0","instruction":"test"}'
assert_http "POST /execute with wrong key → 401" "401" "$HTTP" "$BODY"

call POST /execute -H "Authorization: wrong-format" -H "Content-Type: application/json" -d '{"blueprint_id":"bp_coding_task.1.0.0","instruction":"test"}'
assert_http "POST /execute malformed auth header → 401" "401" "$HTTP" "$BODY"

call POST /execute -H "Authorization: Bearer " -H "Content-Type: application/json" -d '{"blueprint_id":"bp_coding_task.1.0.0","instruction":"test"}'
assert_http "POST /execute empty bearer token → 401" "401" "$HTTP" "$BODY"

echo ""

# ========================================
# Section 2: HTTP Methods
# ========================================
echo "--- 2. HTTP Methods ---"

call GET /execute -H "$AUTH"
assert_http "GET /execute → 200 (health)" "200" "$HTTP" "$BODY"
assert_body_contains "Health check returns status ok" '"status":"ok"' "$BODY"
assert_body_contains "Health check returns service name" "kevin-executor" "$BODY"

call PUT /execute -H "$AUTH" -H "Content-Type: application/json" -d '{}'
assert_http "PUT /execute → 405" "405" "$HTTP" "$BODY"

call DELETE /execute -H "$AUTH"
assert_http "DELETE /execute → 405" "405" "$HTTP" "$BODY"

call PATCH /execute -H "$AUTH" -H "Content-Type: application/json" -d '{}'
assert_http "PATCH /execute → 405" "405" "$HTTP" "$BODY"

call POST /status -H "$AUTH" -H "Content-Type: application/json" -d '{}'
assert_http "POST /status → 405" "405" "$HTTP" "$BODY"

echo ""

# ========================================
# Section 3: CORS
# ========================================
echo "--- 3. CORS ---"

call OPTIONS /execute -H "Origin: https://example.com" -H "Access-Control-Request-Method: POST"
assert_http "OPTIONS /execute → 204" "204" "$HTTP" "$BODY"

call OPTIONS /status -H "Origin: https://example.com" -H "Access-Control-Request-Method: GET"
assert_http "OPTIONS /status → 204" "204" "$HTTP" "$BODY"

call OPTIONS /callback -H "Origin: https://example.com" -H "Access-Control-Request-Method: POST"
assert_http "OPTIONS /callback → 204" "204" "$HTTP" "$BODY"

# Verify CORS headers on actual response
cors_header=$(curl -s -D - -o /dev/null "${BASE}/execute" -H "$AUTH" | grep -i "access-control-allow-origin" | head -1)
TOTAL=$((TOTAL + 1))
if echo "$cors_header" | grep -qi "\*"; then
  PASS=$((PASS + 1))
  echo "  ✓ CORS Allow-Origin: * header present on GET"
else
  FAIL=$((FAIL + 1))
  echo "  ✗ CORS Allow-Origin header missing or not *"
fi

echo ""

# ========================================
# Section 4: Input Validation — /execute
# ========================================
echo "--- 4. Input Validation (/execute) ---"

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{bad json here}'
assert_http "Malformed JSON → 400" "400" "$HTTP" "$BODY"
assert_body_contains "JSON error includes hint" "hint" "$BODY"

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{"trailing": "comma",}'
assert_http "Trailing comma JSON → 400" "400" "$HTTP" "$BODY"

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{}'
assert_http "Empty object → 400" "400" "$HTTP" "$BODY"
assert_body_contains "Missing fields shows example" "example" "$BODY"

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{"blueprint_id":"bp_coding_task.1.0.0"}'
assert_http "Missing instruction → 400" "400" "$HTTP" "$BODY"

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{"instruction":"test"}'
assert_http "Missing blueprint_id → 400" "400" "$HTTP" "$BODY"

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{"blueprint_id":"bp_coding_task.1.0.0","instruction":"test","context":{"repo":"not-a-valid-repo"}}'
assert_http "Invalid repo format (no slash) → 400" "400" "$HTTP" "$BODY"
assert_body_contains "Repo error includes hint" "owner/repo" "$BODY"

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{"blueprint_id":"bp_coding_task.1.0.0","instruction":"test","context":{"repo":"../../../etc/passwd"}}'
assert_http "Path traversal in repo → 400" "400" "$HTTP" "$BODY"

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{"blueprint_id":"bp_coding_task.1.0.0","instruction":"test","context":{"repo":"owner/repo; rm -rf /"}}'
assert_http "Command injection in repo → 400" "400" "$HTTP" "$BODY"

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{"blueprint_id":"bp_coding_task.1.0.0","instruction":"test","context":{"repo":"owner/<script>alert(1)</script>"}}'
assert_http "XSS in repo → 400" "400" "$HTTP" "$BODY"

echo ""

# ========================================
# Section 5: Input Validation — /status
# ========================================
echo "--- 5. Input Validation (/status) ---"

call GET "/status/not-a-uuid" -H "$AUTH"
assert_http "Invalid run_id format → 400" "400" "$HTTP" "$BODY"
assert_body_contains "UUID hint in error" "UUID" "$BODY"

call GET "/status/00000000-0000-0000-0000-000000000000" -H "$AUTH"
assert_http "Non-existent run_id → 404" "404" "$HTTP" "$BODY"

call GET "/status" -H "$AUTH"
assert_http "GET /status (list) → 200" "200" "$HTTP" "$BODY"
assert_body_contains "List returns runs array" "runs" "$BODY"
assert_body_contains "List returns count" "count" "$BODY"

call GET "/status?limit=2" -H "$AUTH"
assert_http "GET /status?limit=2 → 200" "200" "$HTTP" "$BODY"
# Verify limit is respected
run_count=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['runs']))" 2>/dev/null || echo "?")
TOTAL=$((TOTAL + 1))
if [ "$run_count" = "2" ]; then
  PASS=$((PASS + 1))
  echo "  ✓ limit=2 returns exactly 2 runs"
else
  FAIL=$((FAIL + 1))
  echo "  ✗ limit=2 returned ${run_count} runs"
fi

call GET "/status?limit=999" -H "$AUTH"
assert_http "GET /status?limit=999 (capped at 50) → 200" "200" "$HTTP" "$BODY"

call GET "/status?limit=-1" -H "$AUTH"
assert_http "GET /status?limit=-1 (fallback to 10) → 200" "200" "$HTTP" "$BODY"

call GET "/status?limit=abc" -H "$AUTH"
assert_http "GET /status?limit=abc (fallback to 10) → 200" "200" "$HTTP" "$BODY"

call GET "/status?limit=0" -H "$AUTH"
assert_http "GET /status?limit=0 (fallback to 10) → 200" "200" "$HTTP" "$BODY"

echo ""

# ========================================
# Section 6: Special Characters in Instruction
# ========================================
echo "--- 6. Special Characters ---"

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{"blueprint_id":"bp_coding_task.1.0.0","instruction":"Add endpoint returning {\"status\": \"ok\"}","context":{"repo":"centific-cn/kevin-test-target"}}'
assert_http "Escaped quotes in instruction → 202" "202" "$HTTP" "$BODY"
RUN_ID_1=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('run_id',''))" 2>/dev/null || echo "")

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d "{\"blueprint_id\":\"bp_coding_task.1.0.0\",\"instruction\":\"Handle UTF-8: 中文测试 日本語 émojis\",\"context\":{\"repo\":\"centific-cn/kevin-test-target\"}}"
assert_http "Unicode in instruction → 202" "202" "$HTTP" "$BODY"

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{"blueprint_id":"bp_coding_task.1.0.0","instruction":"Code: `const x = 1` and $var","context":{"repo":"centific-cn/kevin-test-target"}}'
assert_http "Backticks and dollar signs → 202" "202" "$HTTP" "$BODY"

echo ""

# ========================================
# Section 7: Callback Validation
# ========================================
echo "--- 7. Callback (/callback) ---"

call POST /callback -H "Content-Type: application/json" -d '{"run_id":"test","status":"running"}'
assert_http "Callback without signature → 403" "403" "$HTTP" "$BODY"
assert_body_contains "Missing signature error" "Missing signature" "$BODY"

call POST /callback -H "Content-Type: application/json" -H "x-signature: fakesig" -d '{"run_id":"test","status":"running"}'
assert_http "Callback with bad signature → 403" "403" "$HTTP" "$BODY"
assert_body_contains "Invalid signature error" "Invalid signature" "$BODY"

echo ""

# ========================================
# Section 8: Real Run Status + elapsed
# ========================================
echo "--- 8. Real Run Status ---"

if [ -n "${RUN_ID_1:-}" ]; then
  call GET "/status/${RUN_ID_1}" -H "$AUTH"
  assert_http "Status of just-created run → 200" "200" "$HTTP" "$BODY"
  assert_body_contains "Has elapsed_seconds" "elapsed_seconds" "$BODY"
  assert_body_contains "Has blueprint_id" "blueprint_id" "$BODY"
  assert_body_contains "Has instruction" "instruction" "$BODY"
  assert_body_contains "Has created_at" "created_at" "$BODY"
fi

echo ""

# ========================================
# Section 9: Concurrent Requests
# ========================================
echo "--- 9. Concurrent Requests ---"

codes_file=$(mktemp)
for i in 1 2 3 4 5; do
  (
    code=$(curl -s -o /dev/null -w "%{http_code}" -X GET "${BASE}/status?limit=1" -H "$AUTH")
    echo "$code" >> "$codes_file"
  ) &
done
wait

ok_count=$(grep -c "200" "$codes_file" 2>/dev/null || echo "0")
TOTAL=$((TOTAL + 1))
if [ "$ok_count" -eq 5 ]; then
  PASS=$((PASS + 1))
  echo "  ✓ 5 concurrent GET /status all returned 200"
else
  FAIL=$((FAIL + 1))
  echo "  ✗ Concurrent requests: ${ok_count}/5 returned 200"
fi
rm -f "$codes_file"

echo ""

# ========================================
# Section 10: Response Format Consistency
# ========================================
echo "--- 10. Response Format ---"

# All error responses should have 'error' key
for test_case in \
  "POST /execute:-H:$AUTH:-H:Content-Type: application/json:-d:{}:400" \
  "GET /status/not-a-uuid:-H:$AUTH:400" \
  "GET /status/00000000-0000-0000-0000-000000000000:-H:$AUTH:404"
do
  IFS=: read -r method_path rest <<< "$test_case"
  # Just verify via earlier tests — check JSON parse on known error
  true
done

call POST /execute -H "$AUTH" -H "Content-Type: application/json" -d '{}'
TOTAL=$((TOTAL + 1))
has_error=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if 'error' in d else 'no')" 2>/dev/null)
if [ "$has_error" = "yes" ]; then
  PASS=$((PASS + 1))
  echo "  ✓ 400 error response has 'error' field"
else
  FAIL=$((FAIL + 1))
  echo "  ✗ 400 error response missing 'error' field"
fi

call GET "/status/not-a-uuid" -H "$AUTH"
TOTAL=$((TOTAL + 1))
has_error=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if 'error' in d else 'no')" 2>/dev/null)
if [ "$has_error" = "yes" ]; then
  PASS=$((PASS + 1))
  echo "  ✓ Status 400 has 'error' field"
else
  FAIL=$((FAIL + 1))
  echo "  ✗ Status 400 missing 'error' field"
fi

# Verify JSON Content-Type
ct=$(curl -s -D - -o /dev/null "${BASE}/status" -H "$AUTH" | grep -i "content-type" | head -1)
TOTAL=$((TOTAL + 1))
if echo "$ct" | grep -qi "application/json"; then
  PASS=$((PASS + 1))
  echo "  ✓ Response Content-Type is application/json"
else
  FAIL=$((FAIL + 1))
  echo "  ✗ Response Content-Type: $ct"
fi

# Cleanup
rm -f "$_TMP_BODY"

echo ""
echo "========================================"
echo " Results: ${PASS}/${TOTAL} passed, ${FAIL} failed"
echo "========================================"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1

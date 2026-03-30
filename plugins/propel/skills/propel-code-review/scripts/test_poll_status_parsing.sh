#!/usr/bin/env bash
# Tests for the review polling status extraction logic.
#
# Validates that the sanitize-then-parse approach correctly handles:
# 1. Clean JSON responses
# 2. JSON with unescaped control characters (tabs, newlines, NUL bytes)
# 3. Non-JSON / empty responses
# 4. Max poll guard
#
# Usage: ./scripts/test_poll_status_parsing.sh

set -uo pipefail

PASS=0
FAIL=0

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    echo "  PASS: $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label — expected [$expected], got [$actual]"
    FAIL=$((FAIL + 1))
  fi
}

# -------------------------------------------------------------------
# extract_status: the exact logic from the fixed SKILL.md polling loop
# -------------------------------------------------------------------
extract_status() {
  printf '%s' "$1" | tr -d '\000-\037' | jq -r '.status // empty' 2>/dev/null
}

# extract_status_file: same logic but reads from a file, for cases where
# the payload contains NUL bytes that bash variables cannot hold.
extract_status_file() {
  tr -d '\000-\037' <"$1" | jq -r '.status // empty' 2>/dev/null
}

echo "=== Test Group 1: Clean JSON ==="

STATUS=$(extract_status '{"status":"completed","comments":[]}')
assert_eq "completed status" "completed" "$STATUS"

STATUS=$(extract_status '{"status":"failed","error":{"code":"generation_failed"}}')
assert_eq "failed status" "failed" "$STATUS"

STATUS=$(extract_status '{"status":"running"}')
assert_eq "running status" "running" "$STATUS"

STATUS=$(extract_status '{"status":"queued"}')
assert_eq "queued status" "queued" "$STATUS"

echo ""
echo "=== Test Group 2: JSON with unescaped control characters ==="

# Tab (0x09) inside a string value — the exact error from the reported bug
RESP_WITH_TAB=$(printf '{"status":"completed","comments":[{"message":"line1\tline2"}]}')
STATUS=$(extract_status "$RESP_WITH_TAB")
assert_eq "tab in message field" "completed" "$STATUS"

# Newline (0x0A) inside a string value
RESP_WITH_NEWLINE=$(printf '{"status":"failed","comments":[{"message":"line1\nline2"}]}')
STATUS=$(extract_status "$RESP_WITH_NEWLINE")
assert_eq "newline in message field" "failed" "$STATUS"

# Carriage return (0x0D) inside a string value
RESP_WITH_CR=$(printf '{"status":"completed","comments":[{"message":"line1\rline2"}]}')
STATUS=$(extract_status "$RESP_WITH_CR")
assert_eq "carriage return in message field" "completed" "$STATUS"

# Multiple control chars
RESP_MULTI=$(printf '{"status":"completed","comments":[{"message":"a\tb\nc\rd"}]}')
STATUS=$(extract_status "$RESP_MULTI")
assert_eq "multiple control chars in message" "completed" "$STATUS"

# NUL byte (0x00) — bash variables strip NULs, so write to a temp file
# and use extract_status_file to test the real byte sequence.
NUL_FILE=$(mktemp)
printf '{"status":"completed","comments":[{"message":"a\x00b"}]}' >"$NUL_FILE"
STATUS=$(extract_status_file "$NUL_FILE")
rm -f "$NUL_FILE"
assert_eq "NUL byte in message field" "completed" "$STATUS"

echo ""
echo "=== Test Group 3: Malformed / empty responses ==="

STATUS=$(extract_status "")
assert_eq "empty response" "" "$STATUS"

STATUS=$(extract_status "not json at all")
assert_eq "non-JSON response" "" "$STATUS"

STATUS=$(extract_status '{"no_status_field": true}')
assert_eq "missing status field" "" "$STATUS"

STATUS=$(extract_status "<html>502 Bad Gateway</html>")
assert_eq "HTML error page" "" "$STATUS"

echo ""
echo "=== Test Group 4: Max poll guard ==="

# Simulate the max poll loop logic
MAX_POLLS=3
POLL_COUNT=0
EXITED_WITH_TIMEOUT=false
while true; do
  POLL_COUNT=$((POLL_COUNT + 1))
  if [ "$POLL_COUNT" -gt "$MAX_POLLS" ]; then
    EXITED_WITH_TIMEOUT=true
    break
  fi
  # Simulate always-running response
  STATUS=$(extract_status '{"status":"running"}')
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
done
assert_eq "max poll guard triggers" "true" "$EXITED_WITH_TIMEOUT"
assert_eq "poll count at exit" "4" "$POLL_COUNT"

echo ""
echo "=== Results ==="
echo "Passed: $PASS"
echo "Failed: $FAIL"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi

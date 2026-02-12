#!/bin/bash
# Test the srt-only kernel prototype
# Usage: bash test_kernel.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=19880
PASS=0
FAIL=0

# Start kernel in srt sandbox (background)
srt --settings "$SCRIPT_DIR/srt-config.json" \
    python3 "$SCRIPT_DIR/kernel.py" $PORT &
KERNEL_PID=$!
sleep 1

cleanup() {
    kill $KERNEL_PID 2>/dev/null || true
    wait $KERNEL_PID 2>/dev/null || true
    echo ""
    echo "Results: $PASS passed, $FAIL failed"
    if [ $FAIL -gt 0 ]; then exit 1; fi
}
trap cleanup EXIT

assert_contains() {
    local label="$1" response="$2" expected="$3"
    if echo "$response" | grep -qF "$expected"; then
        echo "  PASS: $label"
        PASS=$((PASS+1))
    else
        echo "  FAIL: $label (expected '$expected' in '$response')"
        FAIL=$((FAIL+1))
    fi
}

post() {
    curl -s -X POST "http://127.0.0.1:$PORT$1" \
         -H "Content-Type: application/json" -d "$2"
}

get() {
    curl -s "http://127.0.0.1:$PORT$1"
}

echo "=== srt-only kernel prototype tests ==="

# Test 1: health check
echo "Test 1: Health check"
R=$(get "/health")
assert_contains "health" "$R" '"status": "ok"'

# Test 2: exec and state persistence
echo "Test 2: Exec + state persistence"
R=$(post "/exec" '{"code": "x = 42"}')
assert_contains "exec x=42" "$R" '"vars"'
assert_contains "x in vars" "$R" '"x"'

R=$(post "/exec" '{"code": "y = x + 1"}')
assert_contains "y depends on x" "$R" '"y"'

# Test 3: /vars listing
echo "Test 3: Variable listing"
R=$(get "/vars")
assert_contains "x listed" "$R" '"name": "x"'
assert_contains "y listed" "$R" '"name": "y"'

# Test 4: /var/:name
echo "Test 4: Get single variable"
R=$(get "/var/x")
assert_contains "x=42" "$R" '42'
R=$(get "/var/y")
assert_contains "y=43" "$R" '43'

# Test 5: error handling
echo "Test 5: Error handling"
R=$(post "/exec" '{"code": "1/0"}')
assert_contains "division error" "$R" "ZeroDivisionError"

# Test 6: file write to workspace (allowed)
echo "Test 6: File write to allowed workspace"
R=$(post "/exec" '{"code": "open(\"/Users/quartershots/Source/rlm-sandbox/research/srt-prototype/workspace/test.txt\", \"w\").write(\"hello\")"}')
assert_contains "write ok" "$R" '"output"'

# Test 7: file write outside workspace (blocked by srt)
echo "Test 7: File write outside workspace (should fail)"
R=$(post "/exec" '{"code": "open(\"/tmp/evil.txt\", \"w\").write(\"bad\")"}')
assert_contains "write blocked" "$R" "PermissionError"

# Test 8: network access (blocked by srt)
echo "Test 8: Network access (should fail)"
R=$(post "/exec" '{"code": "import urllib.request; urllib.request.urlopen(\"https://example.com\")"}')
assert_contains "network blocked" "$R" "Error"

# Test 9: reset
echo "Test 9: Reset clears state"
R=$(post "/reset" '{}')
assert_contains "reset ok" "$R" '"status": "ok"'
R=$(get "/vars")
assert_contains "vars empty" "$R" '[]'

# Test 10: read sensitive path (blocked by srt)
echo "Test 10: Read sensitive path (should fail)"
R=$(post "/exec" '{"code": "import os; os.listdir(os.path.expanduser(\"~/.ssh\"))"}')
assert_contains "ssh blocked" "$R" "PermissionError"

echo ""
echo "=== done ==="

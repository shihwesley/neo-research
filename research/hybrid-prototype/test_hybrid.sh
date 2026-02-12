#!/bin/bash
# Test the hybrid prototype: Docker kernel + srt-wrapped "MCP server" (simulated)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8080
PASS=0
FAIL=0

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

echo "=== Hybrid prototype tests ==="

# Step 1: Build and start Docker kernel
echo "Building Docker image..."
STARTED=$(date +%s)
docker build -t rlm-hybrid-test "$SCRIPT_DIR" -q 2>&1
echo "Starting container..."
docker run -d --name rlm-hybrid-test \
    -p 18080:8080 \
    --dns 0.0.0.0 \
    --memory 512m \
    --cpus 1 \
    rlm-hybrid-test
BUILT=$(date +%s)
echo "  Docker build+start: $((BUILT-STARTED))s"

sleep 2

# Step 2: Test kernel from host (simulates unsandboxed MCP server)
echo ""
echo "Test 1: Host can reach Docker kernel"
R=$(curl -s http://127.0.0.1:18080/health)
assert_contains "health" "$R" '"status": "ok"'

echo "Test 2: Exec via Docker kernel"
R=$(curl -s -X POST http://127.0.0.1:18080/exec -H "Content-Type: application/json" -d '{"code":"x = 42"}')
assert_contains "exec x=42" "$R" '"x"'

echo "Test 3: State persists in Docker kernel"
R=$(curl -s -X POST http://127.0.0.1:18080/exec -H "Content-Type: application/json" -d '{"code":"y = x + 1"}')
assert_contains "y depends on x" "$R" '"y"'

echo "Test 4: Vars listing"
R=$(curl -s http://127.0.0.1:18080/vars)
assert_contains "x listed" "$R" '"name": "x"'

# Step 3: Test srt-wrapped "MCP server" can reach Docker kernel
echo ""
echo "Test 5: srt-wrapped process can reach Docker kernel"
R=$(srt --settings "$SCRIPT_DIR/mcp-srt-config.json" -c "python3 -c '
import urllib.request, json
req = urllib.request.Request(\"http://127.0.0.1:18080/vars\")
resp = urllib.request.urlopen(req)
print(resp.read().decode())
'" 2>&1)
assert_contains "srt->docker" "$R" '"name": "x"'

# Step 4: Test srt-wrapped process CANNOT reach external
echo "Test 6: srt-wrapped process cannot reach external"
R=$(srt --settings "$SCRIPT_DIR/mcp-srt-config.json" -c "python3 -c '
import urllib.request
try:
    urllib.request.urlopen(\"https://example.com\")
    print(\"FAIL: should have been blocked\")
except Exception as e:
    print(f\"BLOCKED: {e}\")
'" 2>&1)
assert_contains "external blocked" "$R" "BLOCKED"

# Step 5: Test srt-wrapped process cannot read secrets
echo "Test 7: srt-wrapped process cannot read secrets"
R=$(srt --settings "$SCRIPT_DIR/mcp-srt-config.json" -c "python3 -c '
import os
try:
    os.listdir(os.path.expanduser(\"~/.ssh\"))
    print(\"FAIL: should have been blocked\")
except PermissionError:
    print(\"BLOCKED: ssh denied\")
'" 2>&1)
assert_contains "ssh blocked" "$R" "BLOCKED"

# Cleanup
echo ""
echo "Cleaning up..."
docker stop rlm-hybrid-test >/dev/null 2>&1
docker rm rlm-hybrid-test >/dev/null 2>&1
docker rmi rlm-hybrid-test >/dev/null 2>&1

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ $FAIL -gt 0 ]; then exit 1; fi

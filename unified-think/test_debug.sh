#!/bin/bash

echo "=== Debug Test - Raw Server Output ==="
echo

# First, let's see what the server outputs for each request
echo "Test 1: Initialize request"
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"test-client"},"capabilities":{}}}' | INSTANCE_ID="test" cargo run --quiet 2>&1
echo -e "\n---\n"

echo "Test 2: List tools request"
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | INSTANCE_ID="test" cargo run --quiet 2>&1
echo -e "\n---\n"

echo "Test 3: ui_think tool call"
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Debug test thought","thought_number":1,"total_thoughts":1,"next_thought_needed":false}}}' | INSTANCE_ID="test" cargo run --quiet 2>&1
#!/bin/bash
# Manual test for event streaming

echo "Starting unified-think server and sending test requests..."

# Set test instance
export INSTANCE_ID="event_test"
export RUST_LOG=debug

# Create a test script to send multiple requests
cat > test_requests.json << 'EOF'
{"jsonrpc":"2.0","id":"1","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}
{"jsonrpc":"2.0","id":"2","method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Testing event streaming - this thought should create a thought_created event","thought_number":1,"total_thoughts":1,"next_thought_needed":false,"chain_id":"test-chain-123"}}}
{"jsonrpc":"2.0","id":"3","method":"tools/call","params":{"name":"ui_recall","arguments":{"query":"event streaming","limit":5}}}
{"jsonrpc":"2.0","id":"4","method":"tools/call","params":{"name":"ui_recall","arguments":{"chain_id":"test-chain-123"}}}
EOF

# Run the server with test requests
echo "Sending requests to server..."
timeout 10s sh -c 'cat test_requests.json | cargo run 2>&1' | tee server_output.log

echo -e "\n=== Checking server output for event logging ==="
echo "Event stream initialization:"
grep -i "event stream" server_output.log | head -5

echo -e "\nEvent logging:"
grep -i "logged.*event" server_output.log | head -10

echo -e "\nThought operations:"
grep -i "thought_created\|thought_accessed" server_output.log | head -10

# Clean up
rm -f test_requests.json

echo -e "\n=== Test complete ==="
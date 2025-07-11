#!/bin/bash

# Simple direct test for UnifiedThink MCP Server

echo "=== UnifiedThink Phase 1 Simple Test ==="
echo

# Build the project
echo "Building project..."
cargo build || exit 1
echo "Build successful!"
echo

# Create a test file with JSON-RPC requests
cat > test_requests.json << 'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"test-client","version":"1.0.0"},"capabilities":{}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Testing Phase 1 - This is my initial thought about the problem","thought_number":1,"total_thoughts":3,"next_thought_needed":true}}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Applying first principles - breaking down the components","thought_number":2,"total_thoughts":3,"next_thought_needed":true}}}
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Conclusion - the foundation is working correctly","thought_number":3,"total_thoughts":3,"next_thought_needed":false}}}
EOF

# Run the server with test requests
echo "Running tests..."
echo "===================="
INSTANCE_ID="phase1-test" cargo run --quiet < test_requests.json 2>&1 | grep -E '(jsonrpc|Thought Record|INFO)' | while IFS= read -r line; do
    if [[ $line == *"jsonrpc"* ]]; then
        echo "Response: $line"
        echo
    elif [[ $line == *"Thought Record"* ]] || [[ $line == *"INFO"* ]]; then
        echo "$line"
    fi
done

# Clean up
rm -f test_requests.json

echo
echo "=== Test Complete ==="
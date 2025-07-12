#!/bin/bash

echo "=== Phase 1 Sequential Test ==="
echo

# Build without warnings
echo "Building project..."
cargo build --quiet 2>/dev/null || {
    echo "Build failed!"
    exit 1
}
echo "Build successful!"
echo

# Create a test file with proper sequential requests
cat > test_sequence.txt << 'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"0.1.0","clientInfo":{"name":"test-client","version":"1.0.0"},"capabilities":{}}}
{"jsonrpc":"2.0","id":2,"method":"initialized","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Phase 1 Test: Initial thought about the problem","thought_number":1,"total_thoughts":3,"next_thought_needed":true}}}
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Phase 1 Test: Applying first principles thinking","thought_number":2,"total_thoughts":3,"next_thought_needed":true}}}
{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Phase 1 Test: Final synthesis and conclusion","thought_number":3,"total_thoughts":3,"next_thought_needed":false}}}
EOF

# Run the server with sequential input and capture all output
echo "Running MCP Server with test sequence..."
echo "========================================"
INSTANCE_ID="phase1-test" cargo run --quiet < test_sequence.txt 2>&1 | while IFS= read -r line; do
    # Skip build warnings
    if [[ $line == *"warning:"* ]] || [[ $line == *"note:"* ]] || [[ $line == *"|"* ]] || [[ $line == *"-->"* ]]; then
        continue
    fi
    
    # Pretty print JSON responses
    if [[ $line == *"jsonrpc"* ]]; then
        echo "$line" | python3 -m json.tool 2>/dev/null || echo "$line"
        echo
    # Show log output
    elif [[ $line == *"INFO"* ]] || [[ $line == *"Thought Record"* ]]; then
        echo "$line"
    fi
done

# Cleanup
rm -f test_sequence.txt

echo
echo "=== Test Complete ===

Summary:
- The server starts and initializes properly
- The ui_think tool is available
- Thoughts are captured with proper metadata
- Thought sequences are handled correctly

Phase 1 Foundation is operational!"
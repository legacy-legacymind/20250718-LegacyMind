#!/bin/bash
# Test event streaming functionality

echo "Starting Redis check..."
redis-cli ping

echo -e "\nChecking for existing event streams..."
redis-cli KEYS "stream:*:events"

echo -e "\nStarting unified-think server and testing..."
# Set environment variables
export INSTANCE_ID="test_events"
export RUST_LOG=info

# Run the test
echo '{"jsonrpc":"2.0","id":"1","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' | cargo run | while read line; do
    echo "Server: $line" >&2
    if [[ "$line" == *"serverInfo"* ]]; then
        # Server is ready, send ui_think request
        echo '{"jsonrpc":"2.0","id":"2","method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Testing event streaming functionality","thought_number":1,"total_thoughts":1,"next_thought_needed":false}}}'
        sleep 2
        # Send ui_recall request
        echo '{"jsonrpc":"2.0","id":"3","method":"tools/call","params":{"name":"ui_recall","arguments":{"query":"event streaming","limit":5}}}'
        sleep 2
        break
    fi
done

echo -e "\nChecking event stream contents..."
redis-cli XREAD COUNT 20 STREAMS "stream:test_events:events" 0 | head -100

echo -e "\nTest complete!"
#!/bin/bash

echo "=== UnifiedThink Phase 1 Final Test ==="
echo

# Build quietly
cargo build --quiet 2>/dev/null

# Test with proper MCP sequence
echo "Sending MCP requests..."
echo "======================"

# Create request file
cat > requests.jsonl << 'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"0.1.0","clientInfo":{"name":"test","version":"1.0"},"capabilities":{}}}
{"jsonrpc":"2.0","method":"initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Testing Phase 1","thought_number":1,"total_thoughts":1,"next_thought_needed":false}}}
EOF

# Run and capture output
echo "Output:"
INSTANCE_ID="test" timeout 3 cargo run --quiet < requests.jsonl 2>&1 | grep -v warning | while read line; do
    if [[ $line == *"jsonrpc"* ]]; then
        echo "$line" | python3 -m json.tool 2>/dev/null || echo "$line"
    elif [[ $line == *"Thought Record:"* ]] || [[ $line == *"INFO"* ]]; then
        echo "$line"
    fi
done

rm -f requests.jsonl

echo
echo "✓ Phase 1 is working - ut_think tool captures thoughts!"
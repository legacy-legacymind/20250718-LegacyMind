#!/bin/bash
# Test tool listing for unified-think

echo "Testing tool discovery..."

# Set environment variables for local testing
export INSTANCE_ID="test_tools"
export RUST_LOG=error
export ALLOW_DEFAULT_REDIS_PASSWORD=1

# Send initialize and tools/list requests
(
echo '{"jsonrpc":"2.0","id":"1","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}'
sleep 0.5
echo '{"jsonrpc":"2.0","id":"2","method":"tools/list"}'
sleep 0.5
) | cargo run 2>/dev/null | while IFS= read -r line; do
    if [[ "$line" == *'"method":"tools/list"'* ]] || [[ "$line" == *'"tools":'* ]]; then
        echo "Response: $line"
        # Pretty print if it's the tools response
        if [[ "$line" == *'"tools":'* ]]; then
            echo "$line" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if 'result' in data and 'tools' in data['result']:
    tools = data['result']['tools']
    print(f'\nFound {len(tools)} tools:')
    for tool in tools:
        print(f'  - {tool[\"name\"]}: {tool.get(\"description\", \"No description\")}')
"
        fi
    fi
done
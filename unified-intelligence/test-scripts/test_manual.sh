#!/bin/bash

echo "=== UnifiedThink Manual Test Helper ==="
echo
echo "This script helps you manually test the ut_think tool"
echo

# Build first
cargo build --quiet 2>/dev/null || { echo "Build failed!"; exit 1; }

# Create a sample requests file
cat > manual_test_template.jsonl << 'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"manual-test","version":"1.0"}}}
{"jsonrpc":"2.0","method":"initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"YOUR_THOUGHT_HERE","thought_number":1,"total_thoughts":1,"next_thought_needed":false}}}
EOF

echo "To test the server, run:"
echo
echo "  INSTANCE_ID=\"your-instance\" cargo run < manual_test_template.jsonl"
echo
echo "Or create your own test file with multiple thoughts:"
echo
cat << 'EOF'
Example multi-thought sequence:

{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"manual-test","version":"1.0"}}}
{"jsonrpc":"2.0","method":"initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"First thought","thought_number":1,"total_thoughts":3,"next_thought_needed":true}}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Second thought","thought_number":2,"total_thoughts":3,"next_thought_needed":true}}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Final thought","thought_number":3,"total_thoughts":3,"next_thought_needed":false}}}
EOF

echo
echo "The template file 'manual_test_template.jsonl' has been created for you to edit."
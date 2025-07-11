#!/bin/bash

# Test the UnifiedThink MCP Server

echo "Testing UnifiedThink MCP Server..."

# Test initialize request
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"test-client"},"capabilities":{}}}' | cargo run 2>/dev/null

# Give server a moment to initialize
sleep 1

# Test listing tools
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | cargo run 2>/dev/null

# Test calling ui_think tool
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"This is a test thought","thought_number":1,"total_thoughts":3,"next_thought_needed":true}}}' | cargo run 2>/dev/null
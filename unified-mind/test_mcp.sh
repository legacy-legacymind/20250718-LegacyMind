#!/bin/bash

# Test UnifiedMind MCP service

# Start Redis if not running
redis-cli ping > /dev/null 2>&1 || {
    echo "Redis is not running. Please start Redis first."
    exit 1
}

echo "Testing UnifiedMind MCP service..."

# Test initialize request
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' | cargo run 2>/dev/null | jq .

# Test list tools
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | cargo run 2>/dev/null | jq .

echo "Test complete!"
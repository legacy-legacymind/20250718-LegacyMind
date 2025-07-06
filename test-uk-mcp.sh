#!/bin/bash

echo "Testing UnifiedKnowledge MCP..."

# Test listing tickets
echo "Testing ticket list..."
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"uk_ticket","arguments":{"action":"list","limit":2}},"id":1}' | \
docker exec -i legacymind_unified_knowledge node /app/src/index.js 2>/dev/null | \
tail -1 | jq '.'

# Test creating a ticket
echo -e "\nTesting ticket creation..."
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"uk_ticket","arguments":{"action":"create","title":"Test Ticket","description":"This is a test ticket","priority":"medium","type":"task","tags":["test","mcp"]}},"id":2}' | \
docker exec -i legacymind_unified_knowledge node /app/src/index.js 2>/dev/null | \
tail -1 | jq '.'
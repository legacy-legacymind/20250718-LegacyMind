#!/bin/bash

echo "Creating test ticket..."

REQUEST='{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "uk_ticket",
    "arguments": {
      "action": "create",
      "title": "Test MCP Connection",
      "description": "Testing if UnifiedKnowledge MCP is working correctly",
      "priority": "medium",
      "type": "task",
      "tags": ["test", "mcp", "verification"]
    }
  },
  "id": 1
}'

echo "$REQUEST" | docker exec -i legacymind_unified_knowledge node /app/src/index.js 2>&1
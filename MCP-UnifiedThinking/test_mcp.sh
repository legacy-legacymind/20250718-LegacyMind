#!/bin/bash

# Test the MCP-UnifiedThinking server with a proper JSON-RPC request

echo "Testing MCP-UnifiedThinking with ut_think tool..."

# Create a JSON-RPC request for ut_think
REQUEST='{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "ut_think",
    "arguments": {
      "framework": "socratic",
      "content": "This is the first test of the new MCP.",
      "chainId": "MCP_Validation_Chain_1"
    }
  },
  "id": 1
}'

# Send the request to the MCP server
echo "$REQUEST" | ./target/release/MCP-UnifiedThinking
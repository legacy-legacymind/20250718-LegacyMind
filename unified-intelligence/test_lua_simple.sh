#!/bin/bash

# Test Lua scripts with simple JSON-RPC calls

echo "Starting unified-think server..."
cargo run 2>/tmp/server.log &
SERVER_PID=$!
sleep 3

# Test 1: Store a thought
echo "Test 1: Storing a thought..."
echo '{
  "jsonrpc": "2.0",
  "method": "ui_think",
  "params": {
    "thought": "Testing Lua script atomicity with timestamp ' $(date +%s) '",
    "thought_number": 1,
    "total_thoughts": 2,
    "next_thought_needed": true,
    "chain_id": "test-chain-123"
  },
  "id": 1
}' | cargo run 2>/dev/null | jq .

# Test 2: Store the same thought again (should detect duplicate)
echo -e "\nTest 2: Storing the same thought again..."
echo '{
  "jsonrpc": "2.0",
  "method": "ui_think",
  "params": {
    "thought": "Testing Lua script atomicity with timestamp ' $(date +%s) '",
    "thought_number": 2,
    "total_thoughts": 2,
    "next_thought_needed": false,
    "chain_id": "test-chain-123"
  },
  "id": 2
}' | cargo run 2>/dev/null | jq .

# Test 3: Recall the chain
echo -e "\nTest 3: Recalling the chain..."
echo '{
  "jsonrpc": "2.0",
  "method": "ui_recall",
  "params": {
    "chain_id": "test-chain-123",
    "action": "search"
  },
  "id": 3
}' | cargo run 2>/dev/null | jq .

# Cleanup
kill $SERVER_PID 2>/dev/null
echo -e "\nTest complete!"
#!/bin/bash

echo "=== Phase 3 Test: Enhanced ui_recall ==="
echo
echo "Testing the new unified workflow in ui_recall"
echo

# Build first
echo "Building project..."
cargo build --quiet 2>/dev/null || { echo "Build failed!"; exit 1; }

# Create test file with Phase 3 scenarios
cat > phase3_test.jsonl << 'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"phase3-test","version":"1.0"}}}
{"jsonrpc":"2.0","method":"initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
EOF

echo "Test 1: Create some thoughts with chains"
cat >> phase3_test.jsonl << 'EOF'
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Redis performance optimization strategies","thought_number":1,"total_thoughts":2,"next_thought_needed":true,"chain_id":"perf-chain-1"}}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Implementing Redis pipeline for batch operations","thought_number":2,"total_thoughts":2,"next_thought_needed":false,"chain_id":"perf-chain-1"}}}
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Understanding Redis memory management","thought_number":1,"total_thoughts":1,"next_thought_needed":false,"chain_id":"memory-chain-1"}}}
EOF

echo "Test 2: Search for thoughts"
cat >> phase3_test.jsonl << 'EOF'
{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"ui_recall","arguments":{"query":"Redis performance"}}}
EOF

echo "Test 3: Retrieve specific chain"
cat >> phase3_test.jsonl << 'EOF'
{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"ui_recall","arguments":{"chain_id":"perf-chain-1"}}}
EOF

echo "Test 4: Analyze search results"
cat >> phase3_test.jsonl << 'EOF'
{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"ui_recall","arguments":{"query":"Redis","action":"analyze"}}}
EOF

echo "Test 5: Merge chains"
cat >> phase3_test.jsonl << 'EOF'
{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"ui_recall","arguments":{"query":"Redis","action":"merge","action_params":{"new_chain_name":"Redis Combined Knowledge"}}}}
EOF

echo "Test 6: Branch from thought"
cat >> phase3_test.jsonl << 'EOF'
{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"ui_recall","arguments":{"action":"branch","action_params":{"thought_id":"test-thought-id","new_chain_name":"Alternative Approach"}}}}
EOF

echo "Running tests..."
echo
INSTANCE_ID="phase3-test" cargo run < phase3_test.jsonl 2>&1 | grep -E "(Storing thought|Search|chain|error|ERROR)"

echo
echo "Full test output saved to: phase3_test_output.log"
INSTANCE_ID="phase3-test" cargo run < phase3_test.jsonl > phase3_test_output.log 2>&1

echo
echo "To see formatted results:"
echo "  cat phase3_test_output.log | jq -r 'select(.result != null) | .result'"
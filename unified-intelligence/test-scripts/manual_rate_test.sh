#!/bin/bash
# Manual rate limit test

echo "Building the project..."
cargo build

echo -e "\nStarting server and sending rapid requests..."
echo "This will send 105 requests quickly to test the rate limiter (limit is 100/min)"

# Create a test script that sends many requests
cat > rapid_test.jsonl << 'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"rate-test","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
EOF

# Generate 105 ui_think requests
for i in {1..105}; do
    echo "{\"jsonrpc\":\"2.0\",\"id\":$((i+1)),\"method\":\"tools/call\",\"params\":{\"name\":\"ui_think\",\"arguments\":{\"thought\":\"Rate test $i\",\"thought_number\":1,\"total_thoughts\":1,\"next_thought_needed\":false}}}" >> rapid_test.jsonl
done

# Run the test and count results
echo -e "\nRunning test..."
INSTANCE_ID=rate-test ./target/debug/unified-think < rapid_test.jsonl > rate_output.json 2> rate_errors.log

# Count successes and rate limit errors
echo -e "\nAnalyzing results..."
SUCCESS_COUNT=$(grep -c '"isError":false' rate_output.json || echo 0)
RATE_LIMIT_COUNT=$(grep -c 'Rate limit exceeded' rate_output.json || echo 0)

echo "Successful requests: $SUCCESS_COUNT"
echo "Rate limited requests: $RATE_LIMIT_COUNT"

if [ "$SUCCESS_COUNT" -le 100 ] && [ "$RATE_LIMIT_COUNT" -gt 0 ]; then
    echo -e "\n✅ Rate limiting is working!"
else
    echo -e "\n❌ Rate limiting may not be working as expected"
fi

# Check stderr for rate limit warnings
echo -e "\nRate limit warnings in logs:"
grep "Rate limit" rate_errors.log | head -5

# Cleanup
rm -f rapid_test.jsonl rate_output.json rate_errors.log
#!/bin/bash

# Simple test for time series functionality

echo "Testing Time Series thought metrics..."

INSTANCE_ID="test_metrics_$(date +%s)"

# Send multiple thoughts
for i in {1..5}; do
    echo -e "\nSending thought #$i..."
    echo "{\"jsonrpc\":\"2.0\",\"method\":\"ui_think\",\"params\":{\"thought\":\"Test thought #$i for time series\",\"instance\":\"$INSTANCE_ID\"},\"id\":\"test-$i\"}" | nc -w 1 localhost 8080
    sleep 0.5
done

echo -e "\n\nChecking Time Series in Redis..."
echo "Time series key: ts:$INSTANCE_ID:thought_count"

# Check if Redis Time Series commands are available
redis-cli TS.INFO "ts:$INSTANCE_ID:thought_count" 2>/dev/null || echo "Note: Redis TimeSeries module may not be installed"

echo -e "\nYou can manually check the metrics with:"
echo "  redis-cli TS.INFO ts:$INSTANCE_ID:thought_count"
echo "  redis-cli TS.RANGE ts:$INSTANCE_ID:thought_count - +"
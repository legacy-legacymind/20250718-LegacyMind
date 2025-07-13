#!/bin/bash
export REDIS_PASSWORD=legacymind_redis_pass
export INSTANCE_ID=Claude

echo "=== Testing ui_think via stdio ==="

# Test creating a thought
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Testing bloom filter fix - the WRONGTYPE error should be resolved now","instance_id":"Claude"}},"id":1}' | ./target/release/unified-think 2>&1 | grep -v "INFO\|WARN" | jq '.result' 2>/dev/null || echo "Error in response"

# Check bloom filter stats
echo -e "\nBloom filter stats after test:"
docker exec redis-legacymind redis-cli -a legacymind_redis_pass --no-auth-warning BF.INFO "Claude/bloom/thoughts" 2>&1 | grep -A1 "Number of items"
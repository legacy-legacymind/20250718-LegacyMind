#!/bin/bash
export REDIS_PASSWORD=legacymind_redis_pass
export INSTANCE_ID=Claude

# Start the server in background
./target/release/unified-think &
SERVER_PID=$!

# Wait for server to start
sleep 2

echo "=== Testing ui_think after bloom filter fix ==="
echo

# Test 1: Create a thought
echo "Test 1: Creating a thought..."
echo '{"jsonrpc":"2.0","method":"ui_think","params":{"thought":"The bloom filter type error has been fixed. The issue was that bloom filters were created as STRING type instead of proper Redis Bloom filter types.","instance_id":"Claude"},"id":1}' | nc localhost 9999
echo

sleep 1

# Test 2: Try to create duplicate thought
echo "Test 2: Testing duplicate detection..."
echo '{"jsonrpc":"2.0","method":"ui_think","params":{"thought":"The bloom filter type error has been fixed. The issue was that bloom filters were created as STRING type instead of proper Redis Bloom filter types.","instance_id":"Claude"},"id":2}' | nc localhost 9999
echo

sleep 1

# Test 3: Create another unique thought
echo "Test 3: Creating another unique thought..."
echo '{"jsonrpc":"2.0","method":"ui_think","params":{"thought":"Testing ui_think after fixing WRONGTYPE error on bloom filters","instance_id":"Claude"},"id":3}' | nc localhost 9999
echo

sleep 1

# Kill the server
kill $SERVER_PID 2>/dev/null || true

# Check bloom filter stats
echo -e "\nBloom filter stats:"
docker exec redis-legacymind redis-cli -a legacymind_redis_pass --no-auth-warning BF.INFO "Claude/bloom/thoughts" | grep "Number of items"
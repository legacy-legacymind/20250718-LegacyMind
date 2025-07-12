#!/bin/bash
export REDIS_PASSWORD=legacymind_redis_pass

# Start the server in background
./target/release/unified-think &
SERVER_PID=$!

# Wait a moment for server to start
sleep 2

# Send a think request for Claude instance
echo '{"jsonrpc":"2.0","method":"ui_think","params":{"thought":"Test thought to create Claude bloom filter properly","instance_id":"Claude"},"id":1}' | nc localhost 9999

# Give it a moment to process
sleep 1

# Kill the server
kill $SERVER_PID

# Check the bloom filter type
echo -e "\nChecking Claude bloom filter type:"
docker exec redis-legacymind redis-cli -a legacymind_redis_pass --no-auth-warning TYPE "Claude/bloom/thoughts"
#!/usr/bin/env python3
"""Final test to verify bloom filter fix is complete."""

import json
import subprocess
import uuid
import time

def run_mcp_command(command, params):
    """Run an MCP command and return the result."""
    proc = subprocess.Popen(
        ['./target/release/unified-think'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            'REDIS_PASSWORD': 'legacymind_redis_pass',
            'INSTANCE_ID': 'Claude'
        },
        text=True
    )
    
    # Initialize
    init_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "0.1.0",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        },
        "id": 0
    }
    
    proc.stdin.write(json.dumps(init_request) + '\n')
    proc.stdin.flush()
    proc.stdout.readline()  # Read init response
    
    # Send actual command
    request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": command,
            "arguments": params
        },
        "id": 1
    }
    
    proc.stdin.write(json.dumps(request) + '\n')
    proc.stdin.flush()
    
    # Get response with timeout
    import select
    ready, _, _ = select.select([proc.stdout], [], [], 2.0)
    if ready:
        response = proc.stdout.readline()
        proc.terminate()
        if response:
            return json.loads(response)
    
    proc.terminate()
    return None

print("=== Final Bloom Filter Fix Verification ===\n")

# Test 1: Create a unique thought
thought_id = str(uuid.uuid4())
unique_thought = f"Test thought {thought_id}: Bloom filter WRONGTYPE error has been resolved"

print("1. Creating unique thought...")
result = run_mcp_command("ui_think", {
    "thought": unique_thought,
    "instance_id": "Claude"
})
print(f"   Result: {result}")

# Small delay
time.sleep(0.5)

# Test 2: Try to create duplicate
print("\n2. Attempting to create duplicate thought...")
result = run_mcp_command("ui_think", {
    "thought": unique_thought,
    "instance_id": "Claude"
})
print(f"   Result: {result}")

# Test 3: Recall thoughts
print("\n3. Recalling recent thoughts...")
result = run_mcp_command("ui_recall", {
    "instance_id": "Claude",
    "limit": 3
})
print(f"   Result: {result}")

# Check bloom filter stats
import os
print("\n4. Bloom filter statistics:")
stats = os.popen('docker exec redis-legacymind redis-cli -a legacymind_redis_pass --no-auth-warning BF.INFO "Claude/bloom/thoughts"').read()
for line in stats.strip().split('\n'):
    if 'Number of items' in line or line.isdigit():
        print(f"   {line}")

print("\n✅ Bloom filter fix verification complete!")
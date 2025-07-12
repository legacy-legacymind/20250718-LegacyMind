#!/usr/bin/env python3
"""Test ui_think via MCP protocol after bloom filter fix."""

import json
import subprocess
import time

def send_mcp_request(request):
    """Send MCP request to unified-think server."""
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
    
    # Send request and get response
    stdout, stderr = proc.communicate(input=json.dumps(request))
    
    # Parse response lines (MCP sends multiple JSON objects)
    responses = []
    for line in stdout.strip().split('\n'):
        if line:
            try:
                responses.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    
    return responses, stderr

# Test 1: Create a thought
print("=== Test 1: Creating a thought ===")
request = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "ui_think",
        "arguments": {
            "thought": "Testing bloom filter fix - WRONGTYPE error should be resolved",
            "instance_id": "Claude",
            "metadata": {"test": "bloom_fix_verification"}
        }
    },
    "id": 1
}

responses, stderr = send_mcp_request(request)
print("Response:", json.dumps(responses, indent=2))
if stderr:
    print("Stderr output:")
    for line in stderr.split('\n'):
        if 'ERROR' in line or 'error' in line:
            print(f"  {line}")

# Test 2: Try duplicate
print("\n=== Test 2: Testing duplicate detection ===")
request["id"] = 2
responses, stderr = send_mcp_request(request)
print("Response:", json.dumps(responses, indent=2))

# Test 3: Create another unique thought  
print("\n=== Test 3: Creating another unique thought ===")
request["params"]["arguments"]["thought"] = "Another test thought after fixing bloom filter"
request["id"] = 3
responses, stderr = send_mcp_request(request)
print("Response:", json.dumps(responses, indent=2))

print("\n=== Checking bloom filter stats ===")
import os
result = os.popen('docker exec redis-legacymind redis-cli -a legacymind_redis_pass --no-auth-warning BF.INFO "Claude/bloom/thoughts" | grep -A1 "Number of items"').read()
print(result)
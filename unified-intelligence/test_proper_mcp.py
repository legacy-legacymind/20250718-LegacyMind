#!/usr/bin/env python3
"""Test ui_think with proper MCP initialization."""

import json
import subprocess
import sys

def test_mcp_server():
    """Test MCP server with proper initialization."""
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
    
    # Send initialization request
    init_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "0.1.0",
            "capabilities": {
                "tools": {}
            },
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        },
        "id": 0
    }
    
    print("Sending initialization request...")
    proc.stdin.write(json.dumps(init_request) + '\n')
    proc.stdin.flush()
    
    # Read initialization response
    init_response = proc.stdout.readline()
    print("Init response:", init_response.strip())
    
    # Now send ui_think request
    think_request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "ui_think",
            "arguments": {
                "thought": "Testing bloom filter fix after WRONGTYPE error resolution",
                "instance_id": "Claude",
                "metadata": {"test": "bloom_fix_complete"}
            }
        },
        "id": 1
    }
    
    print("\nSending ui_think request...")
    proc.stdin.write(json.dumps(think_request) + '\n')
    proc.stdin.flush()
    
    # Read response
    response = proc.stdout.readline()
    print("Think response:", response.strip())
    
    # Terminate
    proc.terminate()
    proc.wait()
    
    # Check bloom filter
    import os
    print("\nChecking bloom filter stats:")
    result = os.popen('docker exec redis-legacymind redis-cli -a legacymind_redis_pass --no-auth-warning BF.INFO "Claude/bloom/thoughts" 2>&1').read()
    print(result)

if __name__ == "__main__":
    test_mcp_server()
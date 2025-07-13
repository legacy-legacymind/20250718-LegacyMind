#!/usr/bin/env python3
"""Test unified-intelligence MCP server functionality"""

import json
import subprocess
import time

def send_mcp_request(request):
    """Send MCP request to unified-intelligence server."""
    proc = subprocess.Popen(
        ['./target/release/unified-intelligence'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            'REDIS_PASSWORD': 'legacymind_redis_pass',
            'INSTANCE_ID': 'Claude'
        },
        text=True
    )
    
    # Send the request
    stdout, stderr = proc.communicate(json.dumps(request))
    
    print(f"Request: {json.dumps(request, indent=2)}")
    print(f"STDERR: {stderr}")
    print(f"STDOUT: {stdout}")
    
    # Parse response if valid JSON
    try:
        response = json.loads(stdout)
        print(f"Response: {json.dumps(response, indent=2)}")
        return response
    except json.JSONDecodeError:
        print(f"Invalid JSON response: {stdout}")
        return None

def main():
    print("Testing unified-intelligence MCP server...")
    
    # Test 1: Initialize
    print("\n=== TEST 1: Initialize ===")
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    init_response = send_mcp_request(init_request)
    
    # Test 2: List tools
    print("\n=== TEST 2: List Tools ===")
    list_tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    
    tools_response = send_mcp_request(list_tools_request)
    
    # Test 3: Test ui_think
    print("\n=== TEST 3: Test ui_think ===")
    think_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "ui_think",
            "arguments": {
                "thought": "Testing the migrated unified-intelligence MCP server",
                "thought_number": 1,
                "total_thoughts": 1,
                "next_thought_needed": False
            }
        }
    }
    
    think_response = send_mcp_request(think_request)

if __name__ == "__main__":
    main()
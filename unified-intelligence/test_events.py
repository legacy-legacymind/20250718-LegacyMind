#!/usr/bin/env python3
"""Test script to verify event streaming functionality"""

import json
import sys
import time
import subprocess
import uuid

def send_mcp_request(method, params=None):
    """Send an MCP request to the server via stdio"""
    request = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params or {}
    }
    
    print(json.dumps(request), flush=True)
    
    # Read response
    response_line = sys.stdin.readline()
    return json.loads(response_line) if response_line else None

def test_ui_think():
    """Test ui_think to create thought and generate events"""
    print("Testing ui_think to create thought...", file=sys.stderr)
    
    params = {
        "thought": f"Test thought for event streaming at {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "thought_number": 1,
        "total_thoughts": 1,
        "next_thought_needed": False,
        "chain_id": f"test-chain-{uuid.uuid4()}"
    }
    
    response = send_mcp_request("tools/call", {
        "name": "ui_think",
        "arguments": params
    })
    
    print(f"ui_think response: {json.dumps(response, indent=2)}", file=sys.stderr)
    return response

def test_ui_recall():
    """Test ui_recall to search thoughts and generate events"""
    print("\nTesting ui_recall to search thoughts...", file=sys.stderr)
    
    params = {
        "query": "event streaming",
        "limit": 10
    }
    
    response = send_mcp_request("tools/call", {
        "name": "ui_recall", 
        "arguments": params
    })
    
    print(f"ui_recall response: {json.dumps(response, indent=2)}", file=sys.stderr)
    return response

def check_redis_events():
    """Check Redis for events in the stream"""
    print("\nChecking Redis for events...", file=sys.stderr)
    
    # Get instance ID from environment or use default
    import os
    instance_id = os.environ.get("INSTANCE_ID", "test")
    
    # Use redis-cli to check the stream
    cmd = [
        "redis-cli",
        "XREAD", "COUNT", "10", "STREAMS", f"stream:{instance_id}:events", "0"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"Redis stream events:\n{result.stdout}", file=sys.stderr)
        
        if result.returncode != 0:
            print(f"Error reading stream: {result.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"Error checking Redis: {e}", file=sys.stderr)

if __name__ == "__main__":
    print("=== Event Streaming Test ===", file=sys.stderr)
    
    # Initialize connection
    response = send_mcp_request("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {}
    })
    print(f"Initialize response: {json.dumps(response, indent=2)}", file=sys.stderr)
    
    # Test thought creation
    test_ui_think()
    time.sleep(1)  # Give time for event to be logged
    
    # Test thought recall
    test_ui_recall()
    time.sleep(1)  # Give time for event to be logged
    
    # Check events in Redis
    check_redis_events()
    
    print("\n=== Test Complete ===", file=sys.stderr)
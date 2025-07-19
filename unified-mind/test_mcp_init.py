#!/usr/bin/env python3
"""Test UnifiedMind MCP initialization"""

import json
import subprocess
import sys
import os

def test_unified_mind():
    """Test UnifiedMind MCP server initialization"""
    
    # Set environment variables
    env = os.environ.copy()
    env.update({
        'REDIS_HOST': '127.0.0.1',
        'REDIS_PORT': '6379',
        'REDIS_PWD': 'legacymind_redis_pass',
        'UNIFIED_MIND_INSTANCE': 'CC',
        'UNIFIED_MIND_LOG_LEVEL': 'debug',
    })
    
    # MCP initialization request
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "0.1.0",
            "capabilities": {
                "tools": {
                    "enabled": True
                }
            }
        }
    }
    
    # Start the server
    process = subprocess.Popen(
        ['/Users/samuelatagana/Projects/LegacyMind/unified-mind/target/release/unified-mind'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True
    )
    
    # Send initialization request
    request_str = json.dumps(init_request) + '\n'
    stdout, stderr = process.communicate(input=request_str, timeout=5)
    
    # Print output
    print("STDOUT:")
    print(stdout)
    print("\nSTDERR:")
    print(stderr)
    
    # Check if we got a valid response
    if stdout:
        try:
            response = json.loads(stdout.strip())
            if 'result' in response:
                print("\n✅ MCP initialization successful!")
                print(f"Server info: {json.dumps(response['result'], indent=2)}")
                return True
        except json.JSONDecodeError:
            print("\n❌ Invalid JSON response")
    
    return False

if __name__ == "__main__":
    success = test_unified_mind()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""Test rate limiting functionality"""

import json
import subprocess
import sys
import time
from typing import Dict, Any

def send_request(process, request: Dict[str, Any]) -> Dict[str, Any]:
    """Send a JSON-RPC request and get response"""
    request_str = json.dumps(request) + '\n'
    process.stdin.write(request_str)
    process.stdin.flush()
    
    response_line = process.stdout.readline()
    return json.loads(response_line)

def main():
    print("Starting rate limit test...")
    
    # Start the server
    process = subprocess.Popen(
        ['./target/debug/unified-think'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={'INSTANCE_ID': 'rate-test'}
    )
    
    try:
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "rate-limit-test", "version": "1.0"}
            }
        }
        
        response = send_request(process, init_request)
        print("Initialized:", response.get('result', {}).get('serverInfo', {}).get('name'))
        
        # Send initialized notification
        process.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }) + '\n')
        process.stdin.flush()
        
        # Now spam requests to test rate limiting (100 per minute limit)
        print("\nSending 110 requests rapidly to test rate limiting...")
        
        success_count = 0
        rate_limit_count = 0
        
        for i in range(110):
            request = {
                "jsonrpc": "2.0",
                "id": i + 2,
                "method": "tools/call",
                "params": {
                    "name": "ui_think",
                    "arguments": {
                        "thought": f"Rate limit test thought {i + 1}",
                        "thought_number": 1,
                        "total_thoughts": 1,
                        "next_thought_needed": False
                    }
                }
            }
            
            response = send_request(process, request)
            
            if 'result' in response:
                success_count += 1
            elif 'error' in response:
                error_msg = response['error'].get('message', '')
                if 'Rate limit exceeded' in error_msg:
                    rate_limit_count += 1
                    if rate_limit_count == 1:
                        print(f"\nRate limit hit at request {i + 1}")
                else:
                    print(f"Unexpected error at request {i + 1}: {error_msg}")
        
        print(f"\nResults:")
        print(f"- Successful requests: {success_count}")
        print(f"- Rate limited requests: {rate_limit_count}")
        print(f"- Expected rate limit: After 100 requests")
        
        if success_count == 100 and rate_limit_count == 10:
            print("\n✅ Rate limiting is working correctly!")
        else:
            print("\n❌ Rate limiting may not be working as expected")
        
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Verify SearchCache Integration Issue
This script demonstrates that the SearchCache is not being used in the current implementation.
"""

import json
import subprocess
import time
import sys

def send_mcp_request(process, request):
    """Send a request to the MCP server and get response."""
    request_str = json.dumps(request) + '\n'
    process.stdin.write(request_str.encode())
    process.stdin.flush()
    
    response_line = process.stdout.readline().decode().strip()
    if response_line:
        return json.loads(response_line)
    return None

def main():
    print("Testing SearchCache Integration...")
    print("=" * 50)
    
    # Start the server
    cmd = ["./target/debug/unified-think"]
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**subprocess.os.environ, "INSTANCE_ID": "cache-test"}
    )
    
    try:
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {}
            }
        }
        response = send_mcp_request(process, init_request)
        print(f"1. Initialized: {response.get('result', {}).get('protocolVersion')}")
        
        # Send notification
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        send_mcp_request(process, notification)
        time.sleep(0.1)
        
        # Store a thought
        think_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "SearchCache test thought with unique keyword XYZABC123",
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False
                }
            }
        }
        response = send_mcp_request(process, think_request)
        print(f"2. Stored thought: {response.get('result', {}).get('content', [{}])[0].get('text', 'N/A')}")
        
        # Search for the thought multiple times
        search_times = []
        for i in range(3):
            start_time = time.time()
            
            search_request = {
                "jsonrpc": "2.0",
                "id": 3 + i,
                "method": "tools/call",
                "params": {
                    "name": "ui_recall",
                    "arguments": {
                        "query": "XYZABC123",
                        "limit": 10
                    }
                }
            }
            
            response = send_mcp_request(process, search_request)
            elapsed = time.time() - start_time
            search_times.append(elapsed)
            
            result = response.get('result', {}).get('content', [{}])[0]
            if isinstance(result.get('text'), str):
                data = json.loads(result['text'])
                print(f"\n3.{i+1} Search #{i+1} took {elapsed:.3f}s")
                print(f"   - Method: {data.get('search_method')}")
                print(f"   - Found: {data.get('total_found')} thoughts")
        
        # Analysis
        print("\n" + "=" * 50)
        print("CACHE ANALYSIS:")
        print(f"Search times: {[f'{t:.3f}s' for t in search_times]}")
        
        # If cache was working, subsequent searches should be significantly faster
        if all(abs(search_times[0] - t) < 0.01 for t in search_times[1:]):
            print("❌ ISSUE CONFIRMED: All search times are similar")
            print("   Cache is NOT being used (times should decrease)")
        else:
            print("✅ Cache might be working (times vary)")
        
        print("\nNOTE: With proper cache integration, searches 2 & 3")
        print("      should be near-instant (<0.001s) vs first search")
        
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__":
    main()
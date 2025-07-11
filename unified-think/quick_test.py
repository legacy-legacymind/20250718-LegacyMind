#!/usr/bin/env python3
"""
Quick test script for unified-think server.
Minimal example showing basic functionality.
"""

import json
import subprocess
import time
import sys

def send_request(process, request):
    """Send request and read response."""
    request_str = json.dumps(request) + "\n"
    process.stdin.write(request_str)
    process.stdin.flush()
    
    # Read response
    response_line = process.stdout.readline()
    if response_line:
        return json.loads(response_line.strip())
    return None

def main():
    # Start server
    print("Starting unified-think server...")
    process = subprocess.Popen(
        ["./target/debug/unified-think"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**subprocess.os.environ, "INSTANCE_ID": "quick-test"}
    )
    
    try:
        # Initialize
        print("\n1. Initializing...")
        response = send_request(process, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "quick-test", "version": "1.0"}
            }
        })
        print(f"Response: {json.dumps(response, indent=2)}")
        
        # Send initialized notification
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}) + "\n")
        process.stdin.flush()
        time.sleep(0.5)
        
        # Store a thought
        print("\n2. Storing a thought...")
        response = send_request(process, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Quick test of unified-think server",
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False,
                    "chain_id": "quick-test-chain"
                }
            }
        })
        print(f"Response: {json.dumps(response, indent=2)}")
        
        # Search for the thought
        print("\n3. Searching for thoughts...")
        response = send_request(process, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "test"
                }
            }
        })
        print(f"Response: {json.dumps(response, indent=2)}")
        
    finally:
        # Cleanup
        process.terminate()
        process.wait()
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
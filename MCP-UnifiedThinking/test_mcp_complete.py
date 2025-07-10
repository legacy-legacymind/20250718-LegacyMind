#!/usr/bin/env python3
import json
import subprocess
import sys

def send_request(proc, request):
    """Send a JSON-RPC request and get response"""
    request_str = json.dumps(request) + '\n'
    proc.stdin.write(request_str.encode())
    proc.stdin.flush()
    
    # Read response
    response_line = proc.stdout.readline().decode()
    if response_line:
        return json.loads(response_line)
    return None

def main():
    # Start the MCP server
    proc = subprocess.Popen(
        ['./target/release/MCP-UnifiedThinking'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd='/Users/samuelatagana/Projects/LegacyMind/MCP-UnifiedThinking'
    )
    
    try:
        # Initialize the connection
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            },
            "id": 1
        }
        
        print("Sending initialize request...")
        response = send_request(proc, init_request)
        print(f"Initialize response: {json.dumps(response, indent=2)}")
        
        # Call ut_think tool
        think_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "ut_think",
                "arguments": {
                    "framework": "socratic",
                    "content": "This is the first test of the new MCP.",
                    "chainId": "MCP_Validation_Chain_1"
                }
            },
            "id": 2
        }
        
        print("\nSending ut_think request...")
        response = send_request(proc, think_request)
        print(f"ut_think response: {json.dumps(response, indent=2)}")
        
    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
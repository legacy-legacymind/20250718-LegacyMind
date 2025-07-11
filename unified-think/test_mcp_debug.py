#!/usr/bin/env python3
"""Debug MCP server responses"""

import json
import subprocess
import sys
import time

def send_json_rpc(proc, request):
    """Send a JSON-RPC request and get response"""
    request_str = json.dumps(request)
    print(f"Sending: {request_str}", file=sys.stderr)
    
    # Write to stdin
    proc.stdin.write(request_str + '\n')
    proc.stdin.flush()
    
    # Read response
    response = proc.stdout.readline()
    print(f"Received: {response}", file=sys.stderr)
    
    return json.loads(response) if response else None

def main():
    # Start the server
    proc = subprocess.Popen(
        ['cargo', 'run'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd='/Users/samuelatagana/Projects/LegacyMind/unified-think-phase3/unified-think'
    )
    
    # Wait a bit for server to start
    time.sleep(2)
    
    try:
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            },
            "id": 1
        }
        
        response = send_json_rpc(proc, init_request)
        print(f"Initialize response: {json.dumps(response, indent=2)}")
        
        if response:
            # Send initialized notification (no response expected)
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }
            
            # Send notification (no id, so no response expected)
            proc.stdin.write(json.dumps(initialized_notification) + '\n')
            proc.stdin.flush()
            print("Sent initialized notification", file=sys.stderr)
            
            # Give server time to process
            time.sleep(0.5)
            # Send tools/list request
            list_request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2
            }
            
            response = send_json_rpc(proc, list_request)
            print(f"Tools list response: {json.dumps(response, indent=2)}")
            
            # Send tool call
            tool_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "ui_think",
                    "arguments": {
                        "thought": "Test thought",
                        "thought_number": 1,
                        "total_thoughts": 1,
                        "next_thought_needed": False
                    }
                },
                "id": 3
            }
            
            response = send_json_rpc(proc, tool_request)
            print(f"Tool call response: {json.dumps(response, indent=2)}")
    
    finally:
        # Print stderr output
        stderr_output = proc.stderr.read()
        if stderr_output:
            print(f"\nServer stderr:\n{stderr_output}")
        
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
import json
import subprocess
import sys
import time

def send_request(proc, request):
    """Send a JSON-RPC request and get response"""
    request_str = json.dumps(request) + '\n'
    print(f">>> Sending: {json.dumps(request, indent=2)}")
    proc.stdin.write(request_str.encode())
    proc.stdin.flush()
    
    # For notifications, we don't expect a response
    if "id" not in request:
        time.sleep(0.1)
        return None
    
    # Read response for requests
    response_line = proc.stdout.readline().decode()
    if response_line:
        response = json.loads(response_line)
        print(f"<<< Received: {json.dumps(response, indent=2)}")
        return response
    return None

def main():
    # Start the MCP server with INSTANCE_ID
    env = {
        **subprocess.os.environ,
        'INSTANCE_ID': 'test-instance'
    }
    
    proc = subprocess.Popen(
        ['./target/release/MCP-UnifiedThinking'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd='/Users/samuelatagana/Projects/LegacyMind/MCP-UnifiedThinking',
        env=env
    )
    
    try:
        # Step 1: Initialize the connection
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
        
        print("=== Step 1: Initialize ===")
        response = send_request(proc, init_request)
        
        # Step 2: Send initialized notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        
        print("\n=== Step 2: Initialized Notification ===")
        send_request(proc, initialized_notification)
        
        # Step 3: List available tools
        list_tools_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 2
        }
        
        print("\n=== Step 3: List Tools ===")
        response = send_request(proc, list_tools_request)
        
        # Step 4: Call ut_think tool
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
            "id": 3
        }
        
        print("\n=== Step 4: Call ut_think ===")
        response = send_request(proc, think_request)
        
        # Wait a bit for any pending output
        time.sleep(0.5)
        
    except Exception as e:
        print(f"\nError: {e}")
        # Check for stderr output
        stderr = proc.stderr.read().decode()
        if stderr:
            print(f"Stderr: {stderr}")
    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
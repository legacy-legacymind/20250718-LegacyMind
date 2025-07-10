#!/usr/bin/env python3
import json
import subprocess
import sys
import time

def send_request(proc, request):
    """Send a JSON-RPC request and get response"""
    request_str = json.dumps(request) + '\n'
    print(f"Sending: {request_str}")
    proc.stdin.write(request_str.encode())
    proc.stdin.flush()
    
    # Give it a moment
    time.sleep(0.5)
    
    # Read response
    response_line = proc.stdout.readline().decode()
    if response_line:
        print(f"Received: {response_line}")
        return json.loads(response_line)
    else:
        # Check for stderr
        stderr = proc.stderr.read().decode()
        if stderr:
            print(f"Error output: {stderr}")
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
        
        print("=== Initialize ===")
        response = send_request(proc, init_request)
        if response:
            print(f"Response: {json.dumps(response, indent=2)}")
        
        # List available tools
        list_tools_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 2
        }
        
        print("\n=== List Tools ===")
        response = send_request(proc, list_tools_request)
        if response:
            print(f"Available tools: {json.dumps(response, indent=2)}")
        
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
            "id": 3
        }
        
        print("\n=== Call ut_think ===")
        response = send_request(proc, think_request)
        if response:
            print(f"Response: {json.dumps(response, indent=2)}")
        
        # Wait a bit for any pending output
        time.sleep(1)
        
        # Check for any remaining stderr
        proc.stdin.close()
        remaining_err = proc.stderr.read().decode()
        if remaining_err:
            print(f"\nRemaining error output: {remaining_err}")
        
    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
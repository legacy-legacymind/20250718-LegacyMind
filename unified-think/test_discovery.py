#!/usr/bin/env python3
"""Test tool discovery for unified-think MCP server."""

import subprocess
import json
import sys
import os

def test_tool_discovery():
    """Send tools/list request to the MCP server."""
    
    # Initialize request
    init_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    # List tools request
    list_tools_request = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2
    }
    
    # Run the server with test Redis config
    env = {
        "REDIS_PASSWORD": "test_password",
        "REDIS_URL": "redis://localhost:6379",
        "INSTANCE_ID": "test"
    }
    process = subprocess.Popen(
        ["./target/debug/unified-think"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, **env}
    )
    
    try:
        # Check if process started
        if process.poll() is not None:
            stderr = process.stderr.read()
            print("Process exited early with stderr:", stderr)
            return
            
        # Send initialize
        process.stdin.write(json.dumps(init_request) + '\n')
        process.stdin.flush()
        
        # Read initialize response
        init_response = process.stdout.readline()
        print("Initialize response:", init_response)
        
        # Check for errors
        stderr_line = process.stderr.readline()
        if stderr_line:
            print("Stderr:", stderr_line)
        
        # Send tools/list
        process.stdin.write(json.dumps(list_tools_request) + '\n')
        process.stdin.flush()
        
        # Read tools response
        tools_response = process.stdout.readline()
        print("\nTools response:", tools_response)
        
        # Parse and display tools
        if tools_response:
            try:
                response_data = json.loads(tools_response)
                if "result" in response_data and "tools" in response_data["result"]:
                    tools = response_data["result"]["tools"]
                    print(f"\nDiscovered {len(tools)} tools:")
                    for tool in tools:
                        print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                else:
                    print("\nNo tools found in response")
            except json.JSONDecodeError as e:
                print(f"\nError parsing response: {e}")
        
    except Exception as e:
        print(f"\nError: {e}")
        
    finally:
        # Read any remaining output
        stderr_output = process.stderr.read()
        if stderr_output:
            print("\nAll stderr output:")
            print(stderr_output)
        process.terminate()
        process.wait()

if __name__ == "__main__":
    test_tool_discovery()
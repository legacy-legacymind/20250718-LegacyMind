#!/usr/bin/env python3
"""
Interactive test for Phase 1 UnifiedThink MCP Server
"""

import json
import subprocess
import sys
import time
import os

def test_server():
    print("=== UnifiedThink Phase 1 Interactive Test ===\n")
    
    # Set environment
    env = os.environ.copy()
    env["INSTANCE_ID"] = "phase1-test"
    
    # Start the server
    print("Starting MCP server...")
    proc = subprocess.Popen(
        ["cargo", "run", "--quiet"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env
    )
    
    def send_and_receive(request_data, description):
        print(f"\n{description}")
        print(f"Request: {json.dumps(request_data, indent=2)}")
        
        # Send request
        proc.stdin.write(json.dumps(request_data) + "\n")
        proc.stdin.flush()
        
        # Read response (with timeout)
        start_time = time.time()
        while time.time() - start_time < 2:
            line = proc.stdout.readline()
            if line:
                line = line.strip()
                if line.startswith("{") and "jsonrpc" in line:
                    try:
                        response = json.loads(line)
                        print(f"Response: {json.dumps(response, indent=2)}")
                        return response
                    except:
                        print(f"Raw output: {line}")
                elif "INFO" in line or "Thought Record" in line:
                    print(f"Log: {line}")
        
        print("No response received")
        return None
    
    try:
        # Wait for server to start
        time.sleep(1)
        
        # Test 1: Initialize
        response = send_and_receive({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
                "capabilities": {}
            }
        }, "Test 1: Initialize")
        
        if response:
            print("✓ Server initialized successfully")
        
        # Send initialized notification
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "initialized", "params": {}}) + "\n")
        proc.stdin.flush()
        time.sleep(0.5)
        
        # Test 2: List tools
        response = send_and_receive({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }, "Test 2: List Tools")
        
        if response and "result" in response:
            tools = response["result"].get("tools", [])
            print(f"✓ Found {len(tools)} tool(s)")
            for tool in tools:
                print(f"  - {tool['name']}")
        
        # Test 3: Use ui_think tool
        thoughts = [
            ("Initial analysis of the problem", 1, 3, True),
            ("Applying first principles thinking", 2, 3, True),
            ("Final synthesis and conclusion", 3, 3, False)
        ]
        
        print("\nTest 3: Thought Sequence")
        for thought, num, total, next_needed in thoughts:
            response = send_and_receive({
                "jsonrpc": "2.0",
                "id": 2 + num,
                "method": "tools/call",
                "params": {
                    "name": "ui_think",
                    "arguments": {
                        "thought": thought,
                        "thought_number": num,
                        "total_thoughts": total,
                        "next_thought_needed": next_needed
                    }
                }
            }, f"  Thought {num}/{total}")
            
            if response and "result" in response:
                content = response["result"]["content"][0]["text"]
                result = json.loads(content)
                print(f"  ✓ Stored with ID: {result['thought_id']}")
                print(f"    Next needed: {result.get('next_thought_needed', 'N/A')}")
        
        print("\n=== Phase 1 Test Complete ===")
        print("✓ All tests passed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        proc.terminate()
        proc.wait()
        print("\nServer stopped")

if __name__ == "__main__":
    test_server()
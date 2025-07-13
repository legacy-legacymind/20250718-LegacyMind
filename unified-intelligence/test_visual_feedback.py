#!/usr/bin/env python3
"""Test visual feedback for ui_think."""

import json
import subprocess
import sys
import os

def test_visual_feedback():
    """Test the visual feedback implementation."""
    
    # Build the project first
    print("Building unified-intelligence...")
    build_result = subprocess.run(
        ['cargo', 'build', '--release'],
        cwd='/Users/samuelatagana/Projects/LegacyMind/unified-intelligence',
        capture_output=True,
        text=True
    )
    
    if build_result.returncode != 0:
        print(f"Build failed: {build_result.stderr}")
        return False
    
    print("Build successful!")
    
    # Start the MCP server
    env = os.environ.copy()
    env.update({
        'REDIS_PASSWORD': 'legacymind_redis_pass',
        'INSTANCE_ID': 'Claude'
    })
    
    proc = subprocess.Popen(
        ['./target/release/unified-intelligence'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        cwd='/Users/samuelatagana/Projects/LegacyMind/unified-intelligence'
    )
    
    try:
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        proc.stdin.write(json.dumps(init_request) + '\n')
        proc.stdin.flush()
        
        # Read response
        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            print(f"Initialize response: {response}")
        
        # Send ui_think request to test visual feedback
        think_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Testing visual feedback implementation - this should show colored output",
                    "thought_number": 1,
                    "total_thoughts": 3,
                    "next_thought_needed": True
                }
            }
        }
        
        proc.stdin.write(json.dumps(think_request) + '\n')
        proc.stdin.flush()
        
        # Read response
        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            print(f"Think response: {response}")
        
        # Send another thought to test progression
        think_request2 = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Second thought in the sequence - testing chain functionality",
                    "thought_number": 2,
                    "total_thoughts": 3,
                    "next_thought_needed": True,
                    "chain_id": "test-visual-chain"
                }
            }
        }
        
        proc.stdin.write(json.dumps(think_request2) + '\n')
        proc.stdin.flush()
        
        # Read response
        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            print(f"Think 2 response: {response}")
        
        # Final thought
        think_request3 = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Final thought - visual feedback testing complete",
                    "thought_number": 3,
                    "total_thoughts": 3,
                    "next_thought_needed": False,
                    "chain_id": "test-visual-chain"
                }
            }
        }
        
        proc.stdin.write(json.dumps(think_request3) + '\n')
        proc.stdin.flush()
        
        # Read response
        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            print(f"Think 3 response: {response}")
        
        # Check stderr for visual output
        print("\n=== Visual Output (stderr) ===")
        proc.stdin.close()
        stderr_output = proc.stderr.read()
        print(stderr_output)
        
        return True
        
    except Exception as e:
        print(f"Test failed: {e}")
        return False
    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    success = test_visual_feedback()
    sys.exit(0 if success else 1)
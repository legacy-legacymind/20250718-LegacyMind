#!/usr/bin/env python3
"""Simple test for visual feedback."""

import json
import subprocess
import time
import os

def main():
    env = os.environ.copy()
    env.update({
        'REDIS_PASSWORD': 'legacymind_redis_pass',
        'INSTANCE_ID': 'Claude'
    })
    
    # Start server
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
        # Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        }
        proc.stdin.write(json.dumps(init_msg) + '\n')
        proc.stdin.flush()
        
        # Wait and read init response
        time.sleep(0.1)
        
        # Send initialized notification
        initialized_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        proc.stdin.write(json.dumps(initialized_msg) + '\n')
        proc.stdin.flush()
        
        # Send ui_think request
        think_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Testing visual feedback - this should show colored output!",
                    "thought_number": 1,
                    "total_thoughts": 2,
                    "next_thought_needed": True
                }
            }
        }
        proc.stdin.write(json.dumps(think_msg) + '\n')
        proc.stdin.flush()
        
        time.sleep(0.5)  # Let it process
        
        # Second thought
        think_msg2 = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Second thought with visual feedback complete!",
                    "thought_number": 2,
                    "total_thoughts": 2,
                    "next_thought_needed": False,
                    "chain_id": "visual-test-chain"
                }
            }
        }
        proc.stdin.write(json.dumps(think_msg2) + '\n')
        proc.stdin.flush()
        
        time.sleep(0.5)
        
        # Read all output
        proc.stdin.close()
        stdout, stderr = proc.communicate(timeout=5)
        
        print("=== STDOUT ===")
        print(stdout)
        print("\n=== STDERR (Visual Output) ===")
        print(stderr)
        
    except Exception as e:
        print(f"Error: {e}")
        proc.terminate()

if __name__ == "__main__":
    main()
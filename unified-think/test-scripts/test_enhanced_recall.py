#!/usr/bin/env python3
"""Test script for enhanced ui_recall functionality"""

import json
import subprocess
import sys
import time

def send_message(proc, message):
    """Send a JSON-RPC message to the server"""
    msg_str = json.dumps(message) + '\n'
    proc.stdin.write(msg_str.encode())
    proc.stdin.flush()
    print(f"SENT: {msg_str.strip()}")

def read_response(proc, timeout=5):
    """Read a response from the server"""
    import select
    
    # Use select to implement timeout
    ready, _, _ = select.select([proc.stdout], [], [], timeout)
    if ready:
        line = proc.stdout.readline().decode().strip()
        if line:
            print(f"RECEIVED: {line}")
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                return {"raw": line}
    return None

def test_enhanced_recall():
    """Test the enhanced ui_recall functionality"""
    print("Starting unified-think server...")
    
    # Start the server
    proc = subprocess.Popen(
        ['./target/release/unified-think'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False
    )
    
    try:
        # Give server time to start
        time.sleep(0.5)
        
        # 1. Initialize
        print("\n=== INITIALIZATION ===")
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        })
        
        response = read_response(proc)
        if response:
            print(f"Init response: {json.dumps(response, indent=2)}")
        
        # 2. Send initialized notification
        send_message(proc, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })
        
        # 3. Store some test thoughts first
        print("\n=== STORING TEST THOUGHTS ===")
        thoughts = [
            ("Redis performance optimization strategies", "perf-chain"),
            ("Understanding Redis memory management", "memory-chain"),
            ("Redis cluster configuration best practices", "config-chain")
        ]
        
        for i, (thought, chain) in enumerate(thoughts):
            send_message(proc, {
                "jsonrpc": "2.0",
                "id": 10 + i,
                "method": "tools/call",
                "params": {
                    "name": "ui_think",
                    "arguments": {
                        "thought": thought,
                        "thought_number": 1,
                        "total_thoughts": 1,
                        "next_thought_needed": False,
                        "chain_id": chain
                    }
                }
            })
            response = read_response(proc)
            if response:
                print(f"Think response {i+1}: {json.dumps(response, indent=2)}")
        
        # 4. Test search functionality
        print("\n=== TESTING SEARCH ===")
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "Redis",
                    "action": "search"
                }
            }
        })
        
        response = read_response(proc, timeout=10)
        if response:
            print(f"Search response: {json.dumps(response, indent=2)}")
        
        # 5. Test analyze functionality
        print("\n=== TESTING ANALYZE ===")
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "Redis",
                    "action": "analyze"
                }
            }
        })
        
        response = read_response(proc, timeout=10)
        if response:
            print(f"Analyze response: {json.dumps(response, indent=2)}")
        
        # Check stderr for any errors
        time.sleep(1)
        stderr = proc.stderr.read().decode()
        if stderr:
            print(f"\nServer logs:\n{stderr}")
        
    finally:
        # Clean shutdown
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)
        print("\nServer shut down")

if __name__ == "__main__":
    test_enhanced_recall()
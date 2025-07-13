#!/usr/bin/env python3
"""Test search optimization with debug output visible"""

import json
import subprocess
import sys
import time
import uuid

def test_search_debug():
    """Test search with debug output"""
    # Start the server with RUST_LOG=debug
    env = {
        'INSTANCE_ID': 'search-debug',
        'REDIS_PASSWORD': 'legacymind_redis_pass',
        'REDIS_HOST': '192.168.1.160',
        'RUST_LOG': 'unified_think=debug',
        'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin'
    }
    
    proc = subprocess.Popen(
        ['./target/release/unified-think'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env
    )
    
    try:
        # Initialize
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "search-debug-test",
                    "version": "1.0.0"
                }
            },
            "id": 1
        }) + '\n')
        proc.stdin.flush()
        
        time.sleep(0.5)
        
        # Send initialized notification
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }) + '\n')
        proc.stdin.flush()
        
        time.sleep(0.5)
        
        # Create a test thought
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Redis performance optimization is important",
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False
                }
            },
            "id": 10
        }) + '\n')
        proc.stdin.flush()
        
        time.sleep(0.5)
        
        # Search for it
        print("Sending search request...")
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "performance",
                    "limit": 10
                }
            },
            "id": 100
        }) + '\n')
        proc.stdin.flush()
        
        time.sleep(1)
        
        # Read all output
        proc.terminate()
        stdout = proc.stdout.read()
        stderr = proc.stderr.read()
        
        print("\n=== STDOUT ===")
        for line in stdout.split('\n'):
            if line.strip():
                try:
                    data = json.loads(line)
                    if data.get('id') == 100:
                        print(f"Search result: {json.dumps(data, indent=2)}")
                except:
                    pass
        
        print("\n=== DEBUG LOGS (filtered) ===")
        for line in stderr.split('\n'):
            if any(keyword in line.lower() for keyword in ['search', 'scan', 'batch', 'cache', 'fallback']):
                print(line)
        
    finally:
        proc.terminate()

if __name__ == "__main__":
    test_search_debug()
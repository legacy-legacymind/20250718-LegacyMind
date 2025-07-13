#!/usr/bin/env python3
"""Test atomic operations with Lua scripts"""

import subprocess
import json
import time
import uuid

def send_request(request):
    """Send a JSON-RPC request to the server"""
    try:
        proc = subprocess.Popen(
            ['cargo', 'run'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )
        output, _ = proc.communicate(input=json.dumps(request))
        
        # Parse the JSON-RPC response
        for line in output.strip().split('\n'):
            if line.strip().startswith('{'):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        return None
    except Exception as e:
        print(f"Error sending request: {e}")
        return None

def main():
    print("Testing Lua script atomic operations...")
    
    # Test 1: Store a thought
    chain_id = f"test-chain-{uuid.uuid4()}"
    thought_content = f"Testing Lua atomicity at {time.time()}"
    
    print(f"\n1. Storing thought in chain {chain_id}")
    response = send_request({
        "jsonrpc": "2.0",
        "method": "ui_think",
        "params": {
            "thought": thought_content,
            "thought_number": 1,
            "total_thoughts": 3,
            "next_thought_needed": True,
            "chain_id": chain_id
        },
        "id": 1
    })
    
    if response and 'result' in response:
        print(f"   Success: {response['result'].get('success', False)}")
        print(f"   Message: {response['result'].get('message', '')}")
    else:
        print(f"   Error: {response}")
    
    # Test 2: Store the same thought again (should be detected as duplicate)
    print(f"\n2. Storing the same thought again...")
    response = send_request({
        "jsonrpc": "2.0",
        "method": "ui_think",
        "params": {
            "thought": thought_content,
            "thought_number": 2,
            "total_thoughts": 3,
            "next_thought_needed": True,
            "chain_id": chain_id
        },
        "id": 2
    })
    
    if response and 'result' in response:
        print(f"   Success: {response['result'].get('success', False)}")
        print(f"   Message: {response['result'].get('message', '')}")
        # Check if duplicate was detected in logs
    else:
        print(f"   Error: {response}")
    
    # Test 3: Store a different thought
    print(f"\n3. Storing a different thought...")
    response = send_request({
        "jsonrpc": "2.0",
        "method": "ui_think",
        "params": {
            "thought": f"Different thought at {time.time()}",
            "thought_number": 3,
            "total_thoughts": 3,
            "next_thought_needed": False,
            "chain_id": chain_id
        },
        "id": 3
    })
    
    if response and 'result' in response:
        print(f"   Success: {response['result'].get('success', False)}")
        print(f"   Message: {response['result'].get('message', '')}")
    else:
        print(f"   Error: {response}")
    
    # Test 4: Recall the chain
    print(f"\n4. Recalling chain {chain_id}...")
    response = send_request({
        "jsonrpc": "2.0",
        "method": "ui_recall",
        "params": {
            "chain_id": chain_id,
            "action": "search"
        },
        "id": 4
    })
    
    if response and 'result' in response:
        thoughts = response['result'].get('thoughts', [])
        print(f"   Found {len(thoughts)} thoughts")
        for i, thought in enumerate(thoughts):
            print(f"   {i+1}. Number {thought.get('thought_number')}: {thought.get('thought', '')[:50]}...")
    else:
        print(f"   Error: {response}")
    
    print("\nTest complete!")

if __name__ == "__main__":
    main()
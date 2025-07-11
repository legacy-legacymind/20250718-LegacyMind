#!/usr/bin/env python3
"""
Simple validation test to verify input validation is working
"""

import json
import subprocess
import sys
import os
import time

def test_validation():
    """Test that input validation is properly working"""
    
    # Set environment variables
    env = os.environ.copy()
    env.update({
        'REDIS_HOST': '192.168.1.160',
        'REDIS_PORT': '6379', 
        'REDIS_PASSWORD': 'legacymind_redis_pass',
        'REDIS_DB': '0',
        'INSTANCE_ID': 'validation-test',
        'MAX_THOUGHT_LENGTH': '10000',
        'MAX_THOUGHTS_PER_CHAIN': '1000'
    })
    
    print("Testing input validation...")
    
    # Start the server
    process = subprocess.Popen(
        ['cargo', 'run', '--release'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd='/Users/samuelatagana/Projects/LegacyMind/unified-think-phase3/unified-think'
    )
    
    try:
        # Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "validation-test", "version": "1.0.0"}
            }
        }
        
        process.stdin.write(json.dumps(init_msg) + '\n')
        process.stdin.flush()
        
        response = process.stdout.readline()
        init_response = json.loads(response.strip())
        print(f"Initialize response: {init_response}")
        
        # Send initialized notification
        initialized_msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        process.stdin.write(json.dumps(initialized_msg) + '\n')
        process.stdin.flush()
        
        # Test 1: Valid input (should succeed)
        print("\n1. Testing valid input...")
        valid_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "This is a valid thought",
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False
                }
            }
        }
        
        process.stdin.write(json.dumps(valid_msg) + '\n')
        process.stdin.flush()
        
        response = process.stdout.readline()
        valid_response = json.loads(response.strip())
        
        if 'error' not in valid_response:
            print("✅ Valid input accepted")
        else:
            print(f"❌ Valid input rejected: {valid_response['error']}")
            
        # Test 2: Empty thought (should fail)
        print("\n2. Testing empty thought...")
        empty_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "",
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False
                }
            }
        }
        
        process.stdin.write(json.dumps(empty_msg) + '\n')
        process.stdin.flush()
        
        response = process.stdout.readline()
        empty_response = json.loads(response.strip())
        
        if 'error' in empty_response and 'empty' in empty_response['error']['message'].lower():
            print("✅ Empty thought rejected")
        else:
            print(f"❌ Empty thought not rejected: {empty_response}")
            
        # Test 3: Invalid thought number (should fail)
        print("\n3. Testing invalid thought number...")
        invalid_msg = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Test thought",
                    "thought_number": 0,
                    "total_thoughts": 1,
                    "next_thought_needed": False
                }
            }
        }
        
        process.stdin.write(json.dumps(invalid_msg) + '\n')
        process.stdin.flush()
        
        response = process.stdout.readline()
        invalid_response = json.loads(response.strip())
        
        if 'error' in invalid_response and 'invalid thought number' in invalid_response['error']['message'].lower():
            print("✅ Invalid thought number rejected")
        else:
            print(f"❌ Invalid thought number not rejected: {invalid_response}")
            
        # Test 4: Oversized content (should fail)
        print("\n4. Testing oversized content...")
        oversized_msg = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "x" * 10001,  # Over the 10000 limit
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False
                }
            }
        }
        
        process.stdin.write(json.dumps(oversized_msg) + '\n')
        process.stdin.flush()
        
        response = process.stdout.readline()
        oversized_response = json.loads(response.strip())
        
        if 'error' in oversized_response and 'too long' in oversized_response['error']['message'].lower():
            print("✅ Oversized content rejected")
        else:
            print(f"❌ Oversized content not rejected: {oversized_response}")
            
        # Test 5: Invalid chain ID (should fail)
        print("\n5. Testing invalid chain ID...")
        invalid_chain_msg = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Test thought",
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False,
                    "chain_id": "not-a-valid-uuid"
                }
            }
        }
        
        process.stdin.write(json.dumps(invalid_chain_msg) + '\n')
        process.stdin.flush()
        
        response = process.stdout.readline()
        invalid_chain_response = json.loads(response.strip())
        
        if 'error' in invalid_chain_response and 'invalid chain id' in invalid_chain_response['error']['message'].lower():
            print("✅ Invalid chain ID rejected")
        else:
            print(f"❌ Invalid chain ID not rejected: {invalid_chain_response}")
            
        print("\n✅ Validation testing completed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__":
    test_validation()
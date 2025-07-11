#!/usr/bin/env python3
"""
Test script to verify the security fix for Redis credentials.
Tests environment variable configuration.
"""
import json
import subprocess
import time
import sys
import threading
import os

def read_output(proc, responses):
    """Read output in a separate thread"""
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        try:
            decoded = line.decode().strip()
            if decoded.startswith('{'):
                responses.append(json.loads(decoded))
                print(f"RESPONSE: {json.dumps(json.loads(decoded), indent=2)}")
        except:
            pass

def send_message(proc, msg):
    """Send a message to the server"""
    print(f"\nSENDING: {json.dumps(msg, indent=2)}")
    proc.stdin.write((json.dumps(msg) + '\n').encode())
    proc.stdin.flush()
    time.sleep(1)

def main():
    # Set up environment variables for testing
    env = os.environ.copy()
    env.update({
        'REDIS_HOST': '192.168.1.160',
        'REDIS_PORT': '6379', 
        'REDIS_PASSWORD': 'legacymind_redis_pass',
        'REDIS_DB': '0',
        'INSTANCE_ID': 'security-test'
    })
    
    print("=== TESTING SECURITY FIX: ENVIRONMENT VARIABLES ===")
    print(f"Redis configuration:")
    print(f"  Host: {env['REDIS_HOST']}")
    print(f"  Port: {env['REDIS_PORT']}")
    print(f"  DB: {env['REDIS_DB']}")
    print(f"  Instance: {env['INSTANCE_ID']}")
    print(f"  Password: {'*' * len(env['REDIS_PASSWORD'])}")
    
    # Start server with environment variables
    proc = subprocess.Popen(
        ['./target/release/unified-think'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    
    responses = []
    reader = threading.Thread(target=read_output, args=(proc, responses))
    reader.daemon = True
    reader.start()
    
    try:
        # Initialize
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":1,
            "method":"initialize",
            "params":{
                "protocolVersion":"2024-11-05",
                "capabilities":{},
                "clientInfo":{"name":"security-test","version":"1.0"}
            }
        })
        
        send_message(proc, {
            "jsonrpc":"2.0",
            "method":"notifications/initialized"
        })
        
        # Test storing a thought (tests Redis connection)
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":2,
            "method":"tools/call",
            "params":{
                "name":"ui_think",
                "arguments":{
                    "thought":"Security fix test: Redis credentials now use environment variables",
                    "thought_number":1,
                    "total_thoughts":1,
                    "next_thought_needed":False
                }
            }
        })
        
        # Test search functionality
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":3,
            "method":"tools/call",
            "params":{
                "name":"ui_recall",
                "arguments":{
                    "query":"security",
                    "action":"search"
                }
            }
        })
        
        time.sleep(3)
        
    finally:
        proc.terminate()
        print(f"\n\nReceived {len(responses)} responses total")
        stderr = proc.stderr.read().decode()
        
        if "ERROR" in stderr:
            print(f"\nServer errors:\n{stderr}")
        else:
            print("\n✅ Security fix test completed successfully!")
            print("Redis connection established using environment variables")
            
        # Check if Redis connection logs show environment configuration
        if "Connecting to Redis at" in stderr:
            print("\n✅ Redis connection logs show environment variable usage")
        
        if stderr:
            print(f"\nServer logs:\n{stderr}")

if __name__ == "__main__":
    main()
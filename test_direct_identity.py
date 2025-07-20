#!/usr/bin/env python3
import sys
import os
import json
import subprocess

# Test the unified-intelligence binary directly
print("Testing unified-intelligence identity retrieval directly...\n")

# Create a test request
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "ui_identity",
        "arguments": {
            "operation": "view"
        }
    }
}

# Write request to a file
with open('/tmp/test_identity_request.json', 'w') as f:
    json.dump(request, f)

# Run the unified-intelligence binary directly
binary_path = "/Users/samuelatagana/Projects/LegacyMind/unified-intelligence-dev/unified-intelligence/target/debug/unified-intelligence"

if os.path.exists(binary_path):
    print(f"Running: {binary_path}")
    print(f"Request: {json.dumps(request, indent=2)}")
    print("\nResponse:")
    
    try:
        # Set environment variables
        env = os.environ.copy()
        env['REDIS_PASSWORD'] = 'legacymind_redis_pass'
        env['INSTANCE_ID'] = 'CC'
        
        # Run the binary with the request
        process = subprocess.Popen(
            [binary_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        # Send the request
        stdout, stderr = process.communicate(input=json.dumps(request))
        
        if stdout:
            print("STDOUT:")
            print(stdout)
            
        if stderr:
            print("\nSTDERR:")
            print(stderr)
            
    except Exception as e:
        print(f"Error running binary: {e}")
else:
    print(f"Binary not found at: {binary_path}")
    print("Please build the project first with: cargo build")
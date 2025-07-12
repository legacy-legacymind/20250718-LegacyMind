#!/usr/bin/env python3
"""Simple tool discovery test."""

import subprocess
import json
import time
import os

# Set environment
env = {
    "INSTANCE_ID": "test",
    "ALLOW_DEFAULT_REDIS_PASSWORD": "1",
    "RUST_LOG": "error"
}

# Start server
print("Starting server...")
proc = subprocess.Popen(
    ["cargo", "run"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env={**os.environ, **env}
)

# Send initialize
init_req = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {}
    }
}

print("Sending initialize...")
proc.stdin.write(json.dumps(init_req) + '\n')
proc.stdin.flush()

# Read response
print("Reading initialize response...")
response = proc.stdout.readline()
print(f"Initialize response: {response}")

# Send tools/list
tools_req = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
}

print("\nSending tools/list...")
proc.stdin.write(json.dumps(tools_req) + '\n')
proc.stdin.flush()

# Read response
print("Reading tools response...")
response = proc.stdout.readline()
print(f"Tools response: {response}")

# Parse and display
if response:
    try:
        data = json.loads(response)
        if "result" in data and "tools" in data["result"]:
            tools = data["result"]["tools"]
            print(f"\nFound {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
    except:
        pass

# Cleanup
proc.terminate()
proc.wait()

# Show any errors
stderr = proc.stderr.read()
if stderr:
    print(f"\nStderr: {stderr}")
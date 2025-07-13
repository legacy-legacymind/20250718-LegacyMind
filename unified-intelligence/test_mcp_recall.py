#!/usr/bin/env python3
"""Test ui_recall via MCP protocol."""

import json
import subprocess
import sys

# MCP tool call request
mcp_request = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "ui_recall",
        "arguments": {
            "instance_id": "Claude",
            "limit": 5
        }
    },
    "id": 1
}

print("Testing ui_recall via MCP...")
print("Request:", json.dumps(mcp_request))

# Run with unified-think
proc = subprocess.Popen(
    ["./target/release/unified-think"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env={"REDIS_PASSWORD": "legacymind_redis_pass", "PATH": "/usr/bin:/bin"},
    text=True
)

# Send request and get response
stdout, stderr = proc.communicate(json.dumps(mcp_request) + "\n")

print("\n--- STDOUT ---")
print(stdout)
print("\n--- STDERR ---")
print(stderr)

# Parse response if we got one
if stdout:
    try:
        response = json.loads(stdout)
        print("\n--- PARSED RESPONSE ---")
        print(json.dumps(response, indent=2))
    except:
        print("Could not parse response as JSON")
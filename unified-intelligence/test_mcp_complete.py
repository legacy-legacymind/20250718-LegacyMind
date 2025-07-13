#!/usr/bin/env python3
"""Complete MCP test with proper initialization and ui_recall test."""

import json
import subprocess
import sys

# First send initialization
init_request = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "protocolVersion": "0.1.0",
        "capabilities": {
            "roots": {
                "listChanged": True
            },
            "sampling": {}
        },
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    },
    "id": 1
}

# Then call ui_recall
recall_request = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "ui_recall",
        "arguments": {
            "instance_id": "Claude",
            "limit": 5
        }
    },
    "id": 2
}

print("Testing ui_recall with proper MCP initialization...")

# Run with unified-intelligence
proc = subprocess.Popen(
    ["./target/release/unified-intelligence"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env={"REDIS_PASSWORD": "legacymind_redis_pass", "INSTANCE_ID": "Claude", "OPENAI_API_KEY": "sk-test-key-for-verification", "PATH": "/usr/bin:/bin"},
    text=True
)

# Send initialization
proc.stdin.write(json.dumps(init_request) + "\n")
proc.stdin.flush()

# Read initialization response
init_response = proc.stdout.readline()
print("\n--- INIT RESPONSE ---")
print(init_response)

# Send initialized notification
initialized_notif = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized"
}
proc.stdin.write(json.dumps(initialized_notif) + "\n")
proc.stdin.flush()

# Send recall request
proc.stdin.write(json.dumps(recall_request) + "\n")
proc.stdin.flush()

# Read recall response
recall_response = proc.stdout.readline()
print("\n--- RECALL RESPONSE ---")
print(recall_response)

# Close stdin and wait for process to finish
proc.stdin.close()
proc.wait()

# Print stderr if any
stderr = proc.stderr.read()
if stderr:
    print("\n--- STDERR ---")
    print(stderr)
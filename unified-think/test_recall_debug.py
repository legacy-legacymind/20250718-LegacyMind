#!/usr/bin/env python3
"""Debug ui_recall Redis type error."""

import json
import subprocess
import time

# Test just ui_recall
recall_request = {
    "jsonrpc": "2.0",
    "method": "ui_recall",
    "params": {
        "instance_id": "Claude",
        "limit": 5
    },
    "id": 1
}

print("Testing ui_recall...")
print(json.dumps(recall_request))

# Run with unified-think
proc = subprocess.Popen(
    ["./target/release/unified-think"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env={"REDIS_PASSWORD": "legacymind_redis_pass", "PATH": "/usr/bin:/bin"},
    text=True
)

# Send request
output, error = proc.communicate(json.dumps(recall_request))

print("\nOutput:")
print(output)
print("\nError:")
print(error)
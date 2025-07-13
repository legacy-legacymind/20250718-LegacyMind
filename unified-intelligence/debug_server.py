#!/usr/bin/env python3
"""Debug server communication."""

import subprocess
import json
import os
import time

# Set environment
env = {
    "INSTANCE_ID": "test",
    "ALLOW_DEFAULT_REDIS_PASSWORD": "1"
}

# Start server
print("Starting server...")
proc = subprocess.Popen(
    ["./target/debug/unified-think"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env={**os.environ, **env},
    bufsize=0
)

time.sleep(1)  # Let server start

# Check if still running
if proc.poll() is not None:
    print("Server exited early!")
    print("Stdout:", proc.stdout.read())
    print("Stderr:", proc.stderr.read())
    exit(1)

# Send initialize with proper formatting
init_req = {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}
req_str = json.dumps(init_req)
print(f"Sending: {req_str}")
proc.stdin.write(req_str + '\n')
proc.stdin.flush()

# Wait and read
time.sleep(0.5)

# Read stdout line by line
print("\nReading stdout...")
while True:
    try:
        line = proc.stdout.readline()
        if line:
            print(f"Stdout: {line.strip()}")
            # If we got the initialize response, send tools/list
            if "serverInfo" in line:
                tools_req = {"jsonrpc":"2.0","id":2,"method":"tools/list"}
                req_str = json.dumps(tools_req)
                print(f"\nSending: {req_str}")
                proc.stdin.write(req_str + '\n')
                proc.stdin.flush()
                time.sleep(0.5)
                # Read tools response
                tools_line = proc.stdout.readline()
                if tools_line:
                    print(f"Tools response: {tools_line.strip()}")
                    # Parse it
                    try:
                        data = json.loads(tools_line)
                        if "result" in data and "tools" in data["result"]:
                            tools = data["result"]["tools"]
                            print(f"\nDiscovered {len(tools)} tools:")
                            for tool in tools:
                                print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                    except Exception as e:
                        print(f"Parse error: {e}")
                break
        else:
            break
    except:
        break

# Cleanup
time.sleep(0.5)
proc.terminate()

# Show any stderr
stderr = proc.stderr.read()
if stderr:
    print(f"\nStderr output:\n{stderr}")
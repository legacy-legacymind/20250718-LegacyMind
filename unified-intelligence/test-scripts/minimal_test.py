#!/usr/bin/env python3
"""
Minimal test without initialized notification
"""

import json
import subprocess
import time
import sys
import select

def read_available_output(process, timeout=0.1):
    """Read all available output from stdout."""
    outputs = []
    while True:
        ready, _, _ = select.select([process.stdout], [], [], timeout)
        if ready:
            line = process.stdout.readline()
            if line:
                outputs.append(line.strip())
            else:
                break
        else:
            break
    return outputs

def main():
    # Start server
    print("Starting unified-think server...")
    process = subprocess.Popen(
        ["./target/debug/unified-think"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**subprocess.os.environ, "INSTANCE_ID": "minimal-test"}
    )
    
    # Monitor stderr in background
    import threading
    def read_stderr():
        while True:
            line = process.stderr.readline()
            if not line:
                break
            print(f"[STDERR] {line.strip()}")
    
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()
    
    try:
        time.sleep(0.5)  # Let server start
        
        # 1. Initialize only (no initialized notification)
        print("\n1. Sending initialize...")
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "minimal-test", "version": "1.0"}
            }
        }
        
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        
        # Read response
        outputs = read_available_output(process, timeout=2.0)
        for output in outputs:
            try:
                response = json.loads(output)
                print(f"Response: {json.dumps(response, indent=2)}")
            except:
                print(f"Raw output: {output}")
        
        # Check if still running
        if process.poll() is not None:
            print(f"Server exited with code: {process.returncode}")
            return
        
        # 2. Try to list tools (without initialized notification)
        print("\n2. Sending tools/list...")
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        
        # Read response
        outputs = read_available_output(process, timeout=2.0)
        for output in outputs:
            try:
                response = json.loads(output)
                print(f"Response: {json.dumps(response, indent=2)}")
            except:
                print(f"Raw output: {output}")
        
        print("\nTest completed without sending initialized notification")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        time.sleep(0.5)
        if process.poll() is None:
            process.terminate()
            process.wait()
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
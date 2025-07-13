#!/usr/bin/env python3
"""
Debug test script for unified-think server.
Shows stderr output for troubleshooting.
"""

import json
import subprocess
import time
import threading
import sys

def read_stderr(process):
    """Read and print stderr in a separate thread."""
    while True:
        line = process.stderr.readline()
        if not line:
            break
        print(f"[STDERR] {line.strip()}", file=sys.stderr)

def send_request(process, request):
    """Send request and read response."""
    try:
        request_str = json.dumps(request) + "\n"
        print(f"\n[SEND] {json.dumps(request, indent=2)}")
        process.stdin.write(request_str)
        process.stdin.flush()
        
        # Read response with timeout
        start_time = time.time()
        while time.time() - start_time < 5:
            line = process.stdout.readline()
            if line:
                response = json.loads(line.strip())
                print(f"[RECV] {json.dumps(response, indent=2)}")
                return response
        
        print("[ERROR] Timeout waiting for response")
        return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return None

def main():
    # Start server
    print("Starting unified-think server...")
    process = subprocess.Popen(
        ["./target/debug/unified-think"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**subprocess.os.environ, "INSTANCE_ID": "debug-test", "RUST_LOG": "debug"}
    )
    
    # Start stderr reader
    stderr_thread = threading.Thread(target=read_stderr, args=(process,), daemon=True)
    stderr_thread.start()
    
    try:
        # Give server time to start
        time.sleep(1)
        
        # Check if server is still running
        if process.poll() is not None:
            print(f"[ERROR] Server exited with code: {process.returncode}")
            return
        
        # Initialize
        print("\n=== INITIALIZE ===")
        response = send_request(process, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "debug-test", "version": "1.0"}
            }
        })
        
        if not response:
            print("[ERROR] No response to initialize")
            return
        
        # Send initialized notification
        print("\n=== INITIALIZED NOTIFICATION ===")
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "initialized", "params": {}}) + "\n")
        process.stdin.flush()
        time.sleep(0.5)
        
        # Check if server is still running
        if process.poll() is not None:
            print(f"[ERROR] Server exited after initialize with code: {process.returncode}")
            return
        
        # List tools
        print("\n=== LIST TOOLS ===")
        response = send_request(process, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        
        if not response:
            print("[ERROR] No response to tools/list")
            return
        
        # Store a thought
        print("\n=== STORE THOUGHT ===")
        response = send_request(process, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Debug test of unified-think server",
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False,
                    "chain_id": "debug-test-chain"
                }
            }
        })
        
        if not response:
            print("[ERROR] No response to ui_think")
            
        # Give time for any final stderr output
        time.sleep(1)
        
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
    finally:
        # Check final status
        if process.poll() is None:
            print("\n[INFO] Server still running, terminating...")
            process.terminate()
            process.wait(timeout=5)
        else:
            print(f"\n[INFO] Server exited with code: {process.returncode}")
        
        print("\nTest completed.")

if __name__ == "__main__":
    main()
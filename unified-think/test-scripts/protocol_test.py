#!/usr/bin/env python3
"""
Test that sends exact protocol messages with careful handling.
"""

import subprocess
import time
import sys
import os

def test_protocol():
    # Start server
    print("Starting unified-think server...")
    env = os.environ.copy()
    env["INSTANCE_ID"] = "protocol-test"
    
    process = subprocess.Popen(
        ["./target/debug/unified-think"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    
    # Read stderr in background
    import threading
    def read_stderr():
        while True:
            line = process.stderr.readline()
            if not line:
                break
            sys.stderr.write(line.decode() if isinstance(line, bytes) else line)
            sys.stderr.flush()
    
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()
    
    try:
        # Give server time to start
        time.sleep(1)
        
        # Send initialize
        print("\n1. Sending initialize...")
        init_msg = b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"protocol-test","version":"1.0"}}}\n'
        process.stdin.write(init_msg)
        process.stdin.flush()
        
        # Read response
        response = process.stdout.readline()
        print(f"Response: {response.decode() if isinstance(response, bytes) else response}")
        
        # Small delay
        time.sleep(0.1)
        
        # Send initialized notification
        print("\n2. Sending initialized notification...")
        init_notif = b'{"jsonrpc":"2.0","method":"initialized","params":{}}\n'
        process.stdin.write(init_notif)
        process.stdin.flush()
        
        # Small delay
        time.sleep(0.5)
        
        # Check if still running
        if process.poll() is not None:
            print(f"Server exited with code: {process.returncode}")
            return
        
        # Send tools/list
        print("\n3. Sending tools/list...")
        list_msg = b'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n'
        process.stdin.write(list_msg)
        process.stdin.flush()
        
        # Read response
        response = process.stdout.readline()
        print(f"Response: {response.decode() if isinstance(response, bytes) else response}")
        
        # Send a ui_think request
        print("\n4. Sending ui_think...")
        think_msg = b'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Testing protocol","thought_number":1,"total_thoughts":1,"next_thought_needed":false}}}\n'
        process.stdin.write(think_msg)
        process.stdin.flush()
        
        # Read response
        response = process.stdout.readline()
        print(f"Response: {response.decode() if isinstance(response, bytes) else response}")
        
        print("\n✅ Protocol test completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        time.sleep(0.5)
        process.terminate()
        process.wait()
        print("\nServer stopped.")

if __name__ == "__main__":
    test_protocol()
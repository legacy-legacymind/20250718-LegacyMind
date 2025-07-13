#!/usr/bin/env python3
"""
Test script that uses the exact messages from phase3_test.jsonl
"""

import json
import subprocess
import time
import sys

def main():
    # Read test messages from JSONL file
    with open("phase3_test.jsonl", "r") as f:
        test_messages = [json.loads(line.strip()) for line in f if line.strip()]
    
    # Start server
    print("Starting unified-think server...")
    process = subprocess.Popen(
        ["./target/debug/unified-think"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**subprocess.os.environ, "INSTANCE_ID": "jsonl-test"}
    )
    
    try:
        # Process each test message
        for i, message in enumerate(test_messages):
            # Skip if empty
            if not message:
                continue
                
            print(f"\n--- Message {i+1} ---")
            print(f"Sending: {json.dumps(message, indent=2)}")
            
            # Send message
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
            
            # For notifications, don't wait for response
            if "id" not in message:
                print("(Notification sent)")
                time.sleep(0.2)
                continue
            
            # Wait for response
            timeout = 5
            start_time = time.time()
            response_received = False
            
            while time.time() - start_time < timeout:
                line = process.stdout.readline()
                if line:
                    try:
                        response = json.loads(line.strip())
                        print(f"Response: {json.dumps(response, indent=2)}")
                        response_received = True
                        break
                    except json.JSONDecodeError:
                        print(f"Invalid JSON response: {line}")
                
                # Check if process is still running
                if process.poll() is not None:
                    print(f"Server exited with code: {process.returncode}")
                    stderr = process.stderr.read()
                    if stderr:
                        print(f"Server error:\n{stderr}")
                    return
            
            if not response_received:
                print("No response received (timeout)")
        
        print("\nAll test messages sent successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        if process.poll() is None:
            process.terminate()
            process.wait()
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
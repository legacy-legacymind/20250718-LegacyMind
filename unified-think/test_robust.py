#!/usr/bin/env python3
import json
import subprocess
import time
import sys
import threading

def read_output(proc, responses):
    """Read output in a separate thread"""
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        try:
            decoded = line.decode().strip()
            if decoded.startswith('{'):
                responses.append(json.loads(decoded))
                print(f"RESPONSE: {json.dumps(json.loads(decoded), indent=2)}")
        except:
            pass

def main():
    # Start server
    proc = subprocess.Popen(
        ['./target/release/unified-think'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    responses = []
    reader = threading.Thread(target=read_output, args=(proc, responses))
    reader.daemon = True
    reader.start()
    
    try:
        # 1. Initialize
        msg = {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
        proc.stdin.write((json.dumps(msg) + '\n').encode())
        proc.stdin.flush()
        time.sleep(1)
        
        # 2. Send initialized notification  
        msg = {"jsonrpc":"2.0","method":"notifications/initialized"}
        proc.stdin.write((json.dumps(msg) + '\n').encode())
        proc.stdin.flush()
        time.sleep(1)
        
        # 3. Call ui_think
        msg = {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ui_think","arguments":{"thought":"Test thought","thought_number":1,"total_thoughts":1,"next_thought_needed":False}}}
        proc.stdin.write((json.dumps(msg) + '\n').encode())
        proc.stdin.flush()
        time.sleep(2)
        
        # Keep connection open
        time.sleep(2)
        
    finally:
        proc.terminate()
        print(f"\nReceived {len(responses)} responses")
        stderr = proc.stderr.read().decode()
        if stderr:
            print(f"\nServer stderr:\n{stderr}")

if __name__ == "__main__":
    main()
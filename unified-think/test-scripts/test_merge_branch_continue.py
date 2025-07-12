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

def send_message(proc, msg):
    """Send a message to the server"""
    print(f"\nSENDING: {json.dumps(msg, indent=2)}")
    proc.stdin.write((json.dumps(msg) + '\n').encode())
    proc.stdin.flush()
    time.sleep(1)

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
        # Initialize
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":1,
            "method":"initialize",
            "params":{
                "protocolVersion":"2024-11-05",
                "capabilities":{},
                "clientInfo":{"name":"merge-test","version":"1.0"}
            }
        })
        
        send_message(proc, {
            "jsonrpc":"2.0",
            "method":"notifications/initialized"
        })
        
        # Test MERGE
        print("\n=== TESTING MERGE ===")
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":30,
            "method":"tools/call",
            "params":{
                "name":"ui_recall",
                "arguments":{
                    "query":"Redis",
                    "action":"merge",
                    "action_params":{
                        "new_chain_name":"Redis Knowledge Base"
                    }
                }
            }
        })
        
        time.sleep(2)
        
        # Test BRANCH
        print("\n=== TESTING BRANCH ===")
        # First get a thought ID from previous search
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":31,
            "method":"tools/call",
            "params":{
                "name":"ui_recall",
                "arguments":{
                    "action":"branch",
                    "action_params":{
                        "thought_id":"3bfe66e8-058f-47b3-9493-ac9abad0c0f6",
                        "new_chain_name":"Redis Pipeline Deep Dive"
                    }
                }
            }
        })
        
        time.sleep(2)
        
        # Test CONTINUE
        print("\n=== TESTING CONTINUE ===")
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":32,
            "method":"tools/call",
            "params":{
                "name":"ui_recall",
                "arguments":{
                    "chain_id":"redis-opt-chain",
                    "action":"continue"
                }
            }
        })
        
        time.sleep(2)
        
        # Store a new thought to continue the chain
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":33,
            "method":"tools/call",
            "params":{
                "name":"ui_think",
                "arguments":{
                    "thought":"Redis optimization: Monitor slow log for bottlenecks",
                    "thought_number":3,
                    "total_thoughts":3,
                    "next_thought_needed":False,
                    "chain_id":"redis-opt-chain"
                }
            }
        })
        
        time.sleep(3)
        
    finally:
        proc.terminate()
        print(f"\n\nReceived {len(responses)} responses total")
        stderr = proc.stderr.read().decode()
        if "ERROR" in stderr:
            print(f"\nServer errors:\n{stderr}")

if __name__ == "__main__":
    main()
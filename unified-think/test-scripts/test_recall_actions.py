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
    print(f"\nSENDING: {json.dumps(msg)}")
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
        # 1. Initialize
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":1,
            "method":"initialize",
            "params":{
                "protocolVersion":"2024-11-05",
                "capabilities":{},
                "clientInfo":{"name":"recall-test","version":"1.0"}
            }
        })
        
        # 2. Send initialized notification  
        send_message(proc, {
            "jsonrpc":"2.0",
            "method":"notifications/initialized"
        })
        
        # 3. Store some test thoughts
        print("\n=== STORING TEST THOUGHTS ===")
        thoughts = [
            ("Redis optimization: Use pipelining for batch operations", "redis-opt-chain"),
            ("Redis optimization: Configure proper eviction policies", "redis-opt-chain"),
            ("Memory management: Track allocation patterns", "memory-chain"),
            ("Performance testing: Use benchmarking tools", "perf-chain")
        ]
        
        for i, (thought, chain) in enumerate(thoughts):
            send_message(proc, {
                "jsonrpc":"2.0",
                "id":10 + i,
                "method":"tools/call",
                "params":{
                    "name":"ui_think",
                    "arguments":{
                        "thought":thought,
                        "thought_number":i+1,
                        "total_thoughts":len(thoughts),
                        "next_thought_needed":i < len(thoughts)-1,
                        "chain_id":chain
                    }
                }
            })
        
        time.sleep(2)
        
        # 4. Test search
        print("\n=== TESTING SEARCH ===")
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":20,
            "method":"tools/call",
            "params":{
                "name":"ui_recall",
                "arguments":{
                    "query":"Redis",
                    "action":"search"
                }
            }
        })
        
        time.sleep(2)
        
        # 5. Test chain retrieval
        print("\n=== TESTING CHAIN RETRIEVAL ===")
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":21,
            "method":"tools/call",
            "params":{
                "name":"ui_recall",
                "arguments":{
                    "chain_id":"redis-opt-chain"
                }
            }
        })
        
        time.sleep(2)
        
        # 6. Test analyze
        print("\n=== TESTING ANALYZE ===")
        send_message(proc, {
            "jsonrpc":"2.0",
            "id":22,
            "method":"tools/call",
            "params":{
                "name":"ui_recall",
                "arguments":{
                    "query":"optimization",
                    "action":"analyze"
                }
            }
        })
        
        # Keep connection open to receive all responses
        time.sleep(3)
        
    finally:
        proc.terminate()
        print(f"\n\nReceived {len(responses)} responses total")
        stderr = proc.stderr.read().decode()
        if "ERROR" in stderr:
            print(f"\nServer errors:\n{stderr}")
        else:
            print("\nServer ran without errors")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Test search optimization implementation"""

import json
import subprocess
import threading
import time
import uuid

def send_message(proc, message):
    """Send a JSON-RPC message to the process"""
    msg_str = json.dumps(message) + '\n'
    proc.stdin.write(msg_str)
    proc.stdin.flush()

def read_output(proc, responses):
    """Read output in a separate thread"""
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        try:
            response = json.loads(line)
            responses.append(response)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse line: {line.strip()}")

def test_search_optimization():
    """Test the optimized search functionality"""
    # Start the server
    env = {
        'INSTANCE_ID': 'search-test',
        'REDIS_PASSWORD': 'legacymind_redis_pass',
        'REDIS_HOST': '192.168.1.160',
        'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin'
    }
    
    proc = subprocess.Popen(
        ['./target/release/unified-think'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env
    )
    
    responses = []
    output_thread = threading.Thread(target=read_output, args=(proc, responses))
    output_thread.start()
    
    try:
        # Initialize
        send_message(proc, {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "search-optimization-test",
                    "version": "1.0.0"
                }
            },
            "id": 1
        })
        
        time.sleep(0.5)
        
        # Send initialized notification
        send_message(proc, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })
        
        time.sleep(0.5)
        
        # Create test thoughts with searchable content
        print("Creating test thoughts...")
        chain_id = str(uuid.uuid4())
        
        test_thoughts = [
            "Redis performance optimization is crucial for scalability",
            "The search functionality needs to handle large datasets efficiently",
            "Performance monitoring helps identify bottlenecks",
            "Caching strategies improve Redis query response times",
            "Search optimization reduces network overhead significantly"
        ]
        
        for i, thought_content in enumerate(test_thoughts, 1):
            send_message(proc, {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "ui_think",
                    "arguments": {
                        "thought": thought_content,
                        "thought_number": i,
                        "total_thoughts": len(test_thoughts),
                        "next_thought_needed": i < len(test_thoughts),
                        "chain_id": chain_id
                    }
                },
                "id": i + 10
            })
            time.sleep(0.1)
        
        print("Thoughts created. Testing search...")
        
        # Test 1: Search for "performance" (should find 3 results)
        start_time = time.time()
        send_message(proc, {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "performance",
                    "limit": 10
                }
            },
            "id": 100
        })
        
        time.sleep(0.5)
        search_time_1 = time.time() - start_time
        
        # Test 2: Same search again (should hit cache)
        start_time = time.time()
        send_message(proc, {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "performance",
                    "limit": 10
                }
            },
            "id": 101
        })
        
        time.sleep(0.5)
        search_time_2 = time.time() - start_time
        
        # Test 3: Different search
        start_time = time.time()
        send_message(proc, {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "search",
                    "limit": 5
                }
            },
            "id": 102
        })
        
        time.sleep(0.5)
        search_time_3 = time.time() - start_time
        
        # Process responses
        print("\n=== Search Optimization Test Results ===")
        
        search_results = []
        for resp in responses:
            if resp.get('id') in [100, 101, 102]:
                if 'result' in resp:
                    search_results.append(resp)
                elif 'error' in resp:
                    print(f"Error in search {resp['id']}: {resp['error']}")
        
        # Analyze results
        if len(search_results) >= 2:
            # First search
            result1 = search_results[0]['result']
            thoughts1 = result1.get('thoughts', [])
            print(f"\nFirst search for 'performance':")
            print(f"  - Found {len(thoughts1)} results")
            print(f"  - Time: {search_time_1:.3f}s")
            print(f"  - Search method: {result1.get('source', {}).get('search_method', 'unknown')}")
            
            # Second search (cached)
            result2 = search_results[1]['result']
            thoughts2 = result2.get('thoughts', [])
            print(f"\nSecond search for 'performance' (cached):")
            print(f"  - Found {len(thoughts2)} results")
            print(f"  - Time: {search_time_2:.3f}s")
            print(f"  - Cache speedup: {search_time_1/search_time_2:.1f}x faster")
            
            # Third search
            if len(search_results) >= 3:
                result3 = search_results[2]['result']
                thoughts3 = result3.get('thoughts', [])
                print(f"\nSearch for 'search':")
                print(f"  - Found {len(thoughts3)} results")
                print(f"  - Time: {search_time_3:.3f}s")
        
        print("\n=== Performance Summary ===")
        print(f"Cache effectiveness: {'✅ Working' if search_time_2 < search_time_1 else '❌ Not working'}")
        print(f"All searches completed: {'✅ Yes' if len(search_results) >= 3 else '❌ No'}")
        
    finally:
        proc.terminate()
        output_thread.join(timeout=1)
        
        # Print stderr for debugging
        stderr = proc.stderr.read()
        if stderr:
            print(f"\nServer stderr:\n{stderr}")

if __name__ == "__main__":
    test_search_optimization()
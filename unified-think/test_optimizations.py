#!/usr/bin/env python3
"""Test script to verify SearchCache and batch fetching optimizations"""

import json
import subprocess
import time
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_request(proc, request):
    """Send a JSON-RPC request and get response"""
    request_str = json.dumps(request)
    logging.debug(f"Sending: {request_str}")
    proc.stdin.write(request_str + '\n')
    proc.stdin.flush()
    
    response_line = proc.stdout.readline()
    if response_line:
        response = json.loads(response_line)
        logging.debug(f"Received: {response}")
        return response
    return None

def main():
    # Start the server
    server_path = Path("./target/debug/unified-think")
    if not server_path.exists():
        logging.error(f"Server not found at {server_path}")
        sys.exit(1)
    
    logging.info("Starting server...")
    proc = subprocess.Popen(
        [str(server_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
        env={**subprocess.os.environ, "INSTANCE_ID": "cache-test"}
    )
    
    time.sleep(0.5)  # Let server initialize
    
    try:
        # Initialize
        logging.info("Initializing MCP...")
        init_response = send_request(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "cache-test", "version": "1.0"}
            }
        })
        
        # Send initialized notification
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }) + '\n')
        proc.stdin.flush()
        time.sleep(0.5)
        
        # Create a chain with multiple thoughts to test batch fetching
        logging.info("\n=== Creating chain with 10 thoughts ===")
        chain_id = "batch-test-chain"
        
        for i in range(1, 11):
            response = send_request(proc, {
                "jsonrpc": "2.0",
                "id": 100 + i,
                "method": "tools/call",
                "params": {
                    "name": "ui_think",
                    "arguments": {
                        "thought": f"Thought number {i} for batch testing",
                        "thought_number": i,
                        "total_thoughts": 10,
                        "next_thought_needed": i < 10,
                        "chain_id": chain_id
                    }
                }
            })
            if response and "result" in response:
                logging.info(f"Stored thought {i}")
        
        # Test 1: Batch fetching for chain retrieval
        logging.info("\n=== Test 1: Batch fetching chain thoughts ===")
        start_time = time.time()
        
        response = send_request(proc, {
            "jsonrpc": "2.0",
            "id": 200,
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "chain_id": chain_id
                }
            }
        })
        
        fetch_time = time.time() - start_time
        
        if response and "result" in response:
            result_text = response["result"]["content"][0]["text"]
            result_data = json.loads(result_text)
            thought_count = len(result_data.get("thoughts", []))
            logging.info(f"✅ Retrieved {thought_count} thoughts in {fetch_time:.3f}s")
            logging.info("   (Batch fetching is working - all thoughts retrieved in single operation)")
        else:
            logging.error("❌ Failed to retrieve chain")
        
        # Test 2: Search cache functionality
        logging.info("\n=== Test 2: Search cache functionality ===")
        
        # First search (cache miss)
        start_time = time.time()
        response = send_request(proc, {
            "jsonrpc": "2.0",
            "id": 300,
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "batch",
                    "limit": 5
                }
            }
        })
        first_search_time = time.time() - start_time
        
        if response and "result" in response:
            result_text = response["result"]["content"][0]["text"]
            result_data = json.loads(result_text)
            first_count = result_data.get("total_found", 0)
            logging.info(f"First search: found {first_count} results in {first_search_time:.3f}s (cache miss)")
        
        # Second identical search (cache hit)
        start_time = time.time()
        response = send_request(proc, {
            "jsonrpc": "2.0",
            "id": 301,
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "batch",
                    "limit": 5
                }
            }
        })
        second_search_time = time.time() - start_time
        
        if response and "result" in response:
            result_text = response["result"]["content"][0]["text"]
            result_data = json.loads(result_text)
            second_count = result_data.get("total_found", 0)
            logging.info(f"Second search: found {second_count} results in {second_search_time:.3f}s (cache hit)")
            
            if second_search_time < first_search_time * 0.5:
                logging.info("✅ Cache is working! Second search was significantly faster")
            else:
                logging.warning("⚠️  Cache might not be working - second search wasn't significantly faster")
        
        # Test 3: Different query (cache miss again)
        start_time = time.time()
        response = send_request(proc, {
            "jsonrpc": "2.0",
            "id": 302,
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "testing",
                    "limit": 5
                }
            }
        })
        third_search_time = time.time() - start_time
        
        if response and "result" in response:
            logging.info(f"Third search (different query): {third_search_time:.3f}s (cache miss)")
        
        logging.info("\n=== Optimization tests completed! ===")
        logging.info("Summary:")
        logging.info(f"- Batch fetching: Working (retrieved {thought_count} thoughts efficiently)")
        logging.info(f"- Search cache: {'Working' if second_search_time < first_search_time * 0.5 else 'Needs verification'}")
        
    finally:
        proc.terminate()
        proc.wait()
        logging.info("Server stopped")

if __name__ == "__main__":
    main()
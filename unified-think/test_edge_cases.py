#!/usr/bin/env python3
"""
Edge case and error testing for unified-think server.
Tests various error conditions and boundary cases.
"""

import json
import subprocess
import time
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def send_request(process, request, expect_error=False):
    """Send request and read response."""
    request_str = json.dumps(request) + "\n"
    process.stdin.write(request_str)
    process.stdin.flush()
    
    # Read response with timeout
    start_time = time.time()
    while time.time() - start_time < 5:
        line = process.stdout.readline()
        if line:
            response = json.loads(line.strip())
            if expect_error and "error" in response:
                logger.info(f"✓ Expected error received: {response['error']['message']}")
            elif not expect_error and "result" in response:
                logger.info(f"✓ Success: {response.get('id', 'notification')}")
            else:
                logger.error(f"✗ Unexpected response: {json.dumps(response, indent=2)}")
            return response
    
    logger.error("✗ Timeout waiting for response")
    return None

def test_edge_cases():
    """Test various edge cases and error conditions."""
    
    # Start server
    logger.info("Starting unified-think server...")
    process = subprocess.Popen(
        ["./target/debug/unified-think"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**subprocess.os.environ, "INSTANCE_ID": "edge-test"}
    )
    
    try:
        # Initialize first
        logger.info("\n=== Initialization ===")
        send_request(process, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "edge-test", "version": "1.0"}
            }
        })
        
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "initialized", "params": {}}) + "\n")
        process.stdin.flush()
        time.sleep(0.5)
        
        # Test 1: Invalid tool name
        logger.info("\n=== Test 1: Invalid tool name ===")
        send_request(process, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "invalid_tool",
                "arguments": {}
            }
        }, expect_error=True)
        
        # Test 2: Missing required parameters for ui_think
        logger.info("\n=== Test 2: Missing required parameters ===")
        send_request(process, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Test thought"
                    # Missing: thought_number, total_thoughts, next_thought_needed
                }
            }
        }, expect_error=True)
        
        # Test 3: Invalid parameter types
        logger.info("\n=== Test 3: Invalid parameter types ===")
        send_request(process, {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Test thought",
                    "thought_number": "not a number",  # Should be int
                    "total_thoughts": 1,
                    "next_thought_needed": "yes"  # Should be bool
                }
            }
        }, expect_error=True)
        
        # Test 4: ui_recall with neither query nor chain_id
        logger.info("\n=== Test 4: ui_recall without query or chain_id ===")
        send_request(process, {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {}
            }
        }, expect_error=True)
        
        # Test 5: ui_recall with invalid action
        logger.info("\n=== Test 5: ui_recall with invalid action ===")
        send_request(process, {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "test",
                    "action": "invalid_action"
                }
            }
        }, expect_error=True)
        
        # Test 6: Very long thought content
        logger.info("\n=== Test 6: Very long thought content ===")
        long_thought = "x" * 10000  # 10KB of text
        send_request(process, {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": long_thought,
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False
                }
            }
        })
        
        # Test 7: Rapid consecutive requests
        logger.info("\n=== Test 7: Rapid consecutive requests ===")
        for i in range(5):
            send_request(process, {
                "jsonrpc": "2.0",
                "id": 8 + i,
                "method": "tools/call",
                "params": {
                    "name": "ui_think",
                    "arguments": {
                        "thought": f"Rapid test thought {i}",
                        "thought_number": i + 1,
                        "total_thoughts": 5,
                        "next_thought_needed": i < 4,
                        "chain_id": "rapid-test-chain"
                    }
                }
            })
        
        # Test 8: Malformed JSON-RPC
        logger.info("\n=== Test 8: Malformed JSON-RPC ===")
        process.stdin.write('{"invalid": "json-rpc"}\n')
        process.stdin.flush()
        time.sleep(0.5)
        
        # Test 9: Merge action without required params
        logger.info("\n=== Test 9: Merge without new_chain_name ===")
        send_request(process, {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "ui_recall",
                "arguments": {
                    "query": "test",
                    "action": "merge",
                    "action_params": {}  # Missing new_chain_name
                }
            }
        }, expect_error=True)
        
        # Test 10: Special characters in thought
        logger.info("\n=== Test 10: Special characters ===")
        send_request(process, {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {
                "name": "ui_think",
                "arguments": {
                    "thought": "Test with special chars: 🚀 \"quotes\" 'apostrophe' \n newline \t tab",
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False
                }
            }
        })
        
        logger.info("\n=== All edge case tests completed ===")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        process.terminate()
        process.wait()
        logger.info("\nServer stopped.")

if __name__ == "__main__":
    test_edge_cases()
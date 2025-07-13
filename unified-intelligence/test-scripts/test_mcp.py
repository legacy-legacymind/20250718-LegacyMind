#!/usr/bin/env python3
"""
Phase 1 Test Script for UnifiedThink MCP Server
Tests the ut_think tool with proper MCP protocol interaction
"""

import json
import subprocess
import sys
import time
from typing import Dict, Any

class MCPTester:
    def __init__(self):
        self.process = None
        self.request_id = 0
    
    def start_server(self):
        """Start the MCP server"""
        print("Starting UnifiedThink MCP Server...")
        self.process = subprocess.Popen(
            ["cargo", "run", "--quiet"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
            env={**subprocess.os.environ, "INSTANCE_ID": "phase1-test"}
        )
        time.sleep(2)  # Give server time to start
        print("Server started")
    
    def send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a JSON-RPC request and get response"""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        print(f"\n→ Sending: {method}")
        print(f"  Request: {json.dumps(request, indent=2)}")
        
        # Send request
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"← Response: {json.dumps(response, indent=2)}")
            return response
        else:
            print("← No response received")
            return None
    
    def cleanup(self):
        """Clean up the server process"""
        if self.process:
            self.process.terminate()
            self.process.wait()
            print("\nServer stopped")

def run_phase1_tests():
    """Run Phase 1 tests"""
    tester = MCPTester()
    
    try:
        # Start server
        tester.start_server()
        
        print("\n" + "="*60)
        print("PHASE 1 TESTS - UnifiedThink Foundation")
        print("="*60)
        
        # Test 1: Initialize
        print("\n[TEST 1] Initialize")
        response = tester.send_request("initialize", {
            "clientInfo": {
                "name": "phase1-test-client",
                "version": "1.0.0"
            },
            "capabilities": {}
        })
        assert response and "result" in response, "Initialize failed"
        print("✓ Initialize successful")
        
        # Test 2: List tools
        print("\n[TEST 2] List Available Tools")
        response = tester.send_request("tools/list")
        assert response and "result" in response, "List tools failed"
        tools = response["result"]["tools"]
        assert len(tools) > 0, "No tools found"
        assert any(tool["name"] == "ui_think" for tool in tools), "ui_think tool not found"
        print(f"✓ Found {len(tools)} tool(s)")
        for tool in tools:
            print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
        
        # Test 3: Single thought
        print("\n[TEST 3] Single Thought Capture")
        response = tester.send_request("tools/call", {
            "name": "ui_think",
            "arguments": {
                "thought": "Testing Phase 1 foundation - verifying basic thought capture works",
                "thought_number": 1,
                "total_thoughts": 1,
                "next_thought_needed": False
            }
        })
        assert response and "result" in response, "ui_think call failed"
        result = json.loads(response["result"]["content"][0]["text"])
        assert result["status"] == "stored", "Thought not stored"
        print(f"✓ Single thought stored with ID: {result['thought_id']}")
        
        # Test 4: Thought sequence
        print("\n[TEST 4] Thought Sequence (3 thoughts)")
        thoughts = [
            "First thought: Analyzing the problem using first principles",
            "Second thought: Breaking down components into fundamental parts",
            "Third thought: Synthesizing insights into actionable conclusion"
        ]
        
        thought_ids = []
        for i, thought in enumerate(thoughts, 1):
            response = tester.send_request("tools/call", {
                "name": "ui_think",
                "arguments": {
                    "thought": thought,
                    "thought_number": i,
                    "total_thoughts": len(thoughts),
                    "next_thought_needed": i < len(thoughts)
                }
            })
            assert response and "result" in response, f"Thought {i} failed"
            result = json.loads(response["result"]["content"][0]["text"])
            thought_ids.append(result["thought_id"])
            print(f"✓ Thought {i}/3 stored: {result['thought_id']}")
        
        # Summary
        print("\n" + "="*60)
        print("PHASE 1 TEST SUMMARY")
        print("="*60)
        print("✓ Server starts and responds correctly")
        print("✓ Initialize method works")
        print("✓ Tool listing works")
        print("✓ ui_think tool captures single thoughts")
        print("✓ ui_think tool handles thought sequences")
        print(f"✓ Generated {len(thought_ids)} thought IDs")
        print("\n🎉 Phase 1 Foundation is working correctly!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    finally:
        tester.cleanup()

if __name__ == "__main__":
    run_phase1_tests()
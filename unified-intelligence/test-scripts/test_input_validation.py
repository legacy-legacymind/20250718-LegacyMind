#!/usr/bin/env python3
"""
Test input validation implementation for unified-think MCP server
Tests all validation rules and edge cases defined in the security requirements.
"""

import json
import subprocess
import sys
import os
import time
import uuid
from typing import Dict, Any, Optional

class MCPTestClient:
    """Simple MCP test client that communicates via stdio"""
    
    def __init__(self):
        self.process = None
        self.request_id = 1
        
    def start_server(self):
        """Start the MCP server process"""
        env = os.environ.copy()
        env.update({
            'REDIS_HOST': '192.168.1.160',
            'REDIS_PORT': '6379', 
            'REDIS_PASSWORD': 'legacymind_redis_pass',
            'REDIS_DB': '0',
            'INSTANCE_ID': 'validation-test',
            'MAX_THOUGHT_LENGTH': '10000',
            'MAX_THOUGHTS_PER_CHAIN': '1000'
        })
        
        print("Starting MCP server...")
        self.process = subprocess.Popen(
            ['cargo', 'run', '--release'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd='/Users/samuelatagana/Projects/LegacyMind/unified-think-phase3/unified-think'
        )
        
        # Wait a moment for the server to start
        time.sleep(2)
        
        # Send initialization request
        init_request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "validation-test", "version": "1.0.0"}
            }
        }
        self.request_id += 1
        
        response = self.send_request(init_request)
        if not response or 'error' in response:
            raise Exception(f"Failed to initialize: {response}")
            
        print("✅ Server initialized successfully")
        return True
        
    def stop_server(self):
        """Stop the MCP server process"""
        if self.process:
            self.process.terminate()
            self.process.wait()
            
    def send_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request and get response"""
        if not self.process:
            return None
            
        request_str = json.dumps(request) + '\n'
        
        try:
            self.process.stdin.write(request_str)
            self.process.stdin.flush()
            
            response_str = self.process.stdout.readline()
            if response_str:
                return json.loads(response_str.strip())
        except Exception as e:
            print(f"Error sending request: {e}")
            
        return None
        
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool and return the response"""
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        self.request_id += 1
        
        return self.send_request(request)

def test_oversized_content():
    """Test thought content > 10,000 characters"""
    print("\n🧪 Testing oversized content validation...")
    
    client = MCPTestClient()
    try:
        client.start_server()
        
        # Test with content exactly at limit (should pass)
        valid_content = "x" * 10000
        response = client.call_tool("ui_think", {
            "thought": valid_content,
            "thought_number": 1,
            "total_thoughts": 1,
            "next_thought_needed": False
        })
        
        if response and 'error' not in response:
            print("✅ Content at 10,000 chars accepted")
        else:
            print(f"❌ Content at limit rejected: {response}")
            
        # Test with content over limit (should fail)
        oversized_content = "x" * 10001
        response = client.call_tool("ui_think", {
            "thought": oversized_content,
            "thought_number": 1,
            "total_thoughts": 1,
            "next_thought_needed": False
        })
        
        if response and 'error' in response and 'too long' in response['error']['message'].lower():
            print("✅ Oversized content rejected with proper error")
            return True
        else:
            print(f"❌ Oversized content not properly rejected: {response}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        client.stop_server()

def test_invalid_chain_id():
    """Test non-UUID chain_id values"""
    print("\n🧪 Testing invalid chain_id validation...")
    
    client = MCPTestClient()
    try:
        client.start_server()
        
        # Test valid UUID (should pass)
        valid_uuid = str(uuid.uuid4())
        response = client.call_tool("ui_think", {
            "thought": "Valid thought with valid chain_id",
            "thought_number": 1,
            "total_thoughts": 1,
            "next_thought_needed": False,
            "chain_id": valid_uuid
        })
        
        if response and 'error' not in response:
            print("✅ Valid UUID chain_id accepted")
        else:
            print(f"❌ Valid UUID rejected: {response}")
            
        # Test invalid chain_id formats
        invalid_chain_ids = [
            "not-a-uuid",
            "12345",
            "550e8400-e29b-41d4-a716-44665544000",  # Too short
            "550e8400-e29b-41d4-a716-4466554400000", # Too long
            "ggge8400-e29b-41d4-a716-446655440000",  # Invalid chars
        ]
        
        success_count = 0
        for invalid_id in invalid_chain_ids:
            response = client.call_tool("ui_think", {
                "thought": "Test thought",
                "thought_number": 1,
                "total_thoughts": 1,
                "next_thought_needed": False,
                "chain_id": invalid_id
            })
            
            if response and 'error' in response and 'invalid chain id' in response['error']['message'].lower():
                print(f"✅ Invalid chain_id '{invalid_id}' rejected")
                success_count += 1
            else:
                print(f"❌ Invalid chain_id '{invalid_id}' not rejected: {response}")
                
        return success_count == len(invalid_chain_ids)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        client.stop_server()

def test_invalid_thought_numbers():
    """Test negative, zero, or excessive thought numbers"""
    print("\n🧪 Testing invalid thought numbers...")
    
    client = MCPTestClient()
    try:
        client.start_server()
        
        # Test valid numbers (should pass)
        response = client.call_tool("ui_think", {
            "thought": "Valid thought",
            "thought_number": 1,
            "total_thoughts": 5,
            "next_thought_needed": False
        })
        
        if response and 'error' not in response:
            print("✅ Valid thought numbers accepted")
        else:
            print(f"❌ Valid numbers rejected: {response}")
            
        # Test invalid thought number scenarios
        invalid_cases = [
            {"thought_number": 0, "total_thoughts": 5, "desc": "thought_number = 0"},
            {"thought_number": -1, "total_thoughts": 5, "desc": "negative thought_number"},
            {"thought_number": 6, "total_thoughts": 5, "desc": "thought_number > total_thoughts"},
            {"thought_number": 1, "total_thoughts": 0, "desc": "total_thoughts = 0"},
            {"thought_number": 1, "total_thoughts": -1, "desc": "negative total_thoughts"},
            {"thought_number": 1, "total_thoughts": 1001, "desc": "total_thoughts > max limit"},
        ]
        
        success_count = 0
        for case in invalid_cases:
            response = client.call_tool("ui_think", {
                "thought": "Test thought",
                "thought_number": case["thought_number"],
                "total_thoughts": case["total_thoughts"],
                "next_thought_needed": False
            })
            
            if response and 'error' in response and 'invalid thought number' in response['error']['message'].lower():
                print(f"✅ {case['desc']} rejected")
                success_count += 1
            else:
                print(f"❌ {case['desc']} not rejected: {response}")
                
        return success_count == len(invalid_cases)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        client.stop_server()

def test_invalid_instance_id():
    """Test instance_id with special characters"""
    print("\n🧪 Testing invalid instance_id validation...")
    
    # Test with different instance IDs by setting environment variable
    invalid_instance_ids = [
        "",  # Empty
        "instance/with/slashes",  # Path separators
        "instance\\with\\backslashes",  # Windows path separators
        "../traversal",  # Path traversal
        "instance..path",  # Path traversal pattern
        "special@chars!",  # Special characters
        "instance with spaces",  # Spaces
        "x" * 51,  # Too long (over 50 chars)
    ]
    
    success_count = 0
    for invalid_id in invalid_instance_ids:
        client = MCPTestClient()
        try:
            # Override the instance ID in environment
            env = os.environ.copy()
            env.update({
                'REDIS_HOST': '192.168.1.160',
                'REDIS_PORT': '6379', 
                'REDIS_PASSWORD': 'legacymind_redis_pass',
                'REDIS_DB': '0',
                'INSTANCE_ID': invalid_id,  # This is what we're testing
                'MAX_THOUGHT_LENGTH': '10000',
                'MAX_THOUGHTS_PER_CHAIN': '1000'
            })
            
            # Start server with invalid instance ID
            client.process = subprocess.Popen(
                ['cargo', 'run', '--release'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd='/Users/samuelatagana/Projects/LegacyMind/unified-think-phase3/unified-think'
            )
            
            time.sleep(2)
            
            # Try to call the tool - should fail during validation
            response = client.call_tool("ui_think", {
                "thought": "Test thought",
                "thought_number": 1,
                "total_thoughts": 1,
                "next_thought_needed": False
            })
            
            if response and 'error' in response and 'invalid instance id' in response['error']['message'].lower():
                print(f"✅ Invalid instance_id '{invalid_id[:20]}...' rejected")
                success_count += 1
            else:
                print(f"❌ Invalid instance_id '{invalid_id[:20]}...' not rejected: {response}")
                
        except Exception as e:
            print(f"❌ Test with instance_id '{invalid_id[:20]}...' failed: {e}")
        finally:
            client.stop_server()
            
    return success_count == len(invalid_instance_ids)

def test_empty_thought_content():
    """Test empty and whitespace-only thought content"""
    print("\n🧪 Testing empty thought content validation...")
    
    client = MCPTestClient()
    try:
        client.start_server()
        
        empty_contents = [
            "",  # Completely empty
            "   ",  # Only spaces
            "\t\t",  # Only tabs
            "\n\n",  # Only newlines
            "  \t \n  ",  # Mixed whitespace
        ]
        
        success_count = 0
        for content in empty_contents:
            response = client.call_tool("ui_think", {
                "thought": content,
                "thought_number": 1,
                "total_thoughts": 1,
                "next_thought_needed": False
            })
            
            if response and 'error' in response and 'cannot be empty' in response['error']['message'].lower():
                print(f"✅ Empty content '{repr(content)}' rejected")
                success_count += 1
            else:
                print(f"❌ Empty content '{repr(content)}' not rejected: {response}")
                
        return success_count == len(empty_contents)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        client.stop_server()

def test_boundary_values():
    """Test edge cases at validation boundaries"""
    print("\n🧪 Testing boundary values...")
    
    client = MCPTestClient()
    try:
        client.start_server()
        
        # Test content exactly at 10,000 characters
        boundary_content = "x" * 10000
        response = client.call_tool("ui_think", {
            "thought": boundary_content,
            "thought_number": 1000,  # Max thought number
            "total_thoughts": 1000,  # Max total thoughts
            "next_thought_needed": False
        })
        
        if response and 'error' not in response:
            print("✅ Boundary values accepted")
            return True
        else:
            print(f"❌ Boundary values rejected: {response}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        client.stop_server()

def test_performance_overhead():
    """Test that validation doesn't add significant overhead"""
    print("\n🧪 Testing performance overhead...")
    
    client = MCPTestClient()
    try:
        client.start_server()
        
        # Measure time for multiple requests
        start_time = time.time()
        success_count = 0
        
        for i in range(10):
            response = client.call_tool("ui_think", {
                "thought": f"Performance test thought {i}",
                "thought_number": 1,
                "total_thoughts": 1,
                "next_thought_needed": False
            })
            
            if response and 'error' not in response:
                success_count += 1
                
        end_time = time.time()
        avg_time = (end_time - start_time) / 10 * 1000  # Convert to milliseconds
        
        if avg_time < 100:  # Should be under 100ms per request on average
            print(f"✅ Performance acceptable: {avg_time:.2f}ms average per request")
            return True
        else:
            print(f"❌ Performance too slow: {avg_time:.2f}ms average per request")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        client.stop_server()

def run_all_tests():
    """Run all validation tests"""
    print("🚀 Starting Input Validation Test Suite")
    print("=" * 50)
    
    # Build the project first
    print("Building project...")
    build_result = subprocess.run(
        ['cargo', 'build', '--release'],
        cwd='/Users/samuelatagana/Projects/LegacyMind/unified-think-phase3/unified-think',
        capture_output=True,
        text=True
    )
    
    if build_result.returncode != 0:
        print(f"❌ Build failed: {build_result.stderr}")
        return False
        
    print("✅ Build successful")
    
    tests = [
        ("Oversized Content", test_oversized_content),
        ("Invalid Chain ID", test_invalid_chain_id),
        ("Invalid Thought Numbers", test_invalid_thought_numbers),
        ("Invalid Instance ID", test_invalid_instance_id),
        ("Empty Thought Content", test_empty_thought_content),
        ("Boundary Values", test_boundary_values),
        ("Performance Overhead", test_performance_overhead),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All validation tests PASSED!")
        return True
    else:
        print("❌ Some validation tests FAILED!")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
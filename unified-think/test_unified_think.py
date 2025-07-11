#!/usr/bin/env python3
"""
Test script for unified-think MCP server.
Tests JSON-RPC communication with proper error handling and timeouts.
"""

import json
import subprocess
import sys
import time
import threading
from typing import Dict, Any, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedThinkClient:
    """Client for testing unified-think MCP server via JSON-RPC over stdio."""
    
    def __init__(self, server_path: str = "./target/debug/unified-think", timeout: float = 10.0):
        self.server_path = server_path
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0
        self.response_buffer = []
        self.reader_thread: Optional[threading.Thread] = None
        self.running = False
        
    def start(self) -> bool:
        """Start the unified-think server subprocess."""
        try:
            logger.info(f"Starting server: {self.server_path}")
            self.process = subprocess.Popen(
                [self.server_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env={**subprocess.os.environ, "INSTANCE_ID": "test-client"}
            )
            
            # Start reader thread
            self.running = True
            self.reader_thread = threading.Thread(target=self._read_responses, daemon=True)
            self.reader_thread.start()
            
            # Give server time to start
            time.sleep(0.5)
            
            if self.process.poll() is not None:
                stderr = self.process.stderr.read()
                logger.error(f"Server failed to start: {stderr}")
                return False
                
            logger.info("Server started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False
    
    def _read_responses(self):
        """Read responses from server stdout in a separate thread."""
        while self.running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                    
                line = line.strip()
                if line:
                    try:
                        response = json.loads(line)
                        self.response_buffer.append(response)
                        logger.debug(f"Received: {json.dumps(response, indent=2)}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON response: {line} - {e}")
                        
            except Exception as e:
                logger.error(f"Error reading response: {e}")
                break
    
    def send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a JSON-RPC request and wait for response."""
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("Server is not running")
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }
        
        if params is not None:
            request["params"] = params
        
        # Send request
        try:
            request_str = json.dumps(request) + "\n"
            logger.info(f"Sending: {json.dumps(request, indent=2)}")
            self.process.stdin.write(request_str)
            self.process.stdin.flush()
        except Exception as e:
            raise RuntimeError(f"Failed to send request: {e}")
        
        # Wait for response with timeout
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            # Check for matching response
            for i, response in enumerate(self.response_buffer):
                if response.get("id") == self.request_id:
                    self.response_buffer.pop(i)
                    return response
            
            time.sleep(0.1)
        
        raise TimeoutError(f"Timeout waiting for response to request {self.request_id}")
    
    def send_notification(self, method: str, params: Dict[str, Any] = None):
        """Send a JSON-RPC notification (no response expected)."""
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("Server is not running")
        
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        
        if params is not None:
            notification["params"] = params
        
        try:
            notification_str = json.dumps(notification) + "\n"
            logger.info(f"Sending notification: {json.dumps(notification, indent=2)}")
            self.process.stdin.write(notification_str)
            self.process.stdin.flush()
        except Exception as e:
            raise RuntimeError(f"Failed to send notification: {e}")
    
    def stop(self):
        """Stop the server subprocess."""
        self.running = False
        
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Server didn't terminate gracefully, killing...")
                self.process.kill()
                self.process.wait()
            
            logger.info("Server stopped")
    
    def __enter__(self):
        if not self.start():
            raise RuntimeError("Failed to start server")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def test_unified_think():
    """Run comprehensive tests on the unified-think server."""
    
    with UnifiedThinkClient() as client:
        try:
            # 1. Initialize the server
            logger.info("\n=== Step 1: Initialize ===")
            response = client.send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0"
                }
            })
            
            if "result" in response:
                logger.info(f"Initialization successful: {json.dumps(response['result'], indent=2)}")
            else:
                logger.error(f"Initialization failed: {response}")
                return
            
            # 2. Send initialized notification
            logger.info("\n=== Step 2: Send initialized notification ===")
            client.send_notification("notifications/initialized", {})
            time.sleep(0.5)  # Give server time to process
            
            # 3. List available tools
            logger.info("\n=== Step 3: List tools ===")
            response = client.send_request("tools/list", {})
            
            if "result" in response and "tools" in response["result"]:
                tools = response["result"]["tools"]
                logger.info(f"Available tools: {[tool['name'] for tool in tools]}")
            else:
                logger.error(f"Failed to list tools: {response}")
                return
            
            # 4. Store some thoughts using ui_think
            logger.info("\n=== Step 4: Store thoughts ===")
            
            # First thought
            response = client.send_request("tools/call", {
                "name": "ui_think",
                "arguments": {
                    "thought": "Testing unified-think server with Python client",
                    "thought_number": 1,
                    "total_thoughts": 3,
                    "next_thought_needed": True,
                    "chain_id": "test-chain-123"
                }
            })
            
            if "result" in response:
                logger.info(f"Thought 1 stored: {json.dumps(response['result'], indent=2)}")
            else:
                logger.error(f"Failed to store thought 1: {response}")
            
            # Second thought
            response = client.send_request("tools/call", {
                "name": "ui_think",
                "arguments": {
                    "thought": "The server handles JSON-RPC communication over stdio",
                    "thought_number": 2,
                    "total_thoughts": 3,
                    "next_thought_needed": True,
                    "chain_id": "test-chain-123"
                }
            })
            
            if "result" in response:
                logger.info(f"Thought 2 stored: {json.dumps(response['result'], indent=2)}")
            
            # Third thought
            response = client.send_request("tools/call", {
                "name": "ui_think",
                "arguments": {
                    "thought": "Redis is used for persistent storage of thoughts",
                    "thought_number": 3,
                    "total_thoughts": 3,
                    "next_thought_needed": False,
                    "chain_id": "test-chain-123"
                }
            })
            
            if "result" in response:
                logger.info(f"Thought 3 stored: {json.dumps(response['result'], indent=2)}")
            
            # 5. Search for thoughts using ui_recall
            logger.info("\n=== Step 5: Search thoughts ===")
            
            # Search by query
            response = client.send_request("tools/call", {
                "name": "ui_recall",
                "arguments": {
                    "query": "server",
                    "limit": 10
                }
            })
            
            if "result" in response:
                result = response["result"]
                if isinstance(result, list) and len(result) > 0:
                    content = result[0].get("text", {})
                    if isinstance(content, str):
                        content = json.loads(content)
                    logger.info(f"Search results: {json.dumps(content, indent=2)}")
                else:
                    logger.warning("No search results found")
            else:
                logger.error(f"Search failed: {response}")
            
            # 6. Retrieve by chain_id
            logger.info("\n=== Step 6: Retrieve chain ===")
            
            response = client.send_request("tools/call", {
                "name": "ui_recall",
                "arguments": {
                    "chain_id": "test-chain-123"
                }
            })
            
            if "result" in response:
                result = response["result"]
                if isinstance(result, list) and len(result) > 0:
                    content = result[0].get("text", {})
                    if isinstance(content, str):
                        content = json.loads(content)
                    logger.info(f"Chain thoughts: {json.dumps(content, indent=2)}")
            else:
                logger.error(f"Chain retrieval failed: {response}")
            
            # 7. Analyze thoughts
            logger.info("\n=== Step 7: Analyze thoughts ===")
            
            response = client.send_request("tools/call", {
                "name": "ui_recall",
                "arguments": {
                    "query": "server",
                    "action": "analyze"
                }
            })
            
            if "result" in response:
                result = response["result"]
                if isinstance(result, list) and len(result) > 0:
                    content = result[0].get("text", {})
                    if isinstance(content, str):
                        content = json.loads(content)
                    logger.info(f"Analysis: {json.dumps(content, indent=2)}")
            else:
                logger.error(f"Analysis failed: {response}")
            
            logger.info("\n=== All tests completed successfully! ===")
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            raise


if __name__ == "__main__":
    # Check if server binary exists
    import os
    server_paths = [
        "./target/debug/unified-think",
        "./target/release/unified-think",
        "./unified-think"
    ]
    
    server_path = None
    for path in server_paths:
        if os.path.exists(path):
            server_path = path
            break
    
    if not server_path:
        logger.error("unified-think binary not found. Please build the project first with 'cargo build'")
        sys.exit(1)
    
    # Run tests
    try:
        test_unified_think()
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)
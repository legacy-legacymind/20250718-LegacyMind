#!/usr/bin/env python3
"""
Working test script with proper JSON-RPC/MCP protocol handling.
"""

import json
import subprocess
import time
import sys
import threading
from collections import deque

class MCPClient:
    def __init__(self, server_path="./target/debug/unified-think"):
        self.server_path = server_path
        self.process = None
        self.request_id = 0
        self.responses = deque()
        self.running = False
        
    def start(self):
        """Start the server process."""
        print("Starting unified-think server...")
        self.process = subprocess.Popen(
            [self.server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,  # Unbuffered
            env={**subprocess.os.environ, "INSTANCE_ID": "working-test"}
        )
        
        self.running = True
        
        # Start reader threads
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        
        time.sleep(0.5)  # Let server start
        
    def _read_stdout(self):
        """Read stdout in background."""
        while self.running and self.process:
            try:
                line = self.process.stdout.readline()
                if line:
                    self.responses.append(line.strip())
            except:
                break
                
    def _read_stderr(self):
        """Read stderr in background."""
        while self.running and self.process:
            try:
                line = self.process.stderr.readline()
                if line:
                    print(f"[SERVER] {line.strip()}", file=sys.stderr)
            except:
                break
    
    def send_request(self, method, params=None):
        """Send a request and wait for response."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }
        if params:
            request["params"] = params
            
        print(f"\n→ Request: {method}")
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        
        # Wait for response
        start = time.time()
        while time.time() - start < 5:
            if self.responses:
                response_text = self.responses.popleft()
                try:
                    response = json.loads(response_text)
                    if response.get("id") == self.request_id:
                        print(f"← Response: {json.dumps(response, indent=2)}")
                        return response
                    else:
                        # Not our response, put it back
                        self.responses.appendleft(response_text)
                except json.JSONDecodeError:
                    print(f"Invalid JSON: {response_text}")
            time.sleep(0.1)
            
        print("← Timeout waiting for response")
        return None
        
    def send_notification(self, method, params=None):
        """Send a notification (no response expected)."""
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params:
            notification["params"] = params
            
        print(f"\n→ Notification: {method}")
        self.process.stdin.write(json.dumps(notification) + "\n")
        self.process.stdin.flush()
        
    def stop(self):
        """Stop the server."""
        self.running = False
        if self.process:
            self.process.terminate()
            self.process.wait()
            print("\nServer stopped.")


def main():
    client = MCPClient()
    
    try:
        # Start server
        client.start()
        
        # 1. Initialize
        print("\n=== Step 1: Initialize ===")
        response = client.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "working-test",
                "version": "1.0"
            }
        })
        
        if not response or "result" not in response:
            print("Failed to initialize!")
            return
            
        # 2. Send initialized notification (REQUIRED!)
        print("\n=== Step 2: Send initialized notification ===")
        client.send_notification("notifications/initialized", {})
        time.sleep(0.5)  # Give server time to process
        
        # 3. List tools
        print("\n=== Step 3: List tools ===")
        response = client.send_request("tools/list", {})
        
        if response and "result" in response:
            tools = response["result"].get("tools", [])
            print(f"Available tools: {[t['name'] for t in tools]}")
        
        # 4. Store a thought
        print("\n=== Step 4: Store a thought ===")
        response = client.send_request("tools/call", {
            "name": "ui_think",
            "arguments": {
                "thought": "This is a working test of the unified-think server!",
                "thought_number": 1,
                "total_thoughts": 2,
                "next_thought_needed": True,
                "chain_id": "working-test-chain"
            }
        })
        
        # 5. Store another thought
        print("\n=== Step 5: Store another thought ===")
        response = client.send_request("tools/call", {
            "name": "ui_think",
            "arguments": {
                "thought": "The MCP protocol requires an initialized notification after initialization.",
                "thought_number": 2,
                "total_thoughts": 2,
                "next_thought_needed": False,
                "chain_id": "working-test-chain"
            }
        })
        
        # 6. Search for thoughts
        print("\n=== Step 6: Search for thoughts ===")
        response = client.send_request("tools/call", {
            "name": "ui_recall",
            "arguments": {
                "query": "protocol"
            }
        })
        
        if response and "result" in response:
            # Parse the response content
            result = response["result"]
            if isinstance(result, list) and len(result) > 0:
                content = result[0].get("text", {})
                if isinstance(content, str):
                    content = json.loads(content)
                print(f"Search results: {json.dumps(content, indent=2)}")
        
        # 7. Retrieve chain
        print("\n=== Step 7: Retrieve chain ===")
        response = client.send_request("tools/call", {
            "name": "ui_recall",
            "arguments": {
                "chain_id": "working-test-chain"
            }
        })
        
        if response and "result" in response:
            result = response["result"]
            if isinstance(result, list) and len(result) > 0:
                content = result[0].get("text", {})
                if isinstance(content, str):
                    content = json.loads(content)
                print(f"Chain contents: {json.dumps(content, indent=2)}")
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        client.stop()


if __name__ == "__main__":
    main()
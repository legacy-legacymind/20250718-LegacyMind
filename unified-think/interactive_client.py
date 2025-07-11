#!/usr/bin/env python3
"""
Interactive client for unified-think server.
Allows manual testing and experimentation.
"""

import json
import subprocess
import threading
import sys
import time
from datetime import datetime

class InteractiveClient:
    def __init__(self):
        self.process = None
        self.request_id = 0
        self.running = False
        
    def start_server(self):
        """Start the unified-think server."""
        print("Starting unified-think server...")
        self.process = subprocess.Popen(
            ["./target/debug/unified-think"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**subprocess.os.environ, "INSTANCE_ID": "interactive"}
        )
        
        # Start response reader thread
        self.running = True
        reader_thread = threading.Thread(target=self.read_responses, daemon=True)
        reader_thread.start()
        
        time.sleep(0.5)
        print("Server started. Type 'help' for commands.\n")
        
    def read_responses(self):
        """Read and display server responses."""
        while self.running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                    
                response = json.loads(line.strip())
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Response:")
                print(json.dumps(response, indent=2))
                print()
                
            except json.JSONDecodeError:
                pass
            except Exception as e:
                print(f"Error reading response: {e}")
                break
    
    def send_request(self, method, params=None):
        """Send a JSON-RPC request."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }
        
        if params is not None:
            request["params"] = params
            
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str)
        self.process.stdin.flush()
        
    def send_notification(self, method, params=None):
        """Send a JSON-RPC notification."""
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        
        if params is not None:
            notification["params"] = params
            
        notification_str = json.dumps(notification) + "\n"
        self.process.stdin.write(notification_str)
        self.process.stdin.flush()
    
    def initialize(self):
        """Initialize the server."""
        self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "interactive-client", "version": "1.0"}
        })
        time.sleep(0.5)
        self.send_notification("notifications/initialized", {})
        
    def think(self, thought, chain_id=None):
        """Store a thought."""
        self.send_request("tools/call", {
            "name": "ui_think",
            "arguments": {
                "thought": thought,
                "thought_number": 1,
                "total_thoughts": 1,
                "next_thought_needed": False,
                "chain_id": chain_id
            }
        })
        
    def recall(self, query=None, chain_id=None, action=None):
        """Search or retrieve thoughts."""
        args = {}
        if query:
            args["query"] = query
        if chain_id:
            args["chain_id"] = chain_id
        if action:
            args["action"] = action
            
        self.send_request("tools/call", {
            "name": "ui_recall",
            "arguments": args
        })
        
    def run(self):
        """Run the interactive client."""
        self.start_server()
        self.initialize()
        
        print("\nCommands:")
        print("  init                    - Initialize server")
        print("  think <thought>         - Store a thought")
        print("  chain <id> <thought>    - Store thought in specific chain")
        print("  search <query>          - Search thoughts")
        print("  recall <chain_id>       - Get thoughts from chain")
        print("  analyze <query>         - Analyze thoughts matching query")
        print("  list                    - List available tools")
        print("  raw <json>              - Send raw JSON-RPC request")
        print("  help                    - Show this help")
        print("  quit                    - Exit")
        print()
        
        try:
            while True:
                cmd = input(">>> ").strip()
                
                if not cmd:
                    continue
                    
                parts = cmd.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                
                if command == "quit":
                    break
                elif command == "help":
                    self.run()  # Show help again
                elif command == "init":
                    self.initialize()
                elif command == "think":
                    if args:
                        self.think(args)
                    else:
                        print("Usage: think <thought>")
                elif command == "chain":
                    if ' ' in args:
                        chain_id, thought = args.split(maxsplit=1)
                        self.think(thought, chain_id)
                    else:
                        print("Usage: chain <chain_id> <thought>")
                elif command == "search":
                    if args:
                        self.recall(query=args)
                    else:
                        print("Usage: search <query>")
                elif command == "recall":
                    if args:
                        self.recall(chain_id=args)
                    else:
                        print("Usage: recall <chain_id>")
                elif command == "analyze":
                    if args:
                        self.recall(query=args, action="analyze")
                    else:
                        print("Usage: analyze <query>")
                elif command == "list":
                    self.send_request("tools/list", {})
                elif command == "raw":
                    if args:
                        try:
                            request = json.loads(args)
                            self.process.stdin.write(json.dumps(request) + "\n")
                            self.process.stdin.flush()
                        except json.JSONDecodeError as e:
                            print(f"Invalid JSON: {e}")
                    else:
                        print("Usage: raw <json>")
                else:
                    print(f"Unknown command: {command}")
                    
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            self.running = False
            if self.process:
                self.process.terminate()
                self.process.wait()
            print("Server stopped.")

if __name__ == "__main__":
    client = InteractiveClient()
    client.run()
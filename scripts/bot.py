#!/usr/bin/env python3
"""
bot.py - Advanced CLI for Ollama with memory and context management
"""

import os
import sys
import json
import redis
import requests
import argparse
from datetime import datetime
from typing import Optional, Dict, List
import readline  # For better input handling

class BotCLI:
    def __init__(self, model: str = "qwen2.5-coder:1.5b", session: str = "default"):
        self.model = model
        self.session = session
        self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        self.ollama_url = "http://localhost:11434/api/generate"
        self.redis_prefix = "Bot/cli"
        
        # Colors
        self.GREEN = '\033[92m'
        self.BLUE = '\033[94m'
        self.YELLOW = '\033[93m'
        self.RED = '\033[91m'
        self.END = '\033[0m'
        
        # Initialize readline for history
        self.history_file = os.path.expanduser("~/.bot_cli_history")
        self.load_history()
    
    def load_history(self):
        """Load command history"""
        try:
            readline.read_history_file(self.history_file)
        except FileNotFoundError:
            pass
    
    def save_history(self):
        """Save command history"""
        readline.write_history_file(self.history_file)
    
    def get_session_context(self, max_tokens: int = 2000) -> str:
        """Get recent session context"""
        key = f"{self.redis_prefix}/sessions/{self.session}"
        context = self.redis_client.get(key)
        if context and len(context) > max_tokens:
            # Truncate to recent context
            return "..." + context[-max_tokens:]
        return context or ""
    
    def save_interaction(self, prompt: str, response: str):
        """Save interaction to Redis"""
        # Append to session
        session_key = f"{self.redis_prefix}/sessions/{self.session}"
        interaction = f"\nUSER: {prompt}\nBOT: {response}\n---"
        self.redis_client.append(session_key, interaction)
        
        # Log with metadata
        log_key = f"{self.redis_prefix}/logs/{int(datetime.now().timestamp())}"
        log_data = {
            "session": self.session,
            "model": self.model,
            "prompt": prompt,
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.redis_client.set(log_key, json.dumps(log_data))
    
    def generate(self, prompt: str, include_context: bool = True) -> str:
        """Generate response from Ollama"""
        full_prompt = prompt
        
        if include_context:
            context = self.get_session_context()
            if context:
                full_prompt = f"Previous conversation:\n{context}\n\nUser: {prompt}"
        
        try:
            response = requests.post(self.ollama_url, json={
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            })
            
            if response.status_code == 200:
                return response.json()['response']
            else:
                return f"Error: Ollama returned status {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return "Error: Cannot connect to Ollama. Is it running?"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def interactive_mode(self):
        """Interactive chat mode"""
        print(f"{self.GREEN}Bot CLI - Interactive Mode{self.END}")
        print(f"{self.BLUE}Model: {self.model}{self.END}")
        print(f"{self.BLUE}Session: {self.session}{self.END}")
        print("Commands: /exit, /clear, /new (new session), /model <name>, /help")
        print()
        
        while True:
            try:
                # Prompt
                user_input = input(f"{self.YELLOW}You: {self.END}")
                
                # Handle commands
                if user_input.startswith('/'):
                    self.handle_command(user_input)
                    continue
                
                if not user_input.strip():
                    continue
                
                # Generate response
                print(f"{self.GREEN}Bot: {self.END}", end='', flush=True)
                response = self.generate(user_input)
                print(response)
                print()
                
                # Save interaction
                self.save_interaction(user_input, response)
                
            except KeyboardInterrupt:
                print("\nUse /exit to quit")
                continue
            except EOFError:
                break
        
        self.save_history()
        print("\nGoodbye!")
    
    def handle_command(self, command: str):
        """Handle special commands"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        
        if cmd in ['/exit', '/quit']:
            self.save_history()
            print("Goodbye!")
            sys.exit(0)
        
        elif cmd == '/clear':
            os.system('clear' if os.name == 'posix' else 'cls')
        
        elif cmd == '/new':
            self.session = f"session-{int(datetime.now().timestamp())}"
            print(f"{self.BLUE}New session: {self.session}{self.END}")
        
        elif cmd == '/model':
            if len(parts) > 1:
                self.model = parts[1]
                print(f"{self.BLUE}Model changed to: {self.model}{self.END}")
            else:
                print(f"Current model: {self.model}")
                print("Available models:")
                # List available models
                try:
                    resp = requests.get("http://localhost:11434/api/tags")
                    if resp.status_code == 200:
                        models = resp.json().get('models', [])
                        for m in models:
                            print(f"  - {m['name']}")
                except:
                    print("  (Could not fetch model list)")
        
        elif cmd == '/context':
            context = self.get_session_context()
            if context:
                print(f"{self.BLUE}Session context:{self.END}")
                print(context[-1000:])  # Show last 1000 chars
            else:
                print("No context in current session")
        
        elif cmd == '/sessions':
            keys = self.redis_client.keys(f"{self.redis_prefix}/sessions/*")
            sessions = [k.split('/')[-1] for k in keys]
            print(f"{self.BLUE}Active sessions:{self.END}")
            for s in sessions:
                print(f"  - {s}")
        
        elif cmd == '/clear-session':
            key = f"{self.redis_prefix}/sessions/{self.session}"
            self.redis_client.delete(key)
            print(f"{self.BLUE}Session cleared{self.END}")
        
        elif cmd == '/help':
            print("""Commands:
  /exit, /quit     - Exit the program
  /clear          - Clear screen
  /new            - Start new session
  /model [name]   - Change or show model
  /context        - Show session context
  /sessions       - List all sessions
  /clear-session  - Clear current session
  /help           - Show this help""")
        
        else:
            print(f"{self.RED}Unknown command: {cmd}{self.END}")

def main():
    parser = argparse.ArgumentParser(description='Chat with Ollama models')
    parser.add_argument('-m', '--model', default=os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:1.5b'),
                        help='Model to use')
    parser.add_argument('-s', '--session', default=os.getenv('BOT_SESSION', 'default'),
                        help='Session ID for memory')
    parser.add_argument('-p', '--prompt', help='Single prompt mode')
    parser.add_argument('-f', '--file', help='Use file as context')
    parser.add_argument('--no-context', action='store_true', help='Disable session context')
    
    args = parser.parse_args()
    
    bot = BotCLI(model=args.model, session=args.session)
    
    if args.prompt:
        # Single prompt mode
        response = bot.generate(args.prompt, include_context=not args.no_context)
        print(response)
        if not args.no_context:
            bot.save_interaction(args.prompt, response)
    
    elif args.file:
        # File mode
        if os.path.exists(args.file):
            with open(args.file, 'r') as f:
                content = f.read()
            prompt = f"File: {args.file}\n\n{content}\n\nAnalyze this file."
            response = bot.generate(prompt, include_context=False)
            print(response)
        else:
            print(f"File not found: {args.file}")
            sys.exit(1)
    
    else:
        # Interactive mode
        bot.interactive_mode()

if __name__ == "__main__":
    main()
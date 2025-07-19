#!/usr/bin/env python3
"""
Ollama Session Manager with Redis-backed Conversation History
Integrates with ollama-quick.sh for persistent conversations
"""

import redis
import requests
import json
import time
import secrets
import sys
import os
import argparse
from typing import List, Dict, Optional

class OllamaSessionManager:
    def __init__(self, redis_host='localhost', redis_port=6379, ollama_url='http://localhost:11434'):
        self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)
        self.ollama_url = ollama_url
        self.default_ttl = 3600  # 1 hour
        self.default_model = os.environ.get('OLLAMA_MODEL', 'qwen2.5-coder:1.5b')
    
    def create_session(self, name: Optional[str] = None, system_prompt: Optional[str] = None) -> str:
        """Create new chat session"""
        session_id = secrets.token_urlsafe(16)  # Shorter for CLI usage
        
        # Store session metadata
        session_data = {
            "created_at": time.time(),
            "last_activity": time.time(),
            "message_count": 0,
            "name": name or f"session-{time.strftime('%Y%m%d-%H%M%S')}"
        }
        self.redis.hset(f"session:{session_id}:meta", mapping=session_data)
        self.redis.expire(f"session:{session_id}:meta", self.default_ttl)
        
        # Add system prompt if provided
        if system_prompt:
            self._add_message(session_id, "system", system_prompt)
        
        return session_id
    
    def _add_message(self, session_id: str, role: str, content: str) -> None:
        """Add message to session"""
        timestamp = time.time()
        
        # Store message
        message_data = json.dumps({
            "role": role,
            "content": content,
            "timestamp": timestamp
        })
        
        # Add to sorted set
        self.redis.zadd(f"session:{session_id}:messages", {message_data: timestamp})
        
        # Update session metadata
        self.redis.hincrby(f"session:{session_id}:meta", "message_count", 1)
        self.redis.hset(f"session:{session_id}:meta", "last_activity", timestamp)
        
        # Refresh TTL
        self.redis.expire(f"session:{session_id}:messages", self.default_ttl)
        self.redis.expire(f"session:{session_id}:meta", self.default_ttl)
    
    def get_conversation_history(self, session_id: str, limit: int = -1) -> List[Dict[str, str]]:
        """Retrieve conversation history"""
        messages_raw = self.redis.zrange(f"session:{session_id}:messages", 0, limit-1 if limit > 0 else -1)
        
        messages = []
        for msg_json in messages_raw:
            msg_data = json.loads(msg_json)
            messages.append({
                "role": msg_data["role"],
                "content": msg_data["content"]
            })
        
        return messages
    
    def chat(self, session_id: str, user_message: str, model: Optional[str] = None) -> str:
        """Send message to Ollama and store response"""
        # Add user message
        self._add_message(session_id, "user", user_message)
        
        # Get conversation history (limit to recent messages for context window)
        messages = self.get_conversation_history(session_id, limit=20)
        
        # Call Ollama API
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": model or self.default_model,
                    "messages": messages,
                    "stream": False
                },
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            assistant_message = result['message']['content']
            self._add_message(session_id, "assistant", assistant_message)
            return assistant_message
            
        except Exception as e:
            error_msg = f"Error calling Ollama: {str(e)}"
            print(f"ERROR: {error_msg}", file=sys.stderr)
            return error_msg
    
    def list_sessions(self) -> List[Dict]:
        """List all active sessions"""
        sessions = []
        for key in self.redis.scan_iter("session:*:meta"):
            session_id = key.split(":")[1]
            meta = self.redis.hgetall(key)
            sessions.append({
                "id": session_id,
                "name": meta.get("name", "unnamed"),
                "created": float(meta.get("created_at", 0)),
                "last_activity": float(meta.get("last_activity", 0)),
                "messages": int(meta.get("message_count", 0))
            })
        
        # Sort by last activity
        sessions.sort(key=lambda x: x["last_activity"], reverse=True)
        return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session and all associated data"""
        deleted = 0
        deleted += self.redis.delete(f"session:{session_id}:messages")
        deleted += self.redis.delete(f"session:{session_id}:meta")
        return deleted > 0
    
    def clear_old_sessions(self, age_hours: int = 24) -> int:
        """Clear sessions older than specified hours"""
        cutoff = time.time() - (age_hours * 3600)
        deleted_count = 0
        
        for session in self.list_sessions():
            if session["last_activity"] < cutoff:
                if self.delete_session(session["id"]):
                    deleted_count += 1
        
        return deleted_count

def main():
    parser = argparse.ArgumentParser(description='Ollama Session Manager')
    parser.add_argument('prompt', nargs='?', help='Chat prompt')
    parser.add_argument('-s', '--session', help='Session ID to use')
    parser.add_argument('-n', '--new', action='store_true', help='Create new session')
    parser.add_argument('--name', help='Name for new session')
    parser.add_argument('--system', help='System prompt for new session')
    parser.add_argument('-l', '--list', action='store_true', help='List sessions')
    parser.add_argument('-d', '--delete', help='Delete session')
    parser.add_argument('--history', help='Show session history')
    parser.add_argument('--clean', type=int, help='Clean sessions older than N hours')
    parser.add_argument('-m', '--model', help='Model to use')
    
    args = parser.parse_args()
    
    manager = OllamaSessionManager()
    
    # Handle various commands
    if args.list:
        sessions = manager.list_sessions()
        if not sessions:
            print("No active sessions")
        else:
            print(f"{'ID':<24} {'Name':<20} {'Messages':<10} {'Last Activity'}")
            print("-" * 70)
            for s in sessions:
                last_activity = time.strftime('%Y-%m-%d %H:%M', time.localtime(s['last_activity']))
                print(f"{s['id']:<24} {s['name']:<20} {s['messages']:<10} {last_activity}")
        return
    
    if args.delete:
        if manager.delete_session(args.delete):
            print(f"Deleted session: {args.delete}")
        else:
            print(f"Session not found: {args.delete}")
        return
    
    if args.history:
        history = manager.get_conversation_history(args.history)
        if not history:
            print(f"No history found for session: {args.history}")
        else:
            for msg in history:
                print(f"\n[{msg['role'].upper()}]")
                print(msg['content'])
        return
    
    if args.clean:
        deleted = manager.clear_old_sessions(args.clean)
        print(f"Deleted {deleted} old sessions")
        return
    
    # Handle chat
    if args.prompt:
        # Determine session
        if args.new or not args.session:
            session_id = manager.create_session(name=args.name, system_prompt=args.system)
            print(f"Created session: {session_id}", file=sys.stderr)
        else:
            session_id = args.session
        
        # Send message and get response
        response = manager.chat(session_id, args.prompt, model=args.model)
        print(response)
        
        # Print session ID for reference
        print(f"\nSession ID: {session_id}", file=sys.stderr)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
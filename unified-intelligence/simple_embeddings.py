#!/usr/bin/env python3
"""
Simple embedding service for unified-intelligence
Stores embeddings in Redis without using RedisVL for now.
"""

import sys
import json
import os
import redis
import numpy as np
import re
from openai import OpenAI


class SimpleEmbeddingService:
    def __init__(self, redis_url: str, openai_api_key: str, instance: str):
        """Initialize the simple embedding service"""
        self.redis_client = redis.from_url(redis_url)
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.instance = instance
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and normalize text before embedding generation"""
        if not text:
            return ""
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        # Remove excessive punctuation
        text = re.sub(r'[.]{2,}', '.', text)
        text = re.sub(r'[!]{2,}', '!', text)
        text = re.sub(r'[?]{2,}', '?', text)
        
        return text
    
    def generate_embedding(self, text: str) -> list:
        """Generate embedding using OpenAI"""
        try:
            # Preprocess text before sending to API
            processed_text = self._preprocess_text(text)
            
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=processed_text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}", file=sys.stderr)
            return None
    
    def store_thought_embedding(self, thought_id: str, content: str, timestamp: int) -> bool:
        """Store thought with embedding in Redis using simple JSON"""
        try:
            embedding = self.generate_embedding(content)
            if embedding is None:
                return False
            
            # Store embedding as JSON string
            embedding_data = {
                "thought_id": thought_id,
                "content": content,
                "embedding": embedding,
                "timestamp": timestamp,
                "instance": self.instance,
                "provider": "openai",
                "model": "text-embedding-3-small"
            }
            
            # Store in Redis
            key = f"{self.instance}:embeddings:{thought_id}"
            self.redis_client.set(key, json.dumps(embedding_data))
            
            # Also store in a sorted set for quick retrieval
            set_key = f"{self.instance}:embedding_index"
            self.redis_client.zadd(set_key, {thought_id: timestamp})
            
            return True
            
        except Exception as e:
            print(f"Error storing thought embedding: {e}", file=sys.stderr)
            return False
    
    def semantic_search(self, query: str, limit: int = 10, threshold: float = 0.5) -> list:
        """Perform semantic search using cosine similarity"""
        try:
            query_embedding = self.generate_embedding(query)
            if query_embedding is None:
                return []
            
            # Get all stored embeddings
            pattern = f"{self.instance}:embeddings:*"
            print(f"DEBUG: Searching for keys with pattern: {pattern}", file=sys.stderr)
            keys = self.redis_client.keys(pattern)
            print(f"DEBUG: Found {len(keys)} keys matching pattern", file=sys.stderr)
            
            similarities = []
            for key in keys:
                data_str = self.redis_client.get(key)
                if data_str:
                    data = json.loads(data_str)
                    stored_embedding = data["embedding"]
                    
                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(query_embedding, stored_embedding)
                    
                    if similarity >= threshold:
                        similarities.append({
                            "thought_id": data["thought_id"],
                            "content": data["content"],
                            "timestamp": data["timestamp"],
                            "similarity": similarity
                        })
            
            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            print(f"DEBUG: Found {len(similarities)} results above threshold {threshold}", file=sys.stderr)
            return similarities[:limit]
            
        except Exception as e:
            print(f"Error in semantic search: {e}", file=sys.stderr)
            return []
    
    def _cosine_similarity(self, a: list, b: list) -> float:
        """Calculate cosine similarity between two vectors
        OpenAI embeddings are pre-normalized, so we can use simple dot product"""
        try:
            a = np.array(a)
            b = np.array(b)
            # OpenAI embeddings are pre-normalized, so dot product is sufficient
            return np.dot(a, b)
        except Exception:
            return 0.0


def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: python3 simple_embeddings.py <command> [args...]", file=sys.stderr)
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Get configuration from environment
    redis_password = os.getenv('REDIS_PASSWORD', '')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    instance = os.getenv('INSTANCE_ID', 'Claude')
    print(f"DEBUG: Using instance ID: {instance}", file=sys.stderr)
    
    # Try to connect to Redis first to check for API key
    temp_redis = redis.from_url(redis_url)
    
    # First try to get API key from environment
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    # If not in environment, try Redis
    if not openai_api_key:
        try:
            openai_api_key = temp_redis.get('config:openai_api_key')
            if openai_api_key:
                openai_api_key = openai_api_key.decode('utf-8') if isinstance(openai_api_key, bytes) else openai_api_key
                print(f"Retrieved OPENAI_API_KEY from Redis ({len(openai_api_key)} chars)", file=sys.stderr)
        except Exception as e:
            print(f"Error retrieving API key from Redis: {e}", file=sys.stderr)
    
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not found in environment or Redis", file=sys.stderr)
        sys.exit(1)
    
    service = SimpleEmbeddingService(redis_url, openai_api_key, instance)
    
    if command == "store":
        if len(sys.argv) != 5:
            print("Usage: store <thought_id> <content> <timestamp>", file=sys.stderr)
            sys.exit(1)
        
        thought_id = sys.argv[2]
        content = sys.argv[3]
        timestamp = int(sys.argv[4])
        
        success = service.store_thought_embedding(thought_id, content, timestamp)
        print(json.dumps({"success": success}))
    
    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: search <query> [limit] [threshold]", file=sys.stderr)
            sys.exit(1)
        
        query = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
        
        print(f"DEBUG: Search parameters - query: '{query}', limit: {limit}, threshold: {threshold}", file=sys.stderr)
        
        results = service.semantic_search(query, limit, threshold)
        print(json.dumps({"results": results}))
    
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
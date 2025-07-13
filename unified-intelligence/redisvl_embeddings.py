#!/usr/bin/env python3
"""
RedisVL-based embedding service for unified-intelligence
This script can be called from Rust to handle embeddings without PyO3 linking issues.
"""

import sys
import json
import os
import redis
from redisvl.index import SearchIndex
from redisvl.schema import IndexSchema
from openai import OpenAI


class UnifiedIntelligenceVectorService:
    def __init__(self, redis_url: str, openai_api_key: str, instance: str):
        """Initialize the vector service with RedisVL"""
        self.redis_client = redis.from_url(redis_url)
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.instance = instance
        
        # Configure vector index
        self.index_name = f"{instance}_thoughts_index"
        self.schema = {
            "index": {
                "name": self.index_name,
                "prefix": f"{instance}/vectors/",
                "storage_type": "hash"
            },
            "fields": [
                {
                    "name": "thought_id",
                    "type": "text"
                },
                {
                    "name": "content", 
                    "type": "text"
                },
                {
                    "name": "embedding",
                    "type": "vector",
                    "attrs": {
                        "dims": 1536,
                        "distance_metric": "cosine",
                        "algorithm": "hnsw",
                        "m": 16,
                        "ef_construction": 200
                    }
                },
                {
                    "name": "timestamp",
                    "type": "numeric"
                }
            ]
        }
        
        # Initialize index
        schema = IndexSchema.from_dict(self.schema)
        self.index = SearchIndex(schema, redis_client=self.redis_client)
        try:
            self.index.create()
        except Exception as e:
            # Index might already exist
            print(f"Index creation info: {e}", file=sys.stderr)
    
    def generate_embedding(self, text: str) -> list:
        """Generate embedding using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}", file=sys.stderr)
            return None
    
    def store_thought_embedding(self, thought_id: str, content: str, timestamp: int) -> bool:
        """Store thought with embedding in Redis"""
        try:
            embedding = self.generate_embedding(content)
            if embedding is None:
                return False
            
            # Store in RedisVL format
            doc = {
                "thought_id": thought_id,
                "content": content,
                "embedding": embedding,
                "timestamp": timestamp
            }
            
            key = f"{self.instance}/vectors/{thought_id}"
            self.index.load([doc], id_field="thought_id", keys=[key])
            return True
            
        except Exception as e:
            print(f"Error storing thought embedding: {e}", file=sys.stderr)
            return False
    
    def semantic_search(self, query: str, limit: int = 10, threshold: float = 0.7) -> list:
        """Perform semantic search"""
        try:
            query_embedding = self.generate_embedding(query)
            if query_embedding is None:
                return []
            
            # Search using RedisVL
            results = self.index.query(
                query=query_embedding,
                top_k=limit,
                return_fields=["thought_id", "content", "timestamp"],
                filter_expression=None
            )
            
            # Filter by threshold and format results
            filtered_results = []
            for result in results:
                if result.score >= threshold:
                    filtered_results.append({
                        "thought_id": result.thought_id,
                        "content": result.content,
                        "timestamp": result.timestamp,
                        "similarity": result.score
                    })
            
            return filtered_results
            
        except Exception as e:
            print(f"Error in semantic search: {e}", file=sys.stderr)
            return []


def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: python3 redisvl_embeddings.py <command> [args...]", file=sys.stderr)
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Get configuration from environment
    redis_url = f"redis://:{os.getenv('REDIS_PASSWORD', '')}@localhost:6379/0"
    openai_api_key = os.getenv('OPENAI_API_KEY')
    instance = os.getenv('INSTANCE_ID', 'Claude')
    
    if not openai_api_key:
        print("Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    service = UnifiedIntelligenceVectorService(redis_url, openai_api_key, instance)
    
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
        threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.7
        
        results = service.semantic_search(query, limit, threshold)
        print(json.dumps({"results": results}))
    
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
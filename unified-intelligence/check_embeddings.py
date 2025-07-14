#!/usr/bin/env python3
"""
Check embedding storage status
"""

import asyncio
import os
import redis.asyncio as redis

async def check_embeddings():
    """Check the current embedding situation"""
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Count embeddings
        embedding_keys = await client.keys("Claude:embeddings:*")
        print(f"Total embeddings: {len(embedding_keys)}")
        
        # Count thoughts
        thought_keys = await client.keys("Claude:Thoughts:*")
        print(f"Total thoughts: {len(thought_keys)}")
        
        # Check recent embeddings
        if embedding_keys:
            print("\nRecent embeddings:")
            for key in embedding_keys[-5:]:  # Last 5
                thought_id = key.split(':')[-1]
                print(f"  {thought_id}")
        
        # Check if semantic search service is working
        try:
            from simple_embeddings import SimpleEmbeddingService
            api_key = await client.get('config:openai_api_key')
            if api_key:
                sync_redis_url = f"redis://:{redis_password}@localhost:6379/0"
                service = SimpleEmbeddingService(sync_redis_url, api_key, "Claude")
                
                print("\nTesting semantic search...")
                results = service.semantic_search("Redis", limit=3, threshold=0.5)
                print(f"Search results: {len(results)}")
                for result in results[:3]:
                    print(f"  {result['thought_id']}: {result['similarity']:.3f}")
            
        except Exception as e:
            print(f"Semantic search test failed: {e}")
        
        await client.close()
        
    except Exception as e:
        print(f"Check failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_embeddings())
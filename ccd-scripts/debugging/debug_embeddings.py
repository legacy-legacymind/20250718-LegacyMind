#!/usr/bin/env python3
"""
Debug embedding issues - check if thoughts exist and why they don't have embeddings
"""
import redis
import asyncio
import json
import redis.asyncio as async_redis

async def debug_embeddings():
    redis_url = "redis://:legacymind_redis_pass@localhost:6379/0"
    r = await async_redis.from_url(redis_url, decode_responses=True)
    
    instances = ['CC', 'CCI', 'CCD']
    
    print("=== Detailed Embedding Debug ===")
    
    for instance in instances:
        print(f"\n--- {instance} Instance ---")
        
        # Get all thought keys
        thought_keys = await r.keys(f"{instance}:thought:*")
        print(f"Total thoughts: {len(thought_keys)}")
        
        if len(thought_keys) > 0:
            # Check first few thoughts
            for i, key in enumerate(thought_keys[:3]):
                print(f"\nThought {i+1}: {key}")
                thought_data = await r.hgetall(key)
                
                print(f"  Fields: {list(thought_data.keys())}")
                print(f"  Has embedding: {'embedding' in thought_data}")
                print(f"  Content length: {len(thought_data.get('content', ''))}")
                print(f"  Created: {thought_data.get('created_at', 'unknown')}")
                
                if 'embedding' in thought_data:
                    embedding = thought_data['embedding']
                    if embedding:
                        print(f"  Embedding length: {len(embedding)}")
                    else:
                        print(f"  Embedding is empty")
        
        # Check pending events in stream
        stream_key = f"{instance}:events"
        try:
            # Get last 5 events
            events = await r.xrevrange(stream_key, count=5)
            print(f"\nLast 5 events in {stream_key}:")
            for event_id, fields in events:
                print(f"  {event_id}: {fields.get('type', 'unknown')} - {fields.get('thought_id', 'no_id')}")
        except Exception as e:
            print(f"Error reading events: {e}")
    
    await r.aclose()

if __name__ == "__main__":
    asyncio.run(debug_embeddings())
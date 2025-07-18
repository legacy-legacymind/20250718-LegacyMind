#!/usr/bin/env python3
"""
Check which instances have active streams and embedding services
"""
import redis
import asyncio
import redis.asyncio as async_redis

async def check_instances():
    redis_url = "redis://:legacymind_redis_pass@localhost:6379/0"
    r = await async_redis.from_url(redis_url, decode_responses=True)
    
    instances = ['CC', 'CCI', 'CCD', 'Claude']
    
    print("=== Instance Stream Status ===")
    for instance in instances:
        stream_key = f"{instance}:events"
        try:
            length = await r.xlen(stream_key)
            print(f"{instance}: {length} events in stream")
        except Exception as e:
            print(f"{instance}: Stream error - {e}")
    
    print("\n=== Consumer Groups ===")
    for instance in instances:
        stream_key = f"{instance}:events"
        try:
            groups = await r.xinfo_groups(stream_key)
            for group in groups:
                print(f"{instance}: Group '{group['name']}' - {group['consumers']} consumers, {group['pending']} pending")
        except Exception as e:
            print(f"{instance}: No consumer groups or error - {e}")
    
    print("\n=== Recent Thoughts with Embeddings ===")
    for instance in instances:
        try:
            # Check if there are thoughts with embeddings
            keys = await r.keys(f"{instance}:thought:*")
            embedded_count = 0
            for key in keys[:5]:  # Check first 5 thoughts
                embedding = await r.hget(key, 'embedding')
                if embedding:
                    embedded_count += 1
            print(f"{instance}: {embedded_count}/{min(len(keys), 5)} recent thoughts have embeddings ({len(keys)} total thoughts)")
        except Exception as e:
            print(f"{instance}: Error checking thoughts - {e}")
    
    await r.aclose()

if __name__ == "__main__":
    asyncio.run(check_instances())
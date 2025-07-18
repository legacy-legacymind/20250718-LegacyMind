#!/usr/bin/env python3
"""
Complete Redis key structure analysis
"""
import redis
import asyncio
import redis.asyncio as async_redis
from collections import defaultdict

async def full_scan():
    redis_url = "redis://:legacymind_redis_pass@localhost:6379/0"
    r = await async_redis.from_url(redis_url, decode_responses=True)
    
    print("=== Complete Redis Key Analysis ===")
    
    # Get all keys and categorize them
    all_keys = await r.keys("*")
    print(f"Total keys in Redis: {len(all_keys)}")
    
    # Categorize by instance and type
    by_instance = defaultdict(lambda: defaultdict(list))
    
    for key in all_keys:
        parts = key.split(':')
        if len(parts) >= 2:
            instance = parts[0]
            key_type = parts[1]
            by_instance[instance][key_type].append(key)
    
    # Show breakdown by instance
    instances = ['CC', 'CCI', 'CCD', 'Claude', 'DT']
    for instance in instances:
        if instance in by_instance:
            print(f"\n--- {instance} Instance ---")
            for key_type, keys in by_instance[instance].items():
                print(f"  {key_type}: {len(keys)} keys")
                if key_type in ['thought', 'thought_meta'] and keys:
                    print(f"    Sample: {keys[0]}")
                    # Check content of first key
                    if key_type == 'thought':
                        data = await r.hgetall(keys[0])
                        print(f"    Fields: {list(data.keys())}")
                        if 'embedding' in data:
                            print(f"    Has embedding: {bool(data['embedding'])}")
    
    # Specific check for recent thoughts
    print(f"\n=== Recent CCD Thoughts Analysis ===")
    recent_events = await r.xrevrange("CCD:events", count=5)
    for event_id, fields in recent_events:
        thought_id = fields.get('thought_id')
        if thought_id and thought_id != 'no_id':
            print(f"\nEvent {event_id}:")
            print(f"  Thought ID: {thought_id}")
            
            # Check both key types
            thought_key = f"CCD:thought:{thought_id}"
            meta_key = f"CCD:thought_meta:{thought_id}"
            
            thought_exists = await r.exists(thought_key)
            meta_exists = await r.exists(meta_key)
            
            print(f"  thought key exists: {bool(thought_exists)}")
            print(f"  thought_meta key exists: {bool(meta_exists)}")
            
            if thought_exists:
                data = await r.hgetall(thought_key)
                print(f"  thought fields: {list(data.keys())}")
                print(f"  has embedding: {'embedding' in data}")
            
            if meta_exists:
                data = await r.hgetall(meta_key)
                print(f"  meta fields: {list(data.keys())}")
    
    await r.aclose()

if __name__ == "__main__":
    asyncio.run(full_scan())
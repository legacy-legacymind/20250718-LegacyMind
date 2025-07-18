#!/usr/bin/env python3
"""
Check if thoughts are actually being stored in Redis
"""
import redis
import asyncio
import redis.asyncio as async_redis

async def check_thought_storage():
    redis_url = "redis://:legacymind_redis_pass@localhost:6379/0"
    r = await async_redis.from_url(redis_url, decode_responses=True)
    
    instances = ['CC', 'CCI', 'CCD']
    
    print("=== Thought Storage Investigation ===")
    
    for instance in instances:
        print(f"\n--- {instance} Instance ---")
        
        # Check all keys for this instance
        all_keys = await r.keys(f"{instance}:*")
        print(f"Total keys for {instance}: {len(all_keys)}")
        
        # Filter thought keys
        thought_keys = [k for k in all_keys if ':thought:' in k]
        print(f"Thought keys: {len(thought_keys)}")
        
        if thought_keys:
            print("Sample thought keys:")
            for key in thought_keys[:3]:
                print(f"  {key}")
        
        # Check recent events
        stream_key = f"{instance}:events"
        try:
            events = await r.xrevrange(stream_key, count=3)
            print(f"Recent events:")
            for event_id, fields in events:
                thought_id = fields.get('thought_id', 'no_id')
                event_type = fields.get('type', 'unknown')
                print(f"  {event_id}: {event_type} - {thought_id}")
                
                # Check if this thought exists
                if thought_id and thought_id != 'no_id':
                    thought_key = f"{instance}:thought:{thought_id}"
                    exists = await r.exists(thought_key)
                    print(f"    Thought exists: {bool(exists)}")
                    if exists:
                        fields = await r.hgetall(thought_key)
                        print(f"    Fields: {list(fields.keys())}")
        except Exception as e:
            print(f"Error reading events: {e}")
    
    await r.aclose()

if __name__ == "__main__":
    asyncio.run(check_thought_storage())
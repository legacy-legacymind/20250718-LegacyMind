#!/usr/bin/env python3
"""
Verify thought storage - more comprehensive check
"""
import redis
import asyncio
import redis.asyncio as async_redis

async def verify_thoughts():
    redis_url = "redis://:legacymind_redis_pass@localhost:6379/0"
    r = await async_redis.from_url(redis_url, decode_responses=True)
    
    print("=== Comprehensive Thought Verification ===")
    
    # Check all possible thought key patterns
    patterns = [
        "*:thought:*",
        "CCD:thought:*", 
        "CCS:thought:*",
        "thought:*",
        "*thought*"
    ]
    
    for pattern in patterns:
        keys = await r.keys(pattern)
        print(f"Pattern '{pattern}': {len(keys)} keys")
        if keys:
            print(f"  Sample keys: {keys[:3]}")
    
    # Check recent CCD thoughts specifically
    print("\n=== Recent CCD Thoughts ===")
    recent_events = await r.xrevrange("CCD:events", count=10)
    for event_id, fields in recent_events:
        thought_id = fields.get('thought_id')
        if thought_id and thought_id != 'no_id':
            # Try different key formats
            possible_keys = [
                f"CCD:thought:{thought_id}",
                f"thought:{thought_id}",
                f"CCS:thought:{thought_id}",
                thought_id
            ]
            
            for key in possible_keys:
                exists = await r.exists(key)
                if exists:
                    print(f"  FOUND: {key}")
                    data = await r.hgetall(key)
                    print(f"    Fields: {list(data.keys())}")
                    break
            else:
                print(f"  NOT FOUND: {thought_id} (tried {len(possible_keys)} formats)")
    
    await r.aclose()

if __name__ == "__main__":
    asyncio.run(verify_thoughts())
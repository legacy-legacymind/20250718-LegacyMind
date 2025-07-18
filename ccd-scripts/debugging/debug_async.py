#!/usr/bin/env python3
"""
Debug the async issue in federation embedding service
"""
import asyncio
import redis.asyncio as redis

async def test_redis_keys():
    """Test the specific redis.keys() operation that's failing"""
    redis_url = "redis://:legacymind_redis_pass@localhost:6379/0"
    r = redis.from_url(redis_url, decode_responses=True)
    
    try:
        print("Testing redis.keys() operation...")
        
        # This is the exact line that's failing
        stream_pattern = "*:events"
        stream_keys = await r.keys(stream_pattern)
        
        print(f"Success! Found {len(stream_keys)} stream keys:")
        for key in stream_keys:
            print(f"  {key}")
        
        # Test the processing that follows
        new_instances = set()
        for stream_key in stream_keys:
            instance = stream_key.split(':')[0]
            if instance and instance not in ['temp', 'test']:
                new_instances.add(instance)
        
        print(f"Extracted instances: {sorted(new_instances)}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await r.aclose()

if __name__ == "__main__":
    asyncio.run(test_redis_keys())
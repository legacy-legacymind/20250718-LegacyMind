#!/usr/bin/env python3
"""
Debug the specific async issue in the background service
"""

import asyncio
import os
import redis.asyncio as redis

async def debug_redis_async():
    """Debug each Redis operation that's failing"""
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        print("Testing individual Redis operations...")
        
        # Test 1: Basic xreadgroup (stream consumer issue)
        print("1. Testing xreadgroup...")
        try:
            events = await client.xreadgroup(
                "embedding_processors",
                "test_debug",
                {"Claude:events": ">"},
                count=1,
                block=100
            )
            print(f"✅ xreadgroup success: {type(events)}, {len(events)} results")
            
            # Test iteration that might be causing issues
            for stream_name, messages in events:
                print(f"   Stream: {stream_name}, Messages: {len(messages)}")
                for message_id, fields in messages:
                    print(f"   Event: {message_id}")
                    break  # Just test the iteration
                    
        except Exception as e:
            print(f"❌ xreadgroup failed: {e}")
        
        # Test 2: Keys operation (metrics/retry processor issue)
        print("2. Testing keys...")
        try:
            keys = await client.keys("embedding_queue:*")
            print(f"✅ keys success: {type(keys)}, {len(keys)} results")
            
            # Test iteration
            for key in keys:
                print(f"   Key: {key}")
                break  # Just test the iteration
                
        except Exception as e:
            print(f"❌ keys failed: {e}")
        
        # Test 3: hget operation (status checking)
        print("3. Testing hget...")
        try:
            # Create a test hash first
            await client.hset("test_debug_hash", "test_field", "test_value")
            status = await client.hget("test_debug_hash", "test_field")
            print(f"✅ hget success: {type(status)}, value: {status}")
            await client.delete("test_debug_hash")
        except Exception as e:
            print(f"❌ hget failed: {e}")
        
        # Test 4: set operation (metrics publishing)
        print("4. Testing set...")
        try:
            result = await client.set("test_debug_key", "test_value", ex=10)
            print(f"✅ set success: {type(result)}, result: {result}")
            await client.delete("test_debug_key")
        except Exception as e:
            print(f"❌ set failed: {e}")
        
        await client.aclose()
        print("✅ All Redis operations completed")
        
    except Exception as e:
        print(f"❌ Redis debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_redis_async())
#!/usr/bin/env python3
"""
Test Redis async with proper version 6.2.0 usage
"""

import asyncio
import os

async def test_redis_async_v6():
    """Test Redis async with version 6.2.0"""
    print("Testing Redis 6.2.0 async usage...")
    
    try:
        import redis.asyncio as redis
        print(f"✅ Imported redis.asyncio")
        
        redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        redis_url = f"redis://:{redis_password}@localhost:6379/0"
        
        # Test connection
        client = redis.from_url(redis_url, decode_responses=True)
        result = await client.ping()
        print(f"✅ Ping result: {result}")
        
        # Test keys - this was failing
        print("Testing keys operation...")
        keys_result = await client.keys("Claude:*")
        print(f"✅ Keys operation returned: {type(keys_result)} with {len(keys_result)} items")
        
        # Test xreadgroup - this was also failing
        print("Testing xreadgroup...")
        try:
            stream_result = await client.xreadgroup(
                "test_group_v6",
                "test_consumer_v6",
                {"Claude:events": ">"},
                count=1,
                block=100
            )
            print(f"✅ xreadgroup returned: {type(stream_result)} with {len(stream_result)} items")
        except Exception as e:
            print(f"⚠️  xreadgroup error (expected): {e}")
        
        # Test close
        await client.close()
        print("✅ Client closed successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Redis async test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_redis_async_v6())
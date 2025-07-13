#!/usr/bin/env python3
"""
Test Redis async operations to debug the await issues
"""

import asyncio
import os
import redis.asyncio as redis

async def test_redis_operations():
    """Test basic Redis async operations"""
    print("Testing Redis async operations...")
    
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        
        # Test basic operations
        print("1. Testing ping...")
        await client.ping()
        print("✅ Ping successful")
        
        # Test keys operation
        print("2. Testing keys...")
        keys = await client.keys("Claude:*")
        print(f"✅ Keys operation successful: found {len(keys)} keys")
        
        # Test xlen
        print("3. Testing xlen...")
        length = await client.xlen("Claude:events")
        print(f"✅ Stream length: {length}")
        
        # Test xreadgroup
        print("4. Testing xreadgroup...")
        try:
            events = await client.xreadgroup(
                "test_group",
                "test_consumer", 
                {"Claude:events": ">"},
                count=1,
                block=100
            )
            print(f"✅ xreadgroup successful: {len(events)} streams")
        except Exception as e:
            print(f"⚠️  xreadgroup error (expected): {e}")
        
        await client.aclose()
        print("✅ All Redis async operations working")
        return True
        
    except Exception as e:
        print(f"❌ Redis async test failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_redis_operations())
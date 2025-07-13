#!/usr/bin/env python3
"""
Minimal test to isolate Redis async issues
"""

import asyncio
import os
import redis.asyncio as redis

async def test_problematic_operations():
    """Test the specific Redis operations that are failing"""
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        print("Testing hset with individual fields...")
        await client.hset("test_key", "field1", "value1")
        await client.hset("test_key", "field2", "value2")
        print("✅ Individual hset calls work")
        
        print("Testing hget...")
        value = await client.hget("test_key", "field1")
        print(f"✅ hget works: {value}")
        
        print("Testing xreadgroup...")
        try:
            # Create test consumer group first
            await client.xgroup_create("Claude:events", "test_group2", id="0", mkstream=True)
            print("✅ Consumer group created")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                print("✅ Consumer group already exists")
            else:
                raise
        
        # Test actual xreadgroup
        events = await client.xreadgroup(
            "test_group2",
            "test_consumer",
            {"Claude:events": ">"},
            count=1,
            block=100
        )
        print(f"✅ xreadgroup works: {len(events)} results")
        
        # Clean up
        await client.delete("test_key")
        await client.xgroup_destroy("Claude:events", "test_group2")
        await client.aclose()
        
        print("✅ All problematic operations work in isolation")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        await client.aclose()
        return False

if __name__ == "__main__":
    asyncio.run(test_problematic_operations())
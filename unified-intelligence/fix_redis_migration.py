#!/usr/bin/env python3
"""
Fix Redis data corruption from migration
Clear problematic keys and let system rebuild
"""
import asyncio
import redis.asyncio as redis
import os

async def fix_redis_migration():
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        print("🔧 Fixing Redis migration issues...")
        
        # Clear problematic feedback loop keys
        patterns_to_clear = [
            "Claude:relevance:*",
            "Claude:tags:*", 
            "Claude:co_occurrence:*",
            "Claude:feedback:*",
            "Claude:search_cache:*"
        ]
        
        for pattern in patterns_to_clear:
            keys = await client.keys(pattern)
            if keys:
                print(f"Clearing {len(keys)} keys matching {pattern}")
                await client.delete(*keys)
        
        # Clear consumer groups that might be corrupted
        try:
            await client.xgroup_destroy("Claude:events", "feedback_processors")
            print("Cleared feedback_processors consumer group")
        except:
            pass
            
        try:
            await client.xgroup_destroy("Claude:events", "embedders")
            print("Cleared embedders consumer group")
        except:
            pass
        
        print("✅ Redis migration fix complete")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(fix_redis_migration())
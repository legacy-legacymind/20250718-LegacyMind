#!/usr/bin/env python3
"""
Nuclear option: Clear ALL Claude Redis keys and force clean rebuild
"""
import asyncio
import redis.asyncio as redis
import os

async def nuclear_redis_fix():
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        print("💥 NUCLEAR Redis fix - clearing ALL Claude keys...")
        
        # Get all Claude keys
        all_claude_keys = await client.keys("Claude:*")
        print(f"Found {len(all_claude_keys)} Claude keys to clear")
        
        if all_claude_keys:
            await client.delete(*all_claude_keys)
            print(f"✅ Cleared {len(all_claude_keys)} keys")
        
        # Also clear CCI and CCD keys
        for instance in ["CCI", "CCD", "CC"]:
            instance_keys = await client.keys(f"{instance}:*")
            if instance_keys:
                await client.delete(*instance_keys)
                print(f"✅ Cleared {len(instance_keys)} {instance} keys")
        
        print("💥 Nuclear Redis fix complete - system will rebuild cleanly")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(nuclear_redis_fix())
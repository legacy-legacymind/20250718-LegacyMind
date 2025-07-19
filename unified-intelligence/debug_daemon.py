#!/usr/bin/env python3
"""
Debug the background daemon to see why it's not working
"""
import asyncio
import os
import redis.asyncio as redis

async def debug_daemon():
    """Debug what's happening with the daemon"""
    print("🔍 Debugging background embedding daemon...")
    
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Check API key
        api_key = await client.get('config:openai_api_key')
        print(f"API Key: {'✅ Found' if api_key else '❌ Missing'}")
        
        # Check consumer group
        try:
            groups = await client.xinfo_groups("Claude:events")
            print(f"Consumer groups: {len(groups)}")
            for group in groups:
                print(f"  - {group['name']}: {group['consumers']} consumers, {group['pending']} pending")
        except Exception as e:
            print(f"Consumer group error: {e}")
        
        # Check recent events
        try:
            events = await client.xrevrange("Claude:events", count=3)
            print(f"Recent events: {len(events)}")
            for message_id, fields in events:
                print(f"  {message_id}: {list(fields.keys())}")
        except Exception as e:
            print(f"Events error: {e}")
        
        # Try reading with consumer group
        try:
            print("Testing consumer group read...")
            events = await client.xreadgroup(
                "embedding_daemon",
                "test_consumer", 
                {"Claude:events": ">"},
                count=1,
                block=1000
            )
            print(f"Consumer read result: {len(events) if events else 0} streams")
        except Exception as e:
            print(f"Consumer read error: {e}")
            
        # Check embedding counts
        thought_count = len(await client.keys("Claude:Thoughts:*"))
        embedding_count = len(await client.keys("Claude:embeddings:*"))
        print(f"Thoughts: {thought_count}, Embeddings: {embedding_count}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(debug_daemon())
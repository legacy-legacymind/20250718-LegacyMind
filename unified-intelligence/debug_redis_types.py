#!/usr/bin/env python3
"""
Debug script to check Redis data types for thoughts
"""
import asyncio
import redis.asyncio as redis
import os

async def check_redis_types():
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Get some thought IDs from recent events
        events = await client.xread({"Claude:events": "0-0"}, count=5)
        
        for stream_name, messages in events:
            for message_id, fields in messages:
                thought_id = fields.get('thought_id')
                if thought_id:
                    thought_key = f"Claude:Thoughts:{thought_id}"
                    
                    # Check key type
                    key_type = await client.type(thought_key)
                    exists = await client.exists(thought_key)
                    
                    print(f"Key: {thought_key}")
                    print(f"  Exists: {exists}")
                    print(f"  Type: {key_type}")
                    
                    if exists:
                        if key_type == 'string':
                            data = await client.get(thought_key)
                            print(f"  String data: {data[:100]}...")
                        elif key_type == 'hash':
                            data = await client.hgetall(thought_key)
                            print(f"  Hash data: {list(data.keys())}")
                        else:
                            print(f"  Unknown type: {key_type}")
                    print()
                    
                    # Only check first 3
                    if len([x for x in events[0][1] if x[1].get('thought_id')]) >= 3:
                        break
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(check_redis_types())
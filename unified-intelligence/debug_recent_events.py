#!/usr/bin/env python3
"""
Debug recent events causing WRONGTYPE errors
"""
import asyncio
import redis.asyncio as redis
import os
import json

async def debug_recent_events():
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Get the recent events that are failing
        events = await client.xrevrange("Claude:events", count=5)
        
        for message_id, fields in events:
            print(f"Event ID: {message_id}")
            print(f"Fields: {fields}")
            
            # Extract thought_id using both formats
            event_type = fields.get('event_type')
            thought_id = fields.get('thought_id')
            
            if not event_type and 'data' in fields:
                try:
                    data = json.loads(fields['data'])
                    event_type = data.get('type')
                    thought_id = data.get('thought_id')
                    print(f"  Parsed from JSON: event_type={event_type}, thought_id={thought_id}")
                except Exception as e:
                    print(f"  JSON parse error: {e}")
            
            if thought_id:
                thought_key = f"Claude:Thoughts:{thought_id}"
                
                try:
                    key_type = await client.type(thought_key)
                    exists = await client.exists(thought_key)
                    print(f"  Thought key: {thought_key}")
                    print(f"  Exists: {exists}, Type: {key_type}")
                    
                    if exists:
                        if key_type == 'string':
                            data = await client.get(thought_key)
                            print(f"  SUCCESS: String data length {len(data)}")
                        elif key_type == 'hash':
                            data = await client.hgetall(thought_key)
                            print(f"  HASH data: {list(data.keys())}")
                        else:
                            print(f"  OTHER TYPE: {key_type}")
                    else:
                        print(f"  Key {thought_key} does not exist")
                        
                except Exception as e:
                    print(f"  ERROR: {e}")
                    print(f"  Error type: {type(e)}")
            else:
                print("  No thought_id found")
            print()
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(debug_recent_events())
#!/usr/bin/env python3
"""
Debug specific WRONGTYPE error
"""
import asyncio
import redis.asyncio as redis
import os
import json

async def debug_specific_event():
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Check the specific event that was failing
        event_id = "1752430192766-0"
        
        # Get the event data
        events = await client.xread({"Claude:events": event_id}, count=1)
        
        if events:
            for stream_name, messages in events:
                for message_id, fields in messages:
                    print(f"Event ID: {message_id}")
                    print(f"Fields: {fields}")
                    
                    thought_id = fields.get('thought_id')
                    if thought_id:
                        thought_key = f"Claude:Thoughts:{thought_id}"
                        
                        # Check what happens when we try to access this
                        try:
                            key_type = await client.type(thought_key)
                            exists = await client.exists(thought_key)
                            print(f"Thought key: {thought_key}")
                            print(f"Exists: {exists}, Type: {key_type}")
                            
                            if exists:
                                if key_type == 'string':
                                    data = await client.get(thought_key)
                                    print(f"SUCCESS: Got data length {len(data)}")
                                elif key_type == 'hash':
                                    data = await client.hgetall(thought_key) 
                                    print(f"HASH: {list(data.keys())}")
                                else:
                                    print(f"OTHER TYPE: {key_type}")
                            else:
                                print("Key does not exist")
                                
                        except Exception as e:
                            print(f"ERROR accessing thought: {e}")
                            print(f"Error type: {type(e)}")
        else:
            print("No events found")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(debug_specific_event())
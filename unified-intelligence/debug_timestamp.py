#!/usr/bin/env python3
"""
Debug timestamp issue
"""
import asyncio
import os
import json
import redis.asyncio as redis

async def debug_timestamp():
    """Check timestamp format in recent thoughts"""
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Get a recent thought
        thought_keys = await client.keys("Claude:Thoughts:*")
        
        for thought_key in thought_keys[:3]:
            print(f"Checking: {thought_key}")
            
            key_type = await client.type(thought_key)
            print(f"Type: {key_type}")
            
            if key_type == "ReJSON-RL":
                thought_data = await client.execute_command("JSON.GET", thought_key)
                thought_data = json.loads(thought_data)
            else:
                thought_data_str = await client.get(thought_key)
                thought_data = json.loads(thought_data_str)
            
            timestamp = thought_data.get('timestamp')
            print(f"Timestamp: {timestamp} (type: {type(timestamp)})")
            
            # Try to convert to float
            try:
                if isinstance(timestamp, str):
                    print(f"String timestamp: '{timestamp}'")
                    # Try parsing ISO format
                    from datetime import datetime
                    if 'T' in timestamp:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        float_ts = dt.timestamp()
                        print(f"Converted to float: {float_ts}")
                    else:
                        float_ts = float(timestamp)
                        print(f"Direct float conversion: {float_ts}")
                elif isinstance(timestamp, (int, float)):
                    float_ts = float(timestamp)
                    print(f"Already numeric: {float_ts}")
                else:
                    print(f"Unknown timestamp format: {timestamp}")
            except Exception as e:
                print(f"Error converting timestamp: {e}")
            
            print()
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(debug_timestamp())
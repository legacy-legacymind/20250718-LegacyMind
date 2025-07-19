#!/usr/bin/env python3
"""Check what's stored in Redis for Claude thoughts."""

import redis
import json

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

# Check Claude thoughts
pattern = "Claude:Thoughts:*"
keys = r.keys(pattern)
print(f"Found {len(keys)} Claude thought keys matching pattern: {pattern}")

if keys:
    # Show first few keys
    for key in keys[:3]:
        print(f"\nKey: {key}")
        key_type = r.type(key)
        print(f"Type: {key_type}")
        
        if key_type == 'string':
            value = r.get(key)
            try:
                parsed = json.loads(value)
                print("Value (parsed):", json.dumps(parsed, indent=2)[:500])
            except:
                print("Value (raw):", value[:500])
        elif key_type == 'ReJSON-RL':
            # Try JSON.GET
            try:
                value = r.execute_command('JSON.GET', key)
                print("JSON Value:", value[:500])
            except Exception as e:
                print(f"Error getting JSON: {e}")
        else:
            print(f"Unexpected type: {key_type}")

# Check search index info
try:
    info = r.execute_command('FT.INFO', 'idx:thoughts')
    print("\n\nSearch Index Info:")
    for i in range(0, len(info), 2):
        if i+1 < len(info):
            print(f"{info[i]}: {info[i+1]}")
except Exception as e:
    print(f"\nNo search index found: {e}")
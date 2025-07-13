#!/usr/bin/env python3
"""Check Redis event streams"""

import redis
import json
import os
from datetime import datetime

def main():
    # Connect to Redis
    r = redis.Redis(
        host=os.environ.get('REDIS_HOST', 'localhost'),
        port=int(os.environ.get('REDIS_PORT', 6379)),
        password=os.environ.get('REDIS_PASSWORD', 'legacymind_redis_pass'),
        db=int(os.environ.get('REDIS_DB', 0)),
        decode_responses=True
    )
    
    # Test connection
    try:
        r.ping()
        print("✓ Connected to Redis")
    except:
        print("✗ Failed to connect to Redis")
        return
    
    # List all event streams
    print("\n=== Event Streams ===")
    streams = r.keys("stream:*:events")
    print(f"Found {len(streams)} event stream(s)")
    
    for stream in streams:
        print(f"\nStream: {stream}")
        
        # Get stream info
        try:
            info = r.xinfo_stream(stream)
            print(f"  Length: {info.get('length', 0)}")
            print(f"  First entry: {info.get('first-entry', 'None')}")
            print(f"  Last entry: {info.get('last-entry', 'None')}")
        except:
            print("  (Unable to get stream info)")
        
        # Read last 10 events
        print("\n  Recent Events:")
        try:
            events = r.xrevrange(stream, count=10)
            for event_id, data in events:
                print(f"\n  Event ID: {event_id}")
                print(f"  Timestamp: {data.get('timestamp', 'N/A')}")
                print(f"  Event Type: {data.get('event_type', 'N/A')}")
                print(f"  Instance: {data.get('instance', 'N/A')}")
                
                # Print additional fields
                for key, value in data.items():
                    if key not in ['timestamp', 'event_type', 'instance']:
                        print(f"  {key}: {value}")
        except Exception as e:
            print(f"  Error reading events: {e}")
    
    # Check for thoughts
    print("\n\n=== Stored Thoughts ===")
    thought_keys = r.keys("thought:*")
    print(f"Found {len(thought_keys)} thought(s)")
    
    for i, key in enumerate(thought_keys[:5]):  # Show first 5
        try:
            thought_json = r.json().get(key, "$")
            if thought_json and thought_json[0]:
                thought = thought_json[0]
                print(f"\n{i+1}. {key}")
                print(f"   ID: {thought.get('id', 'N/A')}")
                print(f"   Instance: {thought.get('instance', 'N/A')}")
                print(f"   Preview: {thought.get('thought', '')[:100]}...")
                print(f"   Chain ID: {thought.get('chain_id', 'None')}")
        except Exception as e:
            print(f"   Error reading thought: {e}")

if __name__ == "__main__":
    main()
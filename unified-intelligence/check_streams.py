#!/usr/bin/env python3
"""
Check Redis Streams for thought_created events
"""

import redis
import sys

def check_streams():
    try:
        # Connect to Redis
        r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)
        
        # Check if the events stream exists and has data
        stream_key = "Claude:events"
        stream_length = r.xlen(stream_key)
        print(f"Stream '{stream_key}' length: {stream_length}")
        
        if stream_length > 0:
            # Get latest events
            events = r.xrevrange(stream_key, count=5)
            print(f"\nLatest {min(5, len(events))} events:")
            for event_id, fields in events:
                print(f"  Event ID: {event_id}")
                print(f"  All fields: {fields}")
                print()
        else:
            print("No events found in stream")
            
    except Exception as e:
        print(f"Error checking streams: {e}")
        return False
    
    return True

if __name__ == "__main__":
    check_streams()
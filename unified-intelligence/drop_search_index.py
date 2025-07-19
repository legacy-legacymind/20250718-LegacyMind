#!/usr/bin/env python3
"""Drop the search index to allow recreation with correct prefix."""

import redis

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

try:
    # Drop the existing index
    result = r.execute_command('FT.DROPINDEX', 'idx:thoughts')
    print(f"Index dropped successfully: {result}")
except redis.ResponseError as e:
    if "Unknown index" in str(e):
        print("Index doesn't exist, nothing to drop")
    else:
        print(f"Error dropping index: {e}")
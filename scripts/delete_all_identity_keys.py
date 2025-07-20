#!/usr/bin/env python3
"""
Delete all identity keys from Redis.
"""

import redis

# Redis connection
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
REDIS_PASSWORD = 'legacymind_redis_pass'

def connect_redis():
    """Connect to Docker Redis instance"""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True
    )

def delete_identity_keys(r: redis.Redis):
    """Delete all identity-related keys"""
    patterns = [
        "*:identity",
        "*:identity:*",
        "identity:*",
        "*identity*"
    ]
    
    total_deleted = 0
    
    for pattern in patterns:
        print(f"Scanning for pattern: {pattern}")
        for key in r.scan_iter(match=pattern):
            r.delete(key)
            print(f"  Deleted: {key}")
            total_deleted += 1
    
    return total_deleted

def main():
    """Main deletion process"""
    print("Deleting all identity keys from Redis")
    print("=" * 50)
    
    try:
        r = connect_redis()
        r.ping()
        print("✓ Connected to Redis\n")
    except Exception as e:
        print(f"✗ Failed to connect to Redis: {e}")
        return
    
    deleted = delete_identity_keys(r)
    
    print(f"\n{'-' * 50}")
    print(f"Total keys deleted: {deleted}")
    print("All identity keys have been removed.")

if __name__ == "__main__":
    main()
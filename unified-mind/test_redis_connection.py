#!/usr/bin/env python3
"""Test Redis connection with auth"""

import redis
import sys

try:
    # Connect to Redis with auth
    r = redis.Redis(
        host='127.0.0.1',
        port=6379,
        password='legacymind_redis_pass',
        decode_responses=True
    )
    
    # Test connection
    r.ping()
    print("✅ Redis connection successful!")
    
    # Try to get some keys
    keys = r.keys('pattern:*')
    print(f"Found {len(keys)} pattern keys")
    
    keys = r.keys('voice_pattern:*')
    print(f"Found {len(keys)} voice pattern keys")
    
    # Test set/get
    r.set('test:unified_mind', 'connected')
    value = r.get('test:unified_mind')
    print(f"Test set/get: {value}")
    r.delete('test:unified_mind')
    
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    sys.exit(1)
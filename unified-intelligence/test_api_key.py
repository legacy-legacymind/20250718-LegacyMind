#!/usr/bin/env python3
"""Test script to verify API key storage and retrieval from Redis"""

import redis
import os
import sys

def main():
    # Connect to Redis
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = os.getenv('REDIS_PORT', '6379')
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    
    print(f"Connecting to Redis at {redis_host}:{redis_port}")
    
    try:
        r = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True
        )
        
        # Test connection
        r.ping()
        print("✓ Connected to Redis")
        
        # Check if API key exists
        api_key = r.get("config:openai_api_key")
        
        if api_key:
            print(f"✓ Found OPENAI_API_KEY in Redis: {api_key[:10]}... ({len(api_key)} chars)")
        else:
            print("✗ No OPENAI_API_KEY found in Redis")
            
            # Check environment
            env_key = os.getenv("OPENAI_API_KEY")
            if env_key:
                print(f"  Environment has OPENAI_API_KEY: {env_key[:10]}... ({len(env_key)} chars)")
            else:
                print("  No OPENAI_API_KEY in environment either")
                
    except redis.ConnectionError as e:
        print(f"✗ Failed to connect to Redis: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
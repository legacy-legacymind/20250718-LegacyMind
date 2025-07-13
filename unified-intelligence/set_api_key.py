#!/usr/bin/env python3
"""Utility to set the OPENAI_API_KEY in Redis"""

import redis
import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description='Set OPENAI_API_KEY in Redis')
    parser.add_argument('api_key', nargs='?', help='The API key to store (or read from stdin)')
    parser.add_argument('--redis-host', default='localhost', help='Redis host')
    parser.add_argument('--redis-port', default=6379, type=int, help='Redis port')
    parser.add_argument('--redis-password', default=os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass'), help='Redis password')
    
    args = parser.parse_args()
    
    # Get API key from argument or stdin
    if args.api_key:
        api_key = args.api_key
    else:
        print("Enter OPENAI_API_KEY (or pipe from stdin):")
        api_key = sys.stdin.read().strip()
    
    if not api_key:
        print("Error: No API key provided", file=sys.stderr)
        sys.exit(1)
    
    # Connect to Redis
    try:
        r = redis.Redis(
            host=args.redis_host,
            port=args.redis_port,
            password=args.redis_password,
            decode_responses=True
        )
        
        # Test connection
        r.ping()
        print(f"✓ Connected to Redis at {args.redis_host}:{args.redis_port}")
        
        # Store API key with 24-hour expiration
        r.setex("config:openai_api_key", 86400, api_key)
        print(f"✓ Stored OPENAI_API_KEY in Redis ({len(api_key)} chars)")
        
        # Verify
        stored_key = r.get("config:openai_api_key")
        if stored_key == api_key:
            print("✓ Verified: API key stored successfully")
        else:
            print("✗ Warning: Stored key doesn't match", file=sys.stderr)
            
    except redis.ConnectionError as e:
        print(f"✗ Failed to connect to Redis: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
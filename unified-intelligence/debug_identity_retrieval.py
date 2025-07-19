#!/usr/bin/env python3
"""
Debug script to investigate the identity retrieval issue
"""
import redis
import json
import sys

def main():
    # Connect to Redis with authentication
    import os
    redis_password = os.getenv('REDIS_PASSWORD', '')
    
    if redis_password:
        r = redis.Redis(host='localhost', port=6379, password=redis_password, decode_responses=True)
    else:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    # Check if we can scan for CCI identity documents
    pattern = "CCI:identity:*:*"
    print(f"Scanning for pattern: {pattern}")
    
    keys = []
    cursor = 0
    while True:
        cursor, partial_keys = r.scan(cursor, match=pattern, count=1000)
        keys.extend(partial_keys)
        if cursor == 0:
            break
    
    print(f"Found {len(keys)} identity document keys")
    
    if not keys:
        print("No keys found! This explains why view returns stale data.")
        return
    
    # Try to read a few documents
    sample_keys = keys[:3]
    print(f"\nSampling first 3 keys:")
    
    for key in sample_keys:
        print(f"\nKey: {key}")
        try:
            # Try JSON.GET
            doc_data = r.execute_command('JSON.GET', key)
            if doc_data:
                doc = json.loads(doc_data)
                print(f"  Created: {doc.get('created_at', 'unknown')}")
                print(f"  Updated: {doc.get('updated_at', 'unknown')}")
                print(f"  Version: {doc.get('version', 'unknown')}")
                print(f"  Field type: {doc.get('field_type', 'unknown')}")
            else:
                print("  No data returned")
        except Exception as e:
            print(f"  Error reading: {e}")
    
    # Check if there's a monolithic identity
    monolithic_key = "CCI:identity"
    print(f"\nChecking for monolithic identity at: {monolithic_key}")
    try:
        monolithic_data = r.execute_command('JSON.GET', monolithic_key)
        if monolithic_data:
            print("  Monolithic identity exists!")
            monolithic = json.loads(monolithic_data)
            print(f"  Updated: {monolithic.get('_metadata', {}).get('updated_at', 'unknown')}")
        else:
            print("  No monolithic identity found")
    except Exception as e:
        print(f"  Error checking monolithic: {e}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
import redis
import json
import os
from datetime import datetime

def check_identity_structure():
    # Get Redis password from environment
    redis_password = os.environ.get('REDIS_PASSWORD', '')
    
    # Connect to Redis with authentication
    r = redis.Redis(
        host='localhost', 
        port=6379, 
        password=redis_password,
        decode_responses=True
    )
    
    try:
        # Test connection
        r.ping()
        print("✓ Connected to Redis successfully")
    except Exception as e:
        print(f"✗ Failed to connect to Redis: {e}")
        print("Make sure REDIS_PASSWORD environment variable is set")
        return
    
    # Look for identity keys
    identity_keys = []
    for key in r.scan_iter(match="*:identity"):
        identity_keys.append(key)
    
    print(f"\nFound {len(identity_keys)} identity keys:")
    for key in identity_keys:
        print(f"  - {key}")
    
    # Check each identity structure
    for key in identity_keys:
        print(f"\n{'='*60}")
        print(f"Identity Key: {key}")
        print('='*60)
        
        try:
            # Get the identity data
            identity_data = r.hgetall(key)
            
            if not identity_data:
                print("  No data found")
                continue
            
            # Check technical_profile specifically
            if 'technical_profile' in identity_data:
                print("\nTechnical Profile:")
                try:
                    tp_data = json.loads(identity_data['technical_profile'])
                    print(f"  Type: {type(tp_data).__name__}")
                    
                    # Check for required fields
                    required_fields = [
                        'preferred_languages',
                        'frameworks',
                        'tools',
                        'expertise_areas',
                        'learning_interests'
                    ]
                    
                    for field in required_fields:
                        if field in tp_data:
                            print(f"  ✓ {field}: {type(tp_data[field]).__name__} with {len(tp_data[field]) if isinstance(tp_data[field], list) else 'N/A'} items")
                        else:
                            print(f"  ✗ {field}: MISSING")
                    
                    # Show actual structure
                    print("\n  Actual structure:")
                    print(json.dumps(tp_data, indent=4))
                    
                except json.JSONDecodeError as e:
                    print(f"  Error parsing technical_profile JSON: {e}")
                    print(f"  Raw value: {identity_data['technical_profile'][:200]}...")
            else:
                print("  ✗ technical_profile field is missing entirely")
            
            # Show all fields present
            print(f"\nAll fields in {key}:")
            for field in identity_data.keys():
                print(f"  - {field}")
            
        except Exception as e:
            print(f"  Error reading identity: {e}")
    
    # Try to get a specific instance identity if none found
    if not identity_keys:
        print("\nNo identity keys found. Checking for common instance IDs...")
        for instance in ['CCI', 'CC', 'DT', 'CCB']:
            key = f"{instance}:identity"
            if r.exists(key):
                print(f"\nFound {key}!")
                identity_data = r.hgetall(key)
                print(f"Fields: {list(identity_data.keys())}")

if __name__ == "__main__":
    check_identity_structure()
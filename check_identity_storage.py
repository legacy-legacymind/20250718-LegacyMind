#!/usr/bin/env python3
import redis
import json

# Connect to Redis with password
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

# Check all possible identity storage patterns
print("Checking all identity storage patterns...\n")

# Pattern 1: Monolithic identity (instance:identity)
monolithic_patterns = ["CC:identity", "CCI:identity", "CCB:identity", "CCS:identity", "DT:identity"]
for pattern in monolithic_patterns:
    if r.exists(pattern):
        print(f"Found monolithic identity: {pattern}")
        try:
            # Get the JSON value
            data = r.execute_command('JSON.GET', pattern, '$')
            parsed = json.loads(data)
            print(f"  Type: {type(parsed)}")
            
            # Check if it's an array when it shouldn't be
            if isinstance(parsed, list):
                print(f"  WARNING: Stored as array with {len(parsed)} elements")
                if len(parsed) > 0:
                    first = parsed[0]
                    print(f"  First element type: {type(first)}")
                    if isinstance(first, dict):
                        print(f"  First element keys: {list(first.keys())[:5]}...")
                        
                        # Check for string fields that might be arrays
                        for key, value in first.items():
                            if isinstance(value, list) and key in ['name', 'instance_id', 'instance_type']:
                                print(f"  ERROR: Field '{key}' is array but should be string: {value}")
            else:
                print(f"  Stored correctly as: {type(parsed)}")
                
        except Exception as e:
            print(f"  Error reading: {e}")
    else:
        print(f"No monolithic identity found at: {pattern}")

# Pattern 2: Legacy monolithic identity (legacy:instance:identity)
print("\n\nChecking legacy patterns...")
legacy_patterns = ["legacy:CC:identity", "legacy:CCI:identity", "legacy:CCB:identity", "legacy:CCS:identity"]
for pattern in legacy_patterns:
    if r.exists(pattern):
        print(f"Found legacy identity: {pattern}")
        try:
            data = r.execute_command('JSON.GET', pattern, '$')
            parsed = json.loads(data)
            print(f"  Type: {type(parsed)}")
            if isinstance(parsed, list):
                print(f"  WARNING: Stored as array")
        except Exception as e:
            print(f"  Error reading: {e}")

# Check for any other identity-related keys that might be causing issues
print("\n\nScanning for other identity keys...")
for key in r.scan_iter(match="*identity*", count=100):
    key_type = r.type(key)
    if key_type == 'ReJSON-RL' and not any(key.startswith(p + ":") for p in ['CC', 'CCI', 'CCB', 'CCS', 'DT']):
        print(f"\nUnusual identity key: {key} (type: {key_type})")
        try:
            data = r.execute_command('JSON.GET', key, '$')
            parsed = json.loads(data)
            if isinstance(parsed, list):
                print(f"  Stored as array!")
        except:
            pass
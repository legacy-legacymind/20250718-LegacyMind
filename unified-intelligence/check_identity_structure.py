#!/usr/bin/env python3
import redis
import json
from datetime import datetime

def check_identity_structure():
    # Connect to Redis
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    # Look for identity keys
    identity_keys = []
    for key in r.scan_iter(match="*:identity"):
        identity_keys.append(key)
    
    print(f"Found {len(identity_keys)} identity keys:")
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
            
            # Parse and display structure
            for field, value in identity_data.items():
                print(f"\nField: {field}")
                try:
                    # Try to parse as JSON for nested structures
                    parsed = json.loads(value)
                    print(f"  Type: {type(parsed).__name__}")
                    if isinstance(parsed, dict):
                        print("  Structure:")
                        for k, v in parsed.items():
                            print(f"    - {k}: {type(v).__name__}")
                            if isinstance(v, dict):
                                for k2, v2 in v.items():
                                    print(f"        - {k2}: {type(v2).__name__}")
                    else:
                        print(f"  Value: {parsed}")
                except json.JSONDecodeError:
                    print(f"  Value (string): {value[:100]}...")
        except Exception as e:
            print(f"  Error reading identity: {e}")
    
    # Check for expected technical_profile structure
    print(f"\n{'='*60}")
    print("Checking for technical_profile.expertise_areas field")
    print('='*60)
    
    for key in identity_keys:
        technical_profile = r.hget(key, 'technical_profile')
        if technical_profile:
            try:
                tp_data = json.loads(technical_profile)
                if 'expertise_areas' in tp_data:
                    print(f"{key}: Has expertise_areas ✓")
                else:
                    print(f"{key}: MISSING expertise_areas ✗")
                    print(f"  Available fields: {list(tp_data.keys())}")
            except:
                print(f"{key}: Error parsing technical_profile")

if __name__ == "__main__":
    check_identity_structure()
#!/usr/bin/env python3
import redis
import json

# Connect to Redis with password
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

print("Testing document retrieval for CC instance...\n")

# Get all identity documents for CC
instance_id = "CC"
pattern = f"{instance_id}:identity:*"
keys = []
for key in r.scan_iter(match=pattern, count=100):
    if r.type(key) == 'ReJSON-RL':
        keys.append(key)

print(f"Found {len(keys)} identity documents for {instance_id}\n")

# Group by field type
by_field_type = {}
for key in sorted(keys):
    parts = key.split(':')
    if len(parts) >= 4:
        field_type = parts[2]
        if field_type not in by_field_type:
            by_field_type[field_type] = []
        by_field_type[field_type].append(key)

print("Documents by field type:")
for field_type, doc_keys in by_field_type.items():
    print(f"  {field_type}: {len(doc_keys)} document(s)")

# Check if any document has a content field that's an array
print("\nChecking for array content fields...")
for key in keys:
    try:
        data = r.execute_command('JSON.GET', key, '.')
        parsed = json.loads(data)
        
        if isinstance(parsed, dict) and 'content' in parsed:
            content = parsed['content']
            # Check if content is a string (which would cause issues when trying to deserialize as object)
            if isinstance(content, str):
                print(f"\nERROR: Content is string in {key}")
                print(f"  Content: {content[:100]}...")
            elif isinstance(content, list):
                print(f"\nERROR: Content is array in {key}")
                print(f"  Content: {content}")
                
    except Exception as e:
        print(f"Error checking {key}: {e}")

# Test direct JSON.GET with $ path like Rust does
print("\n\nTesting JSON.GET with $ path (like Rust)...")
test_key = "CC:identity:core_info:4456c1bb-191c-4618-a1e0-8413768ed9cb"
if r.exists(test_key):
    try:
        # This is how Rust fetches it
        result = r.execute_command('JSON.GET', test_key, '.')
        print(f"JSON.GET {test_key} with '.' path:")
        print(f"  Type: {type(result)}")
        parsed = json.loads(result)
        print(f"  Parsed type: {type(parsed)}")
        if isinstance(parsed, dict):
            print(f"  Keys: {list(parsed.keys())}")
            if 'content' in parsed:
                print(f"  Content type: {type(parsed['content'])}")
    except Exception as e:
        print(f"  Error: {e}")
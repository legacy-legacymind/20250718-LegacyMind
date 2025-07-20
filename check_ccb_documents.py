#!/usr/bin/env python3
import redis
import json

# Connect to Redis with password
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

print("Checking CCB identity documents for issues...\n")

# Check all identity documents for CCB
instance_id = "CCB"
docs_found = []

for key in r.scan_iter(match=f"{instance_id}:identity:*", count=100):
    if r.type(key) == 'ReJSON-RL':
        docs_found.append(key)

print(f"Found {len(docs_found)} identity documents for {instance_id}\n")

# Check each document
for doc_key in sorted(docs_found):
    parts = doc_key.split(':')
    if len(parts) >= 4:
        field_type = parts[2]
        
        # Special check for relationships
        if field_type.startswith('relationships:'):
            print(f"\nChecking relationship document: {doc_key}")
            try:
                data = r.execute_command('JSON.GET', doc_key, '.')
                doc = json.loads(data)
                
                if 'content' in doc:
                    content = doc['content']
                    print(f"  Content type: {type(content)}")
                    print(f"  Content: {json.dumps(content, indent=2)[:200]}...")
                    
                    # Check if it's a proper RelationshipDynamics structure
                    expected_fields = ['trust_level', 'interaction_style', 'boundaries', 'shared_history', 'current_standing']
                    has_expected = any(field in content for field in expected_fields)
                    
                    if not has_expected:
                        print(f"  WARNING: Not a valid RelationshipDynamics structure!")
                        print(f"  This document should be deleted")
                        
            except Exception as e:
                print(f"  Error: {e}")

# Also check if CCB has a monolithic identity
monolithic_key = f"{instance_id}:identity"
if r.exists(monolithic_key):
    print(f"\n\nFound monolithic identity: {monolithic_key}")
    try:
        data = r.execute_command('JSON.GET', monolithic_key, '$')
        print(f"  Raw type: {type(data)}")
        parsed = json.loads(data)
        if isinstance(parsed, list):
            print(f"  WARNING: Stored as array!")
    except Exception as e:
        print(f"  Error: {e}")
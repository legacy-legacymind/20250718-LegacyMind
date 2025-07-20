#!/usr/bin/env python3
import redis
import json

# Connect to Redis with password
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

print("Checking for metadata field conflicts...\n")

# Check CC's metadata document
metadata_key = "CC:identity:metadata:289658d2-c388-4bf5-9edb-3999416a9752"
if r.exists(metadata_key):
    data = r.execute_command('JSON.GET', metadata_key, '.')
    doc = json.loads(data)
    
    print(f"Document structure for {metadata_key}:")
    print(f"  Top-level keys: {list(doc.keys())}")
    
    if 'content' in doc:
        print(f"  Content: {json.dumps(doc['content'], indent=2)}")
        
    if 'metadata' in doc:
        print(f"  Document metadata: {json.dumps(doc['metadata'], indent=2)}")
        
    # The issue: doc['metadata'] has tags (array), but Identity.metadata expects version (number)
    print("\nThe conflict:")
    print("  - Document has 'metadata' field with tags (Vec<String>)")
    print("  - Identity struct expects metadata with version (u32)")
    print("  - When deserializing, it tries to put array into number field")

# Check all identity documents to see their metadata structure
print("\n\nChecking metadata structure in all identity documents...")
for key in r.scan_iter(match="*:identity:*:*", count=100):
    if r.type(key) == 'ReJSON-RL':
        try:
            data = r.execute_command('JSON.GET', key, '.')
            doc = json.loads(data)
            if 'metadata' in doc and isinstance(doc['metadata'], dict):
                if 'tags' in doc['metadata'] and isinstance(doc['metadata']['tags'], list):
                    parts = key.split(':')
                    field_type = parts[2] if len(parts) > 2 else 'unknown'
                    print(f"\n{key}")
                    print(f"  Field type: {field_type}")
                    print(f"  Has metadata.tags: {doc['metadata']['tags']}")
        except:
            pass
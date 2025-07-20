#!/usr/bin/env python3
import redis
import json
from datetime import datetime

# Connect to Redis with password
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

print("Checking metadata documents...\n")

# Find all metadata documents
metadata_docs = []
for key in r.scan_iter(match="*:identity:metadata:*", count=100):
    if r.type(key) == 'ReJSON-RL':
        metadata_docs.append(key)

print(f"Found {len(metadata_docs)} metadata documents\n")

for doc_key in sorted(metadata_docs):
    try:
        print(f"Checking: {doc_key}")
        
        # Get the document
        data = r.execute_command('JSON.GET', doc_key, '$')
        parsed = json.loads(data)
        
        # Handle JSONPath array result
        if isinstance(parsed, list) and len(parsed) > 0:
            doc = parsed[0]
        else:
            doc = parsed
            
        if isinstance(doc, dict) and 'content' in doc:
            content = doc['content']
            print(f"  Content: {json.dumps(content, indent=2)}")
            
            # Check if metadata has the expected structure
            expected_fields = ['version', 'last_updated', 'update_count', 'created_at']
            for field in expected_fields:
                if field in content:
                    value = content[field]
                    if field in ['last_updated', 'created_at']:
                        # These should be datetime strings
                        if not isinstance(value, str):
                            print(f"  ERROR: {field} is {type(value)} instead of string")
                            print(f"    Value: {value}")
                    elif field == 'version' or field == 'update_count':
                        # These should be numbers
                        if not isinstance(value, (int, float)):
                            print(f"  ERROR: {field} is {type(value)} instead of number")
                            print(f"    Value: {value}")
                            
        print()
        
    except Exception as e:
        print(f"  Error: {e}")
        print()
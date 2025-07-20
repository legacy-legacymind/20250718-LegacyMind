#!/usr/bin/env python3
import redis
import json

# Connect to Redis with password
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

print("Checking relationship documents specifically...\n")

# Find all relationship documents
relationship_docs = []
for key in r.scan_iter(match="*:identity:relationships:*", count=100):
    if r.type(key) == 'ReJSON-RL':
        relationship_docs.append(key)

print(f"Found {len(relationship_docs)} relationship documents\n")

for doc_key in sorted(relationship_docs):
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
            
        print(f"  Document type: {type(doc)}")
        
        if isinstance(doc, dict):
            print(f"  Keys: {list(doc.keys())}")
            
            if 'content' in doc:
                content = doc['content']
                print(f"  Content type: {type(content)}")
                print(f"  Content: {json.dumps(content, indent=2)}")
                
                # Check specific fields in RelationshipDynamics
                if isinstance(content, dict):
                    for field, value in content.items():
                        if field == 'interaction_style' and not isinstance(value, str):
                            print(f"  ERROR: interaction_style is {type(value)} instead of string")
                        elif field == 'current_standing' and not isinstance(value, str):
                            print(f"  ERROR: current_standing is {type(value)} instead of string")
                        elif field == 'trust_level' and not isinstance(value, (int, float)):
                            print(f"  ERROR: trust_level is {type(value)} instead of float")
                            
        print()
        
    except Exception as e:
        print(f"  Error: {e}")
        print()
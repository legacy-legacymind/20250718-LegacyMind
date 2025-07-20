#!/usr/bin/env python3
import redis
import json

# Connect to Redis with password
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

print("Checking all identity documents for arrays in string fields...\n")

# Get all identity documents
identity_docs = []
for key in r.scan_iter(match="*:identity:*", count=100):
    if r.type(key) == 'ReJSON-RL' and ':' in key:
        parts = key.split(':')
        if len(parts) >= 4:  # instance:identity:field_type:uuid
            identity_docs.append(key)

print(f"Found {len(identity_docs)} identity documents\n")

# String fields based on Identity struct
string_fields = {
    'core_info': ['name', 'instance_id', 'instance_type', 'primary_purpose'],
    'communication': ['tone', 'verbosity', 'formality'],
    'relationships': ['interaction_style', 'current_standing'],  # These are nested
    'work_preferences': ['planning_style', 'pace', 'autonomy_level', 'error_handling', 'documentation_style'],
    'behavioral_patterns': [],  # All are Vec<String>
    'technical_profile': [],  # All are Vec<String>
    'context_awareness': ['current_project', 'environment', 'instance_role', 'federation_position'],
    'memory_preferences': ['recall_style', 'context_depth', 'reference_style'],
}

# Check each document
issues_found = []
for doc_key in sorted(identity_docs):
    try:
        # Get the document
        data = r.execute_command('JSON.GET', doc_key, '$')
        parsed = json.loads(data)
        
        # Handle JSONPath array result
        if isinstance(parsed, list) and len(parsed) > 0:
            doc = parsed[0]
        else:
            doc = parsed
            
        if not isinstance(doc, dict) or 'content' not in doc:
            continue
            
        content = doc['content']
        field_type = doc.get('field_type', 'unknown')
        
        # Check string fields for this category
        if field_type in string_fields:
            for field_name in string_fields[field_type]:
                if field_name in content:
                    value = content[field_name]
                    if not isinstance(value, str):
                        issue = {
                            'key': doc_key,
                            'field_type': field_type,
                            'field': field_name,
                            'expected': 'string',
                            'actual': type(value).__name__,
                            'value': value
                        }
                        issues_found.append(issue)
                        print(f"ISSUE FOUND in {doc_key}:")
                        print(f"  Field: {field_name}")
                        print(f"  Expected: string")
                        print(f"  Actual: {type(value).__name__}")
                        print(f"  Value: {value}")
                        print()
                        
    except Exception as e:
        print(f"Error checking {doc_key}: {e}")

if not issues_found:
    print("No type mismatches found in identity documents")
else:
    print(f"\nTotal issues found: {len(issues_found)}")
    
# Also check for any monolithic identities that might have issues
print("\n\nChecking for problematic monolithic identities...")
for instance in ['CC', 'CCI', 'CCB', 'CCS', 'DT']:
    key = f"{instance}:identity"
    if r.exists(key):
        print(f"\nFound monolithic identity: {key}")
        try:
            data = r.execute_command('JSON.GET', key, '$')
            # This might be where the error occurs - if the stored data has arrays for string fields
            print(f"  Raw data type: {type(data)}")
            print(f"  First 200 chars: {str(data)[:200]}...")
        except Exception as e:
            print(f"  Error reading: {e}")
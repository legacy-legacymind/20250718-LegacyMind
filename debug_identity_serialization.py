#!/usr/bin/env python3
import redis
import json

# Connect to Redis with password
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

# Check the identity document structure
print("Checking identity document structure...")

# Get all identity keys for CC instance
identity_keys = []
for key in r.scan_iter(match="CC:identity:*"):
    identity_keys.append(key)

print(f"\nFound {len(identity_keys)} identity keys for CC instance:")
for key in sorted(identity_keys)[:10]:  # Show first 10
    print(f"  - {key}")

# Check a specific core_info document
test_key = "CC:identity:core_info:4456c1bb-191c-4618-a1e0-8413768ed9cb"
print(f"\nChecking structure of {test_key}...")

try:
    # Try to get as JSON
    data = r.execute_command('JSON.GET', test_key)
    parsed = json.loads(data)
    print(f"\nData type: {type(parsed)}")
    print(f"Data structure: {json.dumps(parsed, indent=2)[:500]}...")
    
    # If it's a list, check the first element
    if isinstance(parsed, list) and len(parsed) > 0:
        first_elem = parsed[0]
        print(f"\nFirst element type: {type(first_elem)}")
        print(f"First element keys: {list(first_elem.keys()) if isinstance(first_elem, dict) else 'Not a dict'}")
        
        if isinstance(first_elem, dict) and 'content' in first_elem:
            content = first_elem['content']
            print(f"\nContent type: {type(content)}")
            print(f"Content structure: {json.dumps(content, indent=2)[:300]}...")
            
            # Check for problematic fields
            if isinstance(content, dict):
                for field, value in content.items():
                    print(f"\n  Field '{field}': type={type(value)}")
                    if isinstance(value, list):
                        print(f"    List with {len(value)} items")
                        if len(value) > 0:
                            print(f"    First item: {value[0]}")
                    elif isinstance(value, str):
                        print(f"    String value: {value[:50]}...")
                        
except Exception as e:
    print(f"Error: {e}")

# Check all identity documents for array/string mismatches
print("\n\nChecking all identity documents for type mismatches...")
for key in identity_keys:
    try:
        data = r.execute_command('JSON.GET', key)
        parsed = json.loads(data)
        
        if isinstance(parsed, dict) and 'content' in parsed:
            content = parsed['content']
            field_type = parsed.get('field_type', 'unknown')
            
            # Check each field in content
            for field, value in content.items():
                # These fields should be strings based on the Identity struct
                string_fields = [
                    'name', 'instance_id', 'instance_type', 'primary_purpose',
                    'tone', 'verbosity', 'formality', 'interaction_style', 
                    'current_standing', 'planning_style', 'pace', 'autonomy_level',
                    'error_handling', 'documentation_style', 'current_project',
                    'environment', 'instance_role', 'federation_position',
                    'recall_style', 'context_depth', 'reference_style'
                ]
                
                if field in string_fields and not isinstance(value, str):
                    print(f"\nMISMATCH in {key}:")
                    print(f"  Field '{field}' expects string but got {type(value)}")
                    print(f"  Value: {value}")
                    
    except Exception as e:
        print(f"Error checking {key}: {e}")

# Check the monolithic identity if it exists
monolithic_key = "legacy:CC:identity"
print(f"\n\nChecking monolithic identity key: {monolithic_key}")
if r.exists(monolithic_key):
    try:
        data = r.execute_command('JSON.GET', monolithic_key)
        parsed = json.loads(data)
        print(f"Monolithic data exists, type: {type(parsed)}")
    except Exception as e:
        print(f"Error reading monolithic key: {e}")
else:
    print("Monolithic key does not exist")
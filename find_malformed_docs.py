#!/usr/bin/env python3
import redis
import json

# Connect to Redis with password
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

print("Finding all malformed identity documents...\n")

# Expected structure for each field type
expected_structures = {
    'core_info': ['name', 'instance_id', 'instance_type', 'primary_purpose', 'core_values'],
    'communication': ['tone', 'verbosity', 'humor_level', 'directness', 'formality'],
    'relationships': ['trust_level', 'interaction_style', 'boundaries', 'shared_history', 'current_standing'],
    'work_preferences': ['planning_style', 'pace', 'autonomy_level', 'error_handling', 'documentation_style'],
    'behavioral_patterns': ['common_mistakes', 'strengths', 'triggers', 'improvement_areas'],
    'technical_profile': ['preferred_languages', 'frameworks', 'tools', 'expertise_areas', 'learning_interests'],
    'context_awareness': ['current_project', 'environment', 'instance_role', 'federation_position', 'active_goals'],
    'memory_preferences': ['recall_style', 'priority_topics', 'context_depth', 'reference_style'],
}

malformed_docs = []

# Check all identity documents
for key in r.scan_iter(match="*:identity:*", count=100):
    if r.type(key) == 'ReJSON-RL' and ':' in key:
        parts = key.split(':')
        if len(parts) >= 4:  # instance:identity:field_type:uuid
            try:
                # Get the document
                data = r.execute_command('JSON.GET', key, '$')
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
                
                # Special check for relationships - they should have standard fields
                if field_type.startswith('relationships:'):
                    # This should be a RelationshipDynamics object
                    if not isinstance(content, dict) or not any(field in content for field in expected_structures['relationships']):
                        malformed_docs.append({
                            'key': key,
                            'field_type': field_type,
                            'issue': 'Not a valid RelationshipDynamics structure',
                            'content': content
                        })
                        print(f"MALFORMED: {key}")
                        print(f"  Field type: {field_type}")
                        print(f"  Content: {json.dumps(content, indent=2)[:200]}...")
                        print()
                        
                # Check if content has expected fields for the type
                elif field_type in expected_structures:
                    expected_fields = expected_structures[field_type]
                    if not any(field in content for field in expected_fields):
                        malformed_docs.append({
                            'key': key,
                            'field_type': field_type,
                            'issue': f'Missing expected fields for {field_type}',
                            'content': content
                        })
                        print(f"SUSPICIOUS: {key}")
                        print(f"  Field type: {field_type}")
                        print(f"  Expected fields: {expected_fields}")
                        print(f"  Actual fields: {list(content.keys())}")
                        print()
                        
            except Exception as e:
                print(f"Error checking {key}: {e}")

print(f"\nTotal malformed documents found: {len(malformed_docs)}")

# Now let's fix the malformed relationship document
if malformed_docs:
    print("\nAttempting to fix malformed documents...")
    for doc_info in malformed_docs:
        if 'relationships:' in doc_info['field_type']:
            print(f"\nDeleting malformed document: {doc_info['key']}")
            r.delete(doc_info['key'])
            print("  Deleted successfully")
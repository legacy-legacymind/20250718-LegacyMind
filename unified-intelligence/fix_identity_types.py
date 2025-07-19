#!/usr/bin/env python3
import redis
import json
import os
import sys

def fix_identity_types():
    # Get Redis password from environment
    redis_password = os.environ.get('REDIS_PASSWORD', '')
    
    if not redis_password:
        print("Error: REDIS_PASSWORD environment variable is required")
        print("Please set it with: export REDIS_PASSWORD='your-password'")
        return False
    
    # Connect to Redis with authentication
    r = redis.Redis(
        host='localhost', 
        port=6379, 
        password=redis_password,
        decode_responses=True
    )
    
    try:
        # Test connection
        r.ping()
        print("✓ Connected to Redis successfully")
    except Exception as e:
        print(f"✗ Failed to connect to Redis: {e}")
        return False
    
    # Look for identity keys
    identity_keys = []
    for key in r.scan_iter(match="*:identity"):
        identity_keys.append(key)
    
    if not identity_keys:
        print("No identity keys found in Redis")
        return True
    
    print(f"\nFound {len(identity_keys)} identity keys to check")
    
    # Fix each identity
    for key in identity_keys:
        print(f"\n{'='*60}")
        print(f"Processing: {key}")
        print('='*60)
        
        try:
            # Get the current identity data
            identity_json = r.execute_command('JSON.GET', key, '$')
            if not identity_json:
                print(f"  No data found for {key}")
                continue
            
            # Parse the JSON response
            identity_list = json.loads(identity_json)
            if not identity_list or not isinstance(identity_list, list):
                print(f"  Unexpected response format for {key}")
                continue
            
            identity_data = identity_list[0]
            
            # Track if we made any changes
            changes_made = False
            
            # Fix numeric fields that might be strings
            numeric_fields = {
                'communication': ['humor_level', 'directness'],
                'relationships': {
                    '*': ['trust_level', 'support_needed', 'communication_frequency']
                }
            }
            
            # Fix communication fields
            if 'communication' in identity_data:
                for field in numeric_fields['communication']:
                    if field in identity_data['communication']:
                        value = identity_data['communication'][field]
                        if isinstance(value, str):
                            try:
                                identity_data['communication'][field] = float(value)
                                print(f"  Fixed communication.{field}: '{value}' -> {float(value)}")
                                changes_made = True
                            except ValueError:
                                print(f"  Warning: Could not convert communication.{field} value '{value}' to float")
            
            # Fix relationship fields
            if 'relationships' in identity_data:
                for person, dynamics in identity_data['relationships'].items():
                    for field in numeric_fields['relationships']['*']:
                        if field in dynamics:
                            value = dynamics[field]
                            if isinstance(value, str):
                                try:
                                    identity_data['relationships'][person][field] = float(value)
                                    print(f"  Fixed relationships.{person}.{field}: '{value}' -> {float(value)}")
                                    changes_made = True
                                except ValueError:
                                    print(f"  Warning: Could not convert relationships.{person}.{field} value '{value}' to float")
            
            # Check for missing fields in technical_profile
            if 'technical_profile' in identity_data:
                tp = identity_data['technical_profile']
                required_fields = ['preferred_languages', 'frameworks', 'tools', 'expertise_areas', 'learning_interests']
                
                for field in required_fields:
                    if field not in tp:
                        # Add default empty array for missing fields
                        identity_data['technical_profile'][field] = []
                        print(f"  Added missing technical_profile.{field} field")
                        changes_made = True
            else:
                # Create default technical_profile if missing entirely
                identity_data['technical_profile'] = {
                    'preferred_languages': ['Rust', 'TypeScript'],
                    'frameworks': ['Tokio', 'rmcp'],
                    'tools': ['ui_think', 'Context7'],
                    'expertise_areas': ['MCP development', 'Redis'],
                    'learning_interests': ['vector databases', 'AI systems']
                }
                print("  Created missing technical_profile with defaults")
                changes_made = True
            
            # Save the fixed identity if we made changes
            if changes_made:
                # Use JSON.SET to update the entire identity
                r.execute_command('JSON.SET', key, '$', json.dumps(identity_data))
                print(f"\n✓ Successfully updated {key}")
            else:
                print(f"\n✓ No changes needed for {key}")
                
        except Exception as e:
            print(f"\n✗ Error processing {key}: {e}")
            import traceback
            traceback.print_exc()
    
    return True

if __name__ == "__main__":
    success = fix_identity_types()
    sys.exit(0 if success else 1)
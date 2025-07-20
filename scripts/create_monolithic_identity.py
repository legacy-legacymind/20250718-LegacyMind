#!/usr/bin/env python3
"""
Create monolithic identity from document-based storage.
This is the REVERSE of what CCI did - we're building monolithic FROM documents
so ui_identity view will work.
"""

import redis
import json
from typing import Dict, Any

# Redis connection
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
REDIS_PASSWORD = 'legacymind_redis_pass'

def connect_redis():
    """Connect to Docker Redis instance"""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=False  # Need bytes for JSON operations
    )

def documents_to_monolithic(r: redis.Redis, instance: str) -> Dict[str, Any]:
    """Convert document-based identity back to monolithic format"""
    
    # Initialize monolithic structure
    monolithic = {
        "core_info": {},
        "communication": {},
        "relationships": {},
        "work_preferences": {},
        "behavioral_patterns": {},
        "technical_profile": {},
        "context_awareness": {},
        "memory_preferences": {},
        "metadata": {}
    }
    
    # Scan for all identity documents
    pattern = f"{instance}:identity:*"
    documents_found = 0
    
    for key in r.scan_iter(match=pattern):
        key_str = key.decode('utf-8')
        
        # Skip index keys
        if key_str.endswith(':index'):
            continue
            
        try:
            # Get document content
            doc_json = r.execute_command('JSON.GET', key)
            if doc_json:
                doc = json.loads(doc_json)
                
                # Extract field type and content
                field_type = doc.get('field_type', '')
                content = doc.get('content', {})
                
                print(f"  Processing: {field_type}")
                documents_found += 1
                
                # Handle relationships specially
                if field_type.startswith('relationships:'):
                    person = field_type.split(':', 1)[1]
                    monolithic['relationships'][person] = content
                else:
                    # Direct field mapping
                    if field_type in monolithic:
                        monolithic[field_type] = content
                    
        except Exception as e:
            print(f"  Error processing {key_str}: {e}")
    
    print(f"  Processed {documents_found} documents")
    return monolithic

def create_monolithic_identity(r: redis.Redis, instance: str):
    """Create monolithic identity for an instance"""
    print(f"\nProcessing {instance}...")
    
    # Check if monolithic already exists
    monolithic_key = f"{instance}:identity"
    existing = None
    try:
        existing = r.execute_command('JSON.GET', monolithic_key)
    except:
        pass
        
    if existing:
        print(f"  Monolithic identity already exists at {monolithic_key}")
        return
    
    # Build monolithic from documents
    monolithic_data = documents_to_monolithic(r, instance)
    
    if not any(monolithic_data.values()):
        print(f"  No identity documents found for {instance}")
        return
    
    # Store as ReJSON
    try:
        r.execute_command('JSON.SET', monolithic_key, '.', json.dumps(monolithic_data))
        print(f"  ✓ Created monolithic identity at {monolithic_key}")
        
        # Verify it's readable
        test = r.execute_command('JSON.GET', monolithic_key)
        if test:
            print(f"  ✓ Verified monolithic identity is readable")
        
    except Exception as e:
        print(f"  ✗ Error creating monolithic identity: {e}")

def main():
    """Main conversion process"""
    print("Monolithic Identity Creation Script")
    print("=" * 50)
    print("This script creates monolithic identity from document-based storage")
    print("This allows ui_identity view to work correctly")
    print()
    
    # Connect to Redis
    try:
        r = connect_redis()
        r.ping()
        print("✓ Connected to Redis")
    except Exception as e:
        print(f"✗ Failed to connect to Redis: {e}")
        print("  Make sure Docker Redis is running on port 6379")
        return
    
    # Process each instance
    instances = ["CC", "CCI", "CCD", "CCS", "DT"]
    
    for instance in instances:
        create_monolithic_identity(r, instance)
    
    print("\n" + "=" * 50)
    print("Conversion complete!")
    print("\nTo verify:")
    print("1. Try ui_identity view - should work now")
    print("2. Check keys: docker exec legacymind-redis redis-cli -a 'legacymind_redis_pass' keys '*:identity'")

if __name__ == "__main__":
    main()
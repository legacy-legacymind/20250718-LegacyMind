#!/usr/bin/env python3
"""
Fix identity storage by converting from monolithic back to document-based format.
This fixes the damage done by CCI's conversion script.
"""

import redis
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any

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
        decode_responses=True
    )

def create_identity_document(field_type: str, content: Any, instance: str) -> Dict[str, Any]:
    """Create a new identity document"""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "field_type": field_type,
        "content": content,
        "instance": instance,
        "created_at": now,
        "updated_at": now,
        "version": 1,
        "embedding": None,
        "metadata": {
            "tags": [],
            "importance": None,
            "is_sensitive": False,
            "last_accessed": None,
            "access_count": 0
        }
    }

def monolithic_to_documents(monolithic_data: Dict[str, Any], instance: str) -> List[Dict[str, Any]]:
    """Convert monolithic identity JSON to document-based format"""
    documents = []
    
    for field_name, field_value in monolithic_data.items():
        # Skip internal fields
        if field_name.startswith('_'):
            continue
            
        # Handle relationships specially
        if field_name == "relationships" and isinstance(field_value, dict):
            for person, relationship_data in field_value.items():
                doc = create_identity_document(
                    f"relationships:{person}",
                    relationship_data,
                    instance
                )
                doc["metadata"]["tags"] = ["relationship", person]
                documents.append(doc)
        else:
            doc = create_identity_document(field_name, field_value, instance)
            
            # Add default tags based on field type
            if field_name == "basics":
                doc["metadata"]["tags"].append("core")
            elif field_name == "work_style":
                doc["metadata"]["tags"].append("preferences")
            elif field_name == "communication":
                doc["metadata"]["tags"].append("interaction")
                
            documents.append(doc)
    
    return documents

def create_identity_index(documents: List[Dict[str, Any]], instance: str) -> Dict[str, Any]:
    """Create an index for all identity documents"""
    fields = {}
    for doc in documents:
        field_type = doc["field_type"]
        if field_type not in fields:
            fields[field_type] = []
        fields[field_type].append(doc["id"])
    
    return {
        "fields": fields,
        "document_count": len(documents),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "instance": instance
    }

def fix_identity_storage(r: redis.Redis, instance: str):
    """Fix identity storage for a specific instance"""
    print(f"\nProcessing {instance}...")
    
    # Check for monolithic identity
    monolithic_key = f"identity:{instance}"
    monolithic_data = r.get(monolithic_key)
    
    if not monolithic_data:
        print(f"  No monolithic identity found for {instance}")
        return
    
    try:
        identity_data = json.loads(monolithic_data)
        print(f"  Found monolithic identity with {len(identity_data)} fields")
        
        # Convert to documents
        documents = monolithic_to_documents(identity_data, instance)
        print(f"  Created {len(documents)} documents")
        
        # Store each document
        stored = 0
        for doc in documents:
            key = f"{instance}:identity:{doc['field_type']}:{doc['id']}"
            r.set(key, json.dumps(doc))
            stored += 1
        
        # Create and store index
        index = create_identity_index(documents, instance)
        index_key = f"{instance}:identity:index"
        r.set(index_key, json.dumps(index))
        
        # Backup monolithic data before deletion
        backup_key = f"backup:monolithic:{instance}:{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        r.set(backup_key, monolithic_data)
        r.expire(backup_key, 86400 * 7)  # Keep backup for 7 days
        
        # Delete monolithic key
        r.delete(monolithic_key)
        
        print(f"  ✓ Successfully converted {stored} documents")
        print(f"  ✓ Index created at {index_key}")
        print(f"  ✓ Backup saved at {backup_key}")
        print(f"  ✓ Monolithic key deleted")
        
    except json.JSONDecodeError as e:
        print(f"  ✗ Error parsing JSON: {e}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

def main():
    """Main conversion process"""
    print("Identity Storage Fix Script")
    print("=" * 50)
    print("This script converts monolithic identity storage back to document-based format")
    print("Fixing the damage done by CCI's conversion script")
    print()
    
    # Connect to Redis
    try:
        r = connect_redis()
        r.ping()
        print("✓ Connected to Redis")
    except Exception as e:
        print(f"✗ Failed to connect to Redis: {e}")
        print("  Make sure Docker Redis is running on port 6380")
        return
    
    # Get all identity keys
    instances_to_check = ["CC", "CCI", "CCD", "CCS", "DT"]
    
    for instance in instances_to_check:
        fix_identity_storage(r, instance)
    
    print("\n" + "=" * 50)
    print("Conversion complete!")
    print("\nTo verify the conversion:")
    print("1. Try ui_identity view - should work now")
    print("2. Check document keys with: redis-cli keys '*:identity:*'")
    print("3. Backups are stored for 7 days with 'backup:monolithic:' prefix")

if __name__ == "__main__":
    main()
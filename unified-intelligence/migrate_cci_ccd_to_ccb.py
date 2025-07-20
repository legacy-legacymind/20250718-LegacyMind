#!/usr/bin/env python3
"""
Script to migrate CCI and CCD collections to CCB in Qdrant
Merges CCI_thoughts + CCD_thoughts -> CCB_thoughts
Merges CCI_identity + CCD_identity -> CCB_identity
"""

import requests
import json
import sys
from typing import List, Dict, Any

QDRANT_URL = "http://localhost:6333"

def get_collection_info(collection_name: str) -> Dict:
    """Get collection information"""
    response = requests.get(f"{QDRANT_URL}/collections/{collection_name}")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()

def create_collection(collection_name: str, vector_size: int = 1536) -> bool:
    """Create a new collection"""
    config = {
        "vectors": {
            "size": vector_size,
            "distance": "Cosine"
        },
        "optimizers_config": {
            "default_segment_number": 2,
            "indexing_threshold": 20000
        },
        "hnsw_config": {
            "m": 16,
            "ef_construct": 100,
            "full_scan_threshold": 10000
        }
    }
    
    response = requests.put(f"{QDRANT_URL}/collections/{collection_name}", json=config)
    if response.status_code == 200:
        print(f"✅ Created collection: {collection_name}")
        return True
    else:
        print(f"❌ Failed to create collection {collection_name}: {response.text}")
        return False

def get_all_points(collection_name: str) -> List[Dict]:
    """Get all points from a collection"""
    points = []
    offset = None
    
    while True:
        params = {"limit": 100, "with_payload": True, "with_vector": True}
        if offset:
            params["offset"] = offset
            
        response = requests.post(f"{QDRANT_URL}/collections/{collection_name}/points/scroll", json=params)
        if response.status_code != 200:
            print(f"❌ Failed to scroll collection {collection_name}: {response.text}")
            break
            
        data = response.json()
        batch_points = data["result"]["points"]
        
        if not batch_points:
            break
            
        points.extend(batch_points)
        
        if len(batch_points) < 100:  # Last batch
            break
            
        offset = batch_points[-1]["id"]
    
    return points

def update_instance_in_payload(points: List[Dict], old_instance: str, new_instance: str) -> List[Dict]:
    """Update instance field in point payloads"""
    updated_points = []
    
    for point in points:
        # Deep copy the point
        new_point = json.loads(json.dumps(point))
        
        # Update instance in payload if it exists
        if "payload" in new_point and isinstance(new_point["payload"], dict):
            if "instance" in new_point["payload"]:
                if new_point["payload"]["instance"] == old_instance:
                    new_point["payload"]["instance"] = new_instance
                    
        updated_points.append(new_point)
    
    return updated_points

def upsert_points(collection_name: str, points: List[Dict]) -> bool:
    """Upsert points into collection"""
    if not points:
        return True
        
    # Process in batches of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        
        upsert_data = {"points": batch}
        response = requests.put(f"{QDRANT_URL}/collections/{collection_name}/points", json=upsert_data)
        
        if response.status_code != 200:
            print(f"❌ Failed to upsert batch {i//batch_size + 1}: {response.text}")
            return False
        
        print(f"✅ Upserted batch {i//batch_size + 1} ({len(batch)} points)")
    
    return True

def delete_collection(collection_name: str) -> bool:
    """Delete a collection"""
    response = requests.delete(f"{QDRANT_URL}/collections/{collection_name}")
    if response.status_code == 200:
        print(f"✅ Deleted collection: {collection_name}")
        return True
    else:
        print(f"❌ Failed to delete collection {collection_name}: {response.text}")
        return False

def migrate_collections():
    """Main migration function"""
    print("🔄 Starting CCI/CCD to CCB migration...")
    
    # Define migration mappings
    migrations = [
        {
            "sources": ["CCI_thoughts", "CCD_thoughts"],
            "target": "CCB_thoughts",
            "type": "thoughts"
        },
        {
            "sources": ["CCI_identity", "CCD_identity"], 
            "target": "CCB_identity",
            "type": "identity"
        }
    ]
    
    for migration in migrations:
        print(f"\n📂 Migrating {migration['type']} collections...")
        
        # Check if target collection exists, create if not
        target_info = get_collection_info(migration["target"])
        if not target_info:
            if not create_collection(migration["target"]):
                print(f"❌ Failed to create target collection {migration['target']}")
                continue
        else:
            print(f"ℹ️  Target collection {migration['target']} already exists")
        
        all_points = []
        
        # Collect points from all source collections
        for source_collection in migration["sources"]:
            print(f"\n📥 Reading from {source_collection}...")
            
            source_info = get_collection_info(source_collection)
            if not source_info:
                print(f"⚠️  Collection {source_collection} not found, skipping")
                continue
                
            points_count = source_info["result"]["points_count"]
            print(f"ℹ️  Found {points_count} points in {source_collection}")
            
            if points_count == 0:
                print(f"⚠️  Collection {source_collection} is empty, skipping")
                continue
            
            # Get all points
            points = get_all_points(source_collection)
            print(f"📥 Retrieved {len(points)} points from {source_collection}")
            
            # Update instance field from CCI/CCD to CCB
            instance_name = source_collection.split("_")[0]  # CCI or CCD
            updated_points = update_instance_in_payload(points, instance_name, "CCB")
            
            all_points.extend(updated_points)
        
        if all_points:
            print(f"\n📤 Upserting {len(all_points)} total points to {migration['target']}...")
            if upsert_points(migration["target"], all_points):
                print(f"✅ Successfully migrated {len(all_points)} points to {migration['target']}")
            else:
                print(f"❌ Failed to migrate points to {migration['target']}")
        else:
            print(f"⚠️  No points to migrate for {migration['type']}")
    
    print("\n🎯 Migration summary:")
    # Show final collection counts
    for migration in migrations:
        target_info = get_collection_info(migration["target"])
        if target_info:
            count = target_info["result"]["points_count"]
            print(f"  {migration['target']}: {count} points")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--delete-source":
        print("⚠️  This will also delete source collections after migration!")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            return
        delete_sources = True
    else:
        delete_sources = False
        print("ℹ️  Source collections will be preserved. Use --delete-source to remove them after migration.")
    
    try:
        # Test Qdrant connection
        response = requests.get(f"{QDRANT_URL}/collections")
        response.raise_for_status()
        print("✅ Qdrant is accessible")
        
        migrate_collections()
        
        if delete_sources:
            print("\n🗑️  Deleting source collections...")
            for collection in ["CCI_thoughts", "CCD_thoughts", "CCI_identity", "CCD_identity"]:
                if get_collection_info(collection):
                    delete_collection(collection)
        
        print("\n🎉 Migration completed!")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to Qdrant: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
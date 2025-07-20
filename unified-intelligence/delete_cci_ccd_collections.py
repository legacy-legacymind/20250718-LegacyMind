#!/usr/bin/env python3
"""
Delete CCI and CCD collections from Qdrant after successful migration
"""
import requests

QDRANT_URL = "http://localhost:6333"

def delete_collection(collection_name: str) -> bool:
    """Delete a collection"""
    response = requests.delete(f"{QDRANT_URL}/collections/{collection_name}")
    if response.status_code == 200:
        print(f"✅ Deleted collection: {collection_name}")
        return True
    else:
        print(f"❌ Failed to delete collection {collection_name}: {response.text}")
        return False

def main():
    collections_to_delete = ["CCI_thoughts", "CCD_thoughts", "CCI_identity", "CCD_identity"]
    
    print("🗑️  Deleting CCI and CCD collections...")
    
    for collection in collections_to_delete:
        # Check if collection exists first
        response = requests.get(f"{QDRANT_URL}/collections/{collection}")
        if response.status_code == 404:
            print(f"⚠️  Collection {collection} not found, skipping")
            continue
        elif response.status_code != 200:
            print(f"❌ Error checking collection {collection}: {response.text}")
            continue
            
        delete_collection(collection)
    
    print("✅ Cleanup completed!")

if __name__ == "__main__":
    main()
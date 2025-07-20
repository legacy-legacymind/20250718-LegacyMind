#!/usr/bin/env python3
"""
Quick Qdrant backup before migration
"""
import requests
import json
import os
from datetime import datetime

QDRANT_URL = "http://localhost:6333"
BACKUP_DIR = "/Users/samuelatagana/LegacyMind_Vault/Qdrant_Backups"

def backup_qdrant():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create backup directory
    os.makedirs(f"{BACKUP_DIR}/snapshots", exist_ok=True)
    os.makedirs(f"{BACKUP_DIR}/manifests", exist_ok=True)
    
    print(f"🔄 Creating Qdrant backup at {timestamp}")
    
    # Get all collections
    response = requests.get(f"{QDRANT_URL}/collections")
    response.raise_for_status()
    collections = response.json()["result"]["collections"]
    
    backup_manifest = {
        "timestamp": timestamp,
        "collections": {}
    }
    
    for collection in collections:
        name = collection["name"]
        print(f"📂 Backing up collection: {name}")
        
        # Create snapshot
        snapshot_response = requests.post(f"{QDRANT_URL}/collections/{name}/snapshots")
        if snapshot_response.status_code == 200:
            snapshot_name = snapshot_response.json()["result"]["name"]
            
            # Download snapshot
            download_response = requests.get(f"{QDRANT_URL}/collections/{name}/snapshots/{snapshot_name}")
            if download_response.status_code == 200:
                snapshot_file = f"{BACKUP_DIR}/snapshots/{name}_{timestamp}.snapshot"
                with open(snapshot_file, "wb") as f:
                    f.write(download_response.content)
                
                backup_manifest["collections"][name] = {
                    "snapshot_file": snapshot_file,
                    "points_count": collection.get("points_count", 0)
                }
                print(f"✅ Backed up {name}: {collection.get('points_count', 0)} points")
            else:
                print(f"❌ Failed to download snapshot for {name}")
        else:
            print(f"❌ Failed to create snapshot for {name}")
    
    # Save manifest
    manifest_file = f"{BACKUP_DIR}/manifests/backup_manifest_{timestamp}.json"
    with open(manifest_file, "w") as f:
        json.dump(backup_manifest, f, indent=2)
    
    print(f"✅ Backup completed: {len(backup_manifest['collections'])} collections")
    print(f"📄 Manifest: {manifest_file}")
    
    return timestamp

if __name__ == "__main__":
    try:
        backup_qdrant()
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        exit(1)
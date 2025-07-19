#!/usr/bin/env python3
"""
Script to change all "Claude" instance IDs to "CC" in Redis
"""

import redis
import json
import time
from typing import List, Dict

def connect_redis() -> redis.Redis:
    """Connect to Redis"""
    return redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', db=0)

def find_claude_keys(client: redis.Redis) -> List[str]:
    """Find all keys with 'Claude' instance ID"""
    patterns = [
        "Claude:*",
        "*:Claude:*"
    ]
    
    all_keys = []
    for pattern in patterns:
        keys = client.keys(pattern)
        all_keys.extend([key.decode() if isinstance(key, bytes) else key for key in keys])
    
    return list(set(all_keys))  # Remove duplicates

def rename_key(client: redis.Redis, old_key: str) -> str:
    """Rename a key from Claude to CC"""
    new_key = old_key.replace("Claude:", "CC:").replace(":Claude:", ":CC:")
    return new_key

def update_key_content(client: redis.Redis, key: str, new_key: str) -> bool:
    """Update content within a key if it contains instance references"""
    try:
        # Get the key type
        key_type = client.type(key).decode()
        
        if key_type == "string":
            # Handle string keys (JSON data)
            content = client.get(key)
            if content:
                content_str = content.decode()
                
                # Check if it's JSON
                try:
                    data = json.loads(content_str)
                    
                    # Update instance field if it exists
                    if isinstance(data, dict) and "instance" in data:
                        if data["instance"] == "Claude":
                            data["instance"] = "CC"
                            
                            # Store updated content with new key
                            client.set(new_key, json.dumps(data))
                            client.delete(key)
                            return True
                    
                    # If no instance field but key changed, just copy
                    if new_key != key:
                        client.set(new_key, content_str)
                        client.delete(key)
                        return True
                        
                except json.JSONDecodeError:
                    # Not JSON, just copy if key changed
                    if new_key != key:
                        client.set(new_key, content_str)
                        client.delete(key)
                        return True
        
        elif key_type == "zset":
            # Handle sorted sets
            if new_key != key:
                client.zunionstore(new_key, [key])
                client.delete(key)
                return True
                
        elif key_type == "hash":
            # Handle hashes
            if new_key != key:
                client.hgetall(key)
                hash_data = client.hgetall(key)
                if hash_data:
                    client.hset(new_key, mapping=hash_data)
                    client.delete(key)
                    return True
                    
        elif key_type == "list":
            # Handle lists
            if new_key != key:
                list_data = client.lrange(key, 0, -1)
                if list_data:
                    client.rpush(new_key, *list_data)
                    client.delete(key)
                    return True
        
        return False
        
    except Exception as e:
        print(f"Error updating key {key}: {e}")
        return False

def main():
    """Main function to rename all Claude instances to CC"""
    print("Starting Claude -> CC instance ID migration...")
    
    # Connect to Redis
    client = connect_redis()
    
    # Find all Claude keys
    claude_keys = find_claude_keys(client)
    print(f"Found {len(claude_keys)} keys with 'Claude' instance ID")
    
    if not claude_keys:
        print("No Claude keys found. Migration complete.")
        return
    
    # Show what will be changed
    print("\nKeys to be updated:")
    for key in claude_keys[:10]:  # Show first 10
        new_key = rename_key(client, key)
        print(f"  {key} -> {new_key}")
    
    if len(claude_keys) > 10:
        print(f"  ... and {len(claude_keys) - 10} more")
    
    # Auto-proceed (running in automated mode)
    print(f"\nProceeding with updating {len(claude_keys)} keys...")
    
    # Process each key
    successful = 0
    failed = 0
    
    print("\nProcessing keys...")
    for i, key in enumerate(claude_keys):
        try:
            new_key = rename_key(client, key)
            if update_key_content(client, key, new_key):
                successful += 1
                print(f"  ✓ {key} -> {new_key}")
            else:
                print(f"  - {key} (no change needed)")
            
            # Progress indicator
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{len(claude_keys)}")
                
        except Exception as e:
            failed += 1
            print(f"  ✗ Failed to process {key}: {e}")
    
    print(f"\nMigration complete!")
    print(f"  Successfully updated: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Total processed: {len(claude_keys)}")
    
    # Verify the changes
    remaining_claude_keys = find_claude_keys(client)
    if remaining_claude_keys:
        print(f"\nWarning: {len(remaining_claude_keys)} Claude keys still remain:")
        for key in remaining_claude_keys[:5]:
            print(f"  {key}")
    else:
        print("\n✓ All Claude instance IDs successfully changed to CC!")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Backup all thoughts from Redis to a JSON file before conversion.
"""

import redis
import json
from datetime import datetime
import os

# Redis connection
r = redis.Redis(
    host='127.0.0.1',
    port=6379,
    password='legacymind_redis_pass',
    decode_responses=True
)

def backup_thoughts():
    """Backup all thoughts to a JSON file"""
    backup_data = {
        'backup_time': datetime.now().isoformat(),
        'thoughts': {}
    }
    
    # Scan for all thought keys
    cursor = 0
    count = 0
    
    while True:
        cursor, keys = r.scan(cursor, match="*:Thoughts:*", count=100)
        
        for key in keys:
            key_type = r.type(key)
            
            if key_type == 'string':
                content = r.get(key)
                backup_data['thoughts'][key] = {
                    'type': 'string',
                    'content': content
                }
            elif key_type == 'ReJSON-RL':
                content = r.execute_command('JSON.GET', key, '.')
                backup_data['thoughts'][key] = {
                    'type': 'ReJSON-RL',
                    'content': content
                }
            
            count += 1
            if count % 100 == 0:
                print(f"Backed up {count} thoughts...")
        
        if cursor == 0:
            break
    
    # Save to file
    backup_file = f"/Users/samuelatagana/Projects/LegacyMind/Memory/redis/backups/thoughts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(backup_file), exist_ok=True)
    
    with open(backup_file, 'w') as f:
        json.dump(backup_data, f, indent=2)
    
    print(f"\n✅ Backed up {count} thoughts to: {backup_file}")
    return backup_file

if __name__ == "__main__":
    print("Creating backup of all thoughts...")
    backup_file = backup_thoughts()
    print(f"\nBackup complete! File saved to: {backup_file}")
#!/usr/bin/env python3
"""
Convert string-stored thoughts to ReJSON format in Redis.
The string thoughts are valid JSON but stored as strings rather than using RedisJSON.
"""

import redis
import json
import sys
from datetime import datetime

# Redis connection
r = redis.Redis(
    host='127.0.0.1',
    port=6379,
    password='legacymind_redis_pass',
    decode_responses=True
)

def convert_thought_to_rejson(key):
    """Convert a string-stored thought to ReJSON format"""
    try:
        # Get the current type
        key_type = r.type(key)
        
        if key_type == 'string':
            # Get the string value
            thought_str = r.get(key)
            
            if thought_str:
                # Parse the JSON
                thought_data = json.loads(thought_str)
                
                # Fix missing 'content' field if needed
                if 'content' not in thought_data and 'thought' in thought_data:
                    thought_data['content'] = thought_data['thought']
                
                # Fix timestamp format if it's a raw number
                if 'timestamp' in thought_data and isinstance(thought_data['timestamp'], (int, float)):
                    # Convert Unix timestamp to ISO format
                    dt = datetime.fromtimestamp(thought_data['timestamp'])
                    thought_data['timestamp'] = dt.isoformat() + '+00:00'
                
                # Delete the old string key
                r.delete(key)
                
                # Set as JSON using RedisJSON
                r.execute_command('JSON.SET', key, '.', json.dumps(thought_data))
                
                return True, "Converted successfully"
        else:
            return False, f"Key is already type: {key_type}"
            
    except json.JSONDecodeError as e:
        return False, f"JSON decode error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def main():
    print("Scanning for thought keys...")
    
    # Track statistics
    total_thoughts = 0
    converted = 0
    already_json = 0
    errors = 0
    
    # Scan for all thought keys
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor, match="*:Thoughts:*", count=100)
        
        for key in keys:
            total_thoughts += 1
            key_type = r.type(key)
            
            if key_type == 'string':
                success, message = convert_thought_to_rejson(key)
                if success:
                    converted += 1
                    print(f"✓ Converted: {key}")
                else:
                    errors += 1
                    print(f"✗ Failed {key}: {message}")
            elif key_type == 'ReJSON-RL':
                already_json += 1
                print(f"• Already JSON: {key}")
            else:
                print(f"? Unknown type {key_type}: {key}")
        
        if cursor == 0:
            break
    
    # Print summary
    print("\n" + "="*50)
    print("CONVERSION SUMMARY")
    print("="*50)
    print(f"Total thoughts found: {total_thoughts}")
    print(f"Converted to JSON:    {converted}")
    print(f"Already JSON:         {already_json}")
    print(f"Errors:               {errors}")
    print("="*50)
    
    if errors > 0:
        print("\n⚠️  Some conversions failed. Check the error messages above.")
        sys.exit(1)
    else:
        print("\n✅ All string thoughts successfully converted to ReJSON!")

if __name__ == "__main__":
    # Confirm before proceeding
    print("This script will convert all string-stored thoughts to ReJSON format.")
    print("This will modify Redis data. Make sure you have a backup!")
    response = input("\nProceed? (yes/no): ")
    
    if response.lower() == 'yes':
        main()
    else:
        print("Aborted.")
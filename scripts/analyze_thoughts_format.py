#!/usr/bin/env python3
"""
Analyze the format of thoughts in Redis to understand the mix of string vs ReJSON storage.
This is a read-only script that doesn't modify any data.
"""

import redis
import json
from collections import defaultdict

# Redis connection
r = redis.Redis(
    host='127.0.0.1',
    port=6379,
    password='legacymind_redis_pass',
    decode_responses=True
)

def analyze_thought(key):
    """Analyze a single thought key"""
    key_type = r.type(key)
    instance = key.split(':')[0]
    
    result = {
        'key': key,
        'instance': instance,
        'type': key_type,
        'valid_json': False,
        'has_all_fields': False,
        'sample': None
    }
    
    if key_type == 'string':
        try:
            thought_str = r.get(key)
            thought_data = json.loads(thought_str)
            result['valid_json'] = True
            
            # Check for expected fields
            expected_fields = ['id', 'instance', 'thought', 'content', 'timestamp']
            result['has_all_fields'] = all(field in thought_data for field in expected_fields)
            
            # Get a sample of the data
            result['sample'] = {
                'id': thought_data.get('id', 'missing'),
                'instance': thought_data.get('instance', 'missing'),
                'timestamp': str(thought_data.get('timestamp', 'missing'))[:50],
                'thought_preview': thought_data.get('thought', '')[:50] + '...'
            }
            
        except json.JSONDecodeError:
            result['valid_json'] = False
            
    elif key_type == 'ReJSON-RL':
        try:
            thought_data = json.loads(r.execute_command('JSON.GET', key, '.'))
            result['valid_json'] = True
            
            # Check for expected fields
            expected_fields = ['id', 'instance', 'thought', 'content', 'timestamp']
            result['has_all_fields'] = all(field in thought_data for field in expected_fields)
            
            # Get a sample of the data
            result['sample'] = {
                'id': thought_data.get('id', 'missing'),
                'instance': thought_data.get('instance', 'missing'),
                'timestamp': str(thought_data.get('timestamp', 'missing'))[:50],
                'thought_preview': thought_data.get('thought', '')[:50] + '...'
            }
            
        except:
            result['valid_json'] = False
    
    return result

def main():
    print("Analyzing thought storage formats...\n")
    
    # Statistics
    stats = defaultdict(lambda: defaultdict(int))
    string_thoughts = []
    rejson_thoughts = []
    problem_thoughts = []
    
    # Scan for all thought keys
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor, match="*:Thoughts:*", count=100)
        
        for key in keys:
            analysis = analyze_thought(key)
            instance = analysis['instance']
            key_type = analysis['type']
            
            stats[instance][key_type] += 1
            stats['TOTAL'][key_type] += 1
            
            if key_type == 'string':
                string_thoughts.append(analysis)
                if not analysis['valid_json'] or not analysis['has_all_fields']:
                    problem_thoughts.append(analysis)
            elif key_type == 'ReJSON-RL':
                rejson_thoughts.append(analysis)
                if not analysis['valid_json'] or not analysis['has_all_fields']:
                    problem_thoughts.append(analysis)
        
        if cursor == 0:
            break
    
    # Print summary statistics
    print("="*60)
    print("STORAGE FORMAT SUMMARY BY INSTANCE")
    print("="*60)
    print(f"{'Instance':<10} {'String':<10} {'ReJSON':<10} {'Total':<10}")
    print("-"*40)
    
    for instance in sorted([i for i in stats.keys() if i != 'TOTAL']):
        string_count = stats[instance]['string']
        rejson_count = stats[instance]['ReJSON-RL']
        total = string_count + rejson_count
        print(f"{instance:<10} {string_count:<10} {rejson_count:<10} {total:<10}")
    
    print("-"*40)
    total_string = stats['TOTAL']['string']
    total_rejson = stats['TOTAL']['ReJSON-RL']
    print(f"{'TOTAL':<10} {total_string:<10} {total_rejson:<10} {total_string + total_rejson:<10}")
    
    # Show sample of string thoughts
    if string_thoughts:
        print("\n" + "="*60)
        print("SAMPLE STRING-STORED THOUGHTS (need conversion)")
        print("="*60)
        for thought in string_thoughts[:5]:
            print(f"\nKey: {thought['key']}")
            if thought['sample']:
                print(f"  ID: {thought['sample']['id']}")
                print(f"  Instance: {thought['sample']['instance']}")
                print(f"  Timestamp: {thought['sample']['timestamp']}")
                print(f"  Preview: {thought['sample']['thought_preview']}")
    
    # Show any problematic thoughts
    if problem_thoughts:
        print("\n" + "="*60)
        print("⚠️  PROBLEMATIC THOUGHTS (invalid JSON or missing fields)")
        print("="*60)
        for thought in problem_thoughts:
            print(f"\nKey: {thought['key']}")
            print(f"  Type: {thought['type']}")
            print(f"  Valid JSON: {thought['valid_json']}")
            print(f"  Has all fields: {thought['has_all_fields']}")
    
    # Recommendation
    print("\n" + "="*60)
    print("RECOMMENDATION")
    print("="*60)
    if total_string > 0:
        print(f"Found {total_string} thoughts stored as strings that should be converted to ReJSON.")
        print("Run convert_thoughts_to_json.py to convert them.")
    else:
        print("✅ All thoughts are already stored in ReJSON format!")
    
    if problem_thoughts:
        print(f"\n⚠️  Found {len(problem_thoughts)} problematic thoughts that may need manual review.")

if __name__ == "__main__":
    main()
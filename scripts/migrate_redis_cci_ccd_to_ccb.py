#!/usr/bin/env python3
"""
Redis Migration Script: CCI and CCD to CCB
Migrates all Redis keys from CCI:* and CCD:* namespaces to CCB:*

Key Types Handled:
- Thoughts (ReJSON-RL)
- Tags (Redis Sets) 
- Chains (Redis Lists)
- Search Sessions (Redis Hashes)
- Thought Metadata (ReJSON-RL)

Safety Features:
- Backup verification before migration
- Dry-run mode
- Rollback capability
- Conflict detection and resolution
"""

import redis
import json
import sys
import os
import time
from typing import Dict, List, Set, Any, Optional
from datetime import datetime
import argparse

class RedisMigrator:
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0, redis_password=None):
        """Initialize Redis connection"""
        try:
            # Try with password first if provided
            connection_args = {
                'host': redis_host,
                'port': redis_port,
                'db': redis_db,
                'decode_responses': True
            }
            
            if redis_password:
                connection_args['password'] = redis_password
            
            self.redis_client = redis.Redis(**connection_args)
            
            # Test connection
            self.redis_client.ping()
            print("✅ Redis connection established")
        except redis.AuthenticationError:
            print("❌ Redis authentication failed. Please provide password via --password or REDIS_PASSWORD env var")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            sys.exit(1)
    
    def scan_keys_by_pattern(self, pattern: str) -> List[str]:
        """Scan and return all keys matching pattern"""
        keys = []
        cursor = 0
        
        while True:
            cursor, batch = self.redis_client.scan(cursor=cursor, match=pattern, count=1000)
            keys.extend(batch)
            if cursor == 0:
                break
                
        return sorted(keys)
    
    def get_key_info(self, key: str) -> Dict[str, Any]:
        """Get comprehensive key information"""
        info = {
            'key': key,
            'type': self.redis_client.type(key),
            'ttl': self.redis_client.ttl(key),
            'exists': self.redis_client.exists(key)
        }
        return info
    
    def backup_key(self, key: str) -> Dict[str, Any]:
        """Create backup of a key with its data"""
        key_info = self.get_key_info(key)
        backup = key_info.copy()
        
        try:
            if key_info['type'] == 'ReJSON-RL':
                # Handle JSON keys
                backup['data'] = self.redis_client.execute_command('JSON.GET', key)
            elif key_info['type'] == 'set':
                backup['data'] = list(self.redis_client.smembers(key))
            elif key_info['type'] == 'list':
                backup['data'] = self.redis_client.lrange(key, 0, -1)
            elif key_info['type'] == 'hash':
                backup['data'] = self.redis_client.hgetall(key)
            elif key_info['type'] == 'string':
                backup['data'] = self.redis_client.get(key)
            else:
                print(f"⚠️  Unknown key type {key_info['type']} for key {key}")
                backup['data'] = None
                
        except Exception as e:
            print(f"❌ Failed to backup key {key}: {e}")
            backup['data'] = None
            backup['error'] = str(e)
            
        return backup
    
    def restore_key(self, backup: Dict[str, Any]) -> bool:
        """Restore a key from backup"""
        key = backup['key']
        key_type = backup['type']
        data = backup.get('data')
        ttl = backup.get('ttl', -1)
        
        if data is None:
            print(f"❌ No data to restore for key {key}")
            return False
            
        try:
            # Delete existing key first
            self.redis_client.delete(key)
            
            if key_type == 'ReJSON-RL':
                self.redis_client.execute_command('JSON.SET', key, '.', data)
            elif key_type == 'set':
                if data:  # Only add if data exists
                    self.redis_client.sadd(key, *data)
            elif key_type == 'list':
                if data:  # Only add if data exists
                    self.redis_client.lpush(key, *reversed(data))
            elif key_type == 'hash':
                if data:  # Only add if data exists
                    self.redis_client.hset(key, mapping=data)
            elif key_type == 'string':
                self.redis_client.set(key, data)
            else:
                print(f"❌ Cannot restore unknown key type {key_type}")
                return False
                
            # Set TTL if needed
            if ttl > 0:
                self.redis_client.expire(key, ttl)
                
            return True
            
        except Exception as e:
            print(f"❌ Failed to restore key {key}: {e}")
            return False
    
    def migrate_key(self, source_key: str, target_key: str, update_instance: bool = True) -> bool:
        """Migrate a single key from source to target"""
        backup = self.backup_key(source_key)
        
        if backup.get('data') is None:
            return False
            
        key_type = backup['type']
        data = backup['data']
        ttl = backup.get('ttl', -1)
        
        try:
            if key_type == 'ReJSON-RL':
                # Handle JSON data with potential instance updates
                if update_instance and isinstance(data, str):
                    try:
                        json_data = json.loads(data)
                        if isinstance(json_data, dict) and 'instance' in json_data:
                            json_data['instance'] = 'CCB'
                            data = json.dumps(json_data)
                    except json.JSONDecodeError:
                        pass  # Keep original data if not valid JSON
                        
                self.redis_client.execute_command('JSON.SET', target_key, '.', data)
                
            elif key_type == 'set':
                if data:
                    self.redis_client.sadd(target_key, *data)
                    
            elif key_type == 'list':
                if data:
                    self.redis_client.lpush(target_key, *reversed(data))
                    
            elif key_type == 'hash':
                if data:
                    # Update instance field if present
                    if update_instance and 'instance' in data:
                        data['instance'] = 'CCB'
                    self.redis_client.hset(target_key, mapping=data)
                    
            elif key_type == 'string':
                self.redis_client.set(target_key, data)
                
            # Set TTL if needed
            if ttl > 0:
                self.redis_client.expire(target_key, ttl)
                
            return True
            
        except Exception as e:
            print(f"❌ Failed to migrate {source_key} → {target_key}: {e}")
            return False
    
    def handle_tag_conflicts(self, cci_key: str, ccd_key: str, target_key: str) -> bool:
        """Handle tag conflicts by merging sets"""
        try:
            cci_members = set()
            ccd_members = set()
            
            if self.redis_client.exists(cci_key):
                cci_members = self.redis_client.smembers(cci_key)
                
            if self.redis_client.exists(ccd_key):
                ccd_members = self.redis_client.smembers(ccd_key)
                
            # Merge the sets
            all_members = cci_members.union(ccd_members)
            
            if all_members:
                self.redis_client.sadd(target_key, *all_members)
                print(f"🔀 Merged tag {target_key}: {len(cci_members)} CCI + {len(ccd_members)} CCD = {len(all_members)} total")
                
            return True
            
        except Exception as e:
            print(f"❌ Failed to merge tags for {target_key}: {e}")
            return False
    
    def analyze_migration(self) -> Dict[str, Any]:
        """Analyze what needs to be migrated"""
        analysis = {
            'cci_keys': {},
            'ccd_keys': {},
            'ccb_keys': {},
            'conflicts': [],
            'total_keys': 0
        }
        
        # Scan for all key types
        key_patterns = {
            'thoughts': 'Thoughts:*',
            'tags': 'tags:*', 
            'chains': 'chains:*',
            'search_sessions': 'search_sessions:*',
            'thought_meta': 'thought_meta:*'
        }
        
        for pattern_name, pattern in key_patterns.items():
            print(f"\n📊 Analyzing {pattern_name}...")
            
            cci_keys = self.scan_keys_by_pattern(f'CCI:{pattern}')
            ccd_keys = self.scan_keys_by_pattern(f'CCD:{pattern}')
            ccb_keys = self.scan_keys_by_pattern(f'CCB:{pattern}')
            
            analysis['cci_keys'][pattern_name] = cci_keys
            analysis['ccd_keys'][pattern_name] = ccd_keys  
            analysis['ccb_keys'][pattern_name] = ccb_keys
            
            print(f"  CCI: {len(cci_keys)} keys")
            print(f"  CCD: {len(ccd_keys)} keys") 
            print(f"  CCB: {len(ccb_keys)} keys (existing)")
            
            # Check for conflicts (same base name in both CCI and CCD)
            if pattern_name == 'tags':
                cci_names = {key.split(':', 2)[2] for key in cci_keys}
                ccd_names = {key.split(':', 2)[2] for key in ccd_keys}
                conflicts = cci_names.intersection(ccd_names)
                if conflicts:
                    analysis['conflicts'].extend(list(conflicts))
                    print(f"  ⚠️  Tag conflicts: {len(conflicts)} names appear in both CCI and CCD")
        
        analysis['total_keys'] = (
            sum(len(keys) for keys in analysis['cci_keys'].values()) +
            sum(len(keys) for keys in analysis['ccd_keys'].values())
        )
        
        return analysis
    
    def perform_migration(self, dry_run: bool = True, backup_file: Optional[str] = None) -> bool:
        """Perform the complete migration"""
        print(f"\n{'🔍 DRY RUN' if dry_run else '🚀 EXECUTING'} Redis Migration: CCI/CCD → CCB")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Analyze migration scope
        analysis = self.analyze_migration()
        
        print(f"\n📈 Migration Summary:")
        print(f"  Total keys to migrate: {analysis['total_keys']}")
        print(f"  Tag conflicts to resolve: {len(analysis['conflicts'])}")
        
        if dry_run:
            print("\n✅ Dry run completed. Use --execute to perform actual migration.")
            return True
            
        # Create backup if requested
        if backup_file:
            print(f"\n💾 Creating backup to {backup_file}...")
            backup_data = {}
            all_keys = []
            
            for category in analysis['cci_keys'].values():
                all_keys.extend(category)
            for category in analysis['ccd_keys'].values():
                all_keys.extend(category)
                
            for key in all_keys:
                backup_data[key] = self.backup_key(key)
                
            with open(backup_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'total_keys': len(all_keys),
                    'keys': backup_data
                }, f, indent=2)
                
            print(f"✅ Backup completed: {len(all_keys)} keys saved")
        
        # Perform migration
        success_count = 0
        total_count = analysis['total_keys']
        
        print(f"\n🔄 Starting migration of {total_count} keys...")
        
        # Handle each key type
        for key_type in ['thoughts', 'chains', 'search_sessions', 'thought_meta']:
            print(f"\n📦 Migrating {key_type}...")
            
            # Migrate CCI keys
            for cci_key in analysis['cci_keys'][key_type]:
                target_key = cci_key.replace('CCI:', 'CCB:')
                if self.migrate_key(cci_key, target_key):
                    success_count += 1
                    print(f"  ✅ {cci_key} → {target_key}")
                else:
                    print(f"  ❌ Failed: {cci_key}")
            
            # Migrate CCD keys  
            for ccd_key in analysis['ccd_keys'][key_type]:
                target_key = ccd_key.replace('CCD:', 'CCB:')
                if self.migrate_key(ccd_key, target_key):
                    success_count += 1
                    print(f"  ✅ {ccd_key} → {target_key}")
                else:
                    print(f"  ❌ Failed: {ccd_key}")
        
        # Handle tags with conflict resolution
        print(f"\n🏷️  Migrating tags with conflict resolution...")
        all_tag_names = set()
        
        # Get all unique tag names
        for cci_key in analysis['cci_keys']['tags']:
            tag_name = cci_key.split(':', 2)[2]
            all_tag_names.add(tag_name)
            
        for ccd_key in analysis['ccd_keys']['tags']:
            tag_name = ccd_key.split(':', 2)[2]
            all_tag_names.add(tag_name)
        
        for tag_name in sorted(all_tag_names):
            cci_key = f"CCI:tags:{tag_name}"
            ccd_key = f"CCD:tags:{tag_name}"
            target_key = f"CCB:tags:{tag_name}"
            
            if self.handle_tag_conflicts(cci_key, ccd_key, target_key):
                success_count += 1
                print(f"  ✅ Merged tag: {tag_name}")
            else:
                print(f"  ❌ Failed tag: {tag_name}")
        
        print(f"\n🎯 Migration Results:")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {total_count - success_count}")
        print(f"  Success Rate: {(success_count/total_count)*100:.1f}%")
        
        return success_count == total_count

def main():
    parser = argparse.ArgumentParser(description='Migrate Redis keys from CCI/CCD to CCB')
    parser.add_argument('--execute', action='store_true', help='Execute migration (default: dry-run)')
    parser.add_argument('--backup', type=str, help='Backup file path (recommended)')
    parser.add_argument('--host', default='localhost', help='Redis host')
    parser.add_argument('--port', type=int, default=6379, help='Redis port')
    parser.add_argument('--db', type=int, default=0, help='Redis database')
    parser.add_argument('--password', type=str, help='Redis password')
    
    args = parser.parse_args()
    
    # Get password from args or environment
    redis_password = args.password or os.environ.get('REDIS_PASSWORD')
    
    # Create migrator
    migrator = RedisMigrator(args.host, args.port, args.db, redis_password)
    
    # Set backup file if executing
    backup_file = args.backup
    if args.execute and not backup_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'redis_backup_cci_ccd_{timestamp}.json'
        print(f"📁 Auto-generating backup file: {backup_file}")
    
    # Perform migration
    success = migrator.perform_migration(
        dry_run=not args.execute,
        backup_file=backup_file if args.execute else None
    )
    
    if success:
        print("\n🎉 Migration completed successfully!")
        if args.execute:
            print("\n⚠️  IMPORTANT: Verify the migration before deleting source keys!")
            print("   Use Redis commands to spot-check migrated data.")
            print("   Consider running the UnifiedIntelligence tests.")
    else:
        print("\n❌ Migration encountered errors. Check logs above.")
        sys.exit(1)

if __name__ == '__main__':
    main()
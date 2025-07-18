#!/usr/bin/env python3
"""
Federation Auto-Discovery for Embedding Service
Automatically discovers all federation instances (CC, CCI, CCD, CCS, etc.) and processes embeddings.
Built for Phase 1 deployment with dynamic instance detection.
"""

import redis
import json
import time
from typing import Set, List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FederationInstance:
    """Represents a federation instance"""
    name: str
    thoughts_count: int
    embeddings_count: int
    missing_embeddings: int
    last_activity: Optional[datetime] = None


class FederationAutoDiscovery:
    """
    Auto-discovery service for federation instances.
    Finds all instances with thoughts and manages embedding generation.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.known_instances: Set[str] = set()
        self.instance_stats: Dict[str, FederationInstance] = {}
        
    def discover_federation_instances(self) -> List[FederationInstance]:
        """
        Auto-discover all federation instances by scanning Redis keys.
        Looks for patterns: {INSTANCE}:Thoughts:* and {INSTANCE}:embeddings:*
        """
        try:
            # Scan for all thought keys to find instances
            thought_keys = self.redis.keys("*:Thoughts:*")
            embedding_keys = self.redis.keys("*:embeddings:*")
            
            # Extract instance names from thought keys
            instances_with_thoughts = set()
            for key in thought_keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                instance = key_str.split(':')[0]
                if instance and instance != 'config':  # Skip config keys
                    instances_with_thoughts.add(instance)
            
            # Extract instance names from embedding keys
            instances_with_embeddings = set()
            for key in embedding_keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                instance = key_str.split(':')[0]
                if instance and instance != 'config':  # Skip config keys
                    instances_with_embeddings.add(instance)
            
            # Combine all discovered instances
            all_instances = instances_with_thoughts.union(instances_with_embeddings)
            
            # Get detailed stats for each instance
            federation_instances = []
            for instance in all_instances:
                stats = self._get_instance_stats(instance)
                if stats:
                    federation_instances.append(stats)
                    self.known_instances.add(instance)
                    self.instance_stats[instance] = stats
            
            # Sort by activity (most active first)
            federation_instances.sort(key=lambda x: x.missing_embeddings, reverse=True)
            
            print(f"Discovered {len(federation_instances)} federation instances:")
            for instance in federation_instances:
                print(f"  {instance.name}: {instance.thoughts_count} thoughts, "
                      f"{instance.embeddings_count} embeddings, "
                      f"{instance.missing_embeddings} missing")
            
            return federation_instances
            
        except Exception as e:
            print(f"Error discovering federation instances: {e}")
            return []
    
    def _get_instance_stats(self, instance: str) -> Optional[FederationInstance]:
        """Get detailed statistics for a specific instance"""
        try:
            # Count thoughts
            thought_pattern = f"{instance}:Thoughts:*"
            thought_keys = self.redis.keys(thought_pattern)
            thoughts_count = len(thought_keys)
            
            # Count embeddings (both JSON and binary formats)
            embedding_pattern = f"{instance}:embeddings:*"
            embedding_keys = self.redis.keys(embedding_pattern)
            
            # Filter out metadata and binary keys to avoid double counting
            actual_embedding_keys = []
            for key in embedding_keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                if ':meta:' not in key_str and ':binary:' not in key_str:
                    actual_embedding_keys.append(key_str)
            
            embeddings_count = len(actual_embedding_keys)
            
            # Calculate missing embeddings
            embedded_thought_ids = set()
            for key in actual_embedding_keys:
                thought_id = key.split(':')[-1]
                embedded_thought_ids.add(thought_id)
            
            # Check for binary embeddings too
            binary_pattern = f"{instance}:embeddings:binary:*"
            binary_keys = self.redis.keys(binary_pattern)
            for key in binary_keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                thought_id = key_str.split(':')[-1]
                embedded_thought_ids.add(thought_id)
            
            # Count thoughts without embeddings
            missing_count = 0
            for thought_key in thought_keys:
                key_str = thought_key.decode('utf-8') if isinstance(thought_key, bytes) else thought_key
                thought_id = key_str.split(':')[-1]
                if thought_id not in embedded_thought_ids:
                    missing_count += 1
            
            # Get last activity (most recent thought timestamp)
            last_activity = None
            if thought_keys:
                try:
                    # Sample a few recent thoughts to get activity
                    sample_keys = thought_keys[-3:] if len(thought_keys) >= 3 else thought_keys
                    latest_timestamp = 0
                    
                    for key in sample_keys:
                        thought_data_str = self.redis.get(key)
                        if thought_data_str:
                            thought_data = json.loads(thought_data_str)
                            timestamp_str = thought_data.get('timestamp', '')
                            if timestamp_str:
                                try:
                                    timestamp = int(datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp())
                                    latest_timestamp = max(latest_timestamp, timestamp)
                                except:
                                    pass
                    
                    if latest_timestamp > 0:
                        last_activity = datetime.fromtimestamp(latest_timestamp)
                        
                except Exception as e:
                    print(f"Error getting last activity for {instance}: {e}")
            
            return FederationInstance(
                name=instance,
                thoughts_count=thoughts_count,
                embeddings_count=len(embedded_thought_ids),  # Total unique embeddings
                missing_embeddings=missing_count,
                last_activity=last_activity
            )
            
        except Exception as e:
            print(f"Error getting stats for instance {instance}: {e}")
            return None
    
    def get_thoughts_without_embeddings(self, instance: str) -> List[Dict]:
        """Get all thoughts without embeddings for a specific instance"""
        try:
            # Get all thought keys for this instance
            thought_pattern = f"{instance}:Thoughts:*"
            thought_keys = self.redis.keys(thought_pattern)
            
            # Get all embedding keys (both formats)
            embedding_pattern = f"{instance}:embeddings:*"
            embedding_keys = self.redis.keys(embedding_pattern)
            binary_pattern = f"{instance}:embeddings:binary:*"
            binary_keys = self.redis.keys(binary_pattern)
            
            # Extract thought IDs that have embeddings
            embedded_thought_ids = set()
            
            # JSON embeddings
            for key in embedding_keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                if ':meta:' not in key_str and ':binary:' not in key_str:
                    thought_id = key_str.split(':')[-1]
                    embedded_thought_ids.add(thought_id)
            
            # Binary embeddings
            for key in binary_keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                thought_id = key_str.split(':')[-1]
                embedded_thought_ids.add(thought_id)
            
            # Find thoughts without embeddings
            missing_thoughts = []
            for thought_key in thought_keys:
                key_str = thought_key.decode('utf-8') if isinstance(thought_key, bytes) else thought_key
                thought_id = key_str.split(':')[-1]
                
                if thought_id not in embedded_thought_ids:
                    try:
                        # Try RedisJSON first, then fallback to regular string
                        try:
                            thought_data = self.redis.json().get(key_str)
                        except:
                            # Fallback to string get + JSON parse
                            thought_data_str = self.redis.get(key_str)
                            thought_data = json.loads(thought_data_str) if thought_data_str else None
                        
                        if thought_data and 'thought' in thought_data:
                                # Convert ISO timestamp to epoch seconds
                                timestamp_str = thought_data.get('timestamp', '')
                                try:
                                    if timestamp_str:
                                        timestamp = int(datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp())
                                    else:
                                        timestamp = int(time.time())
                                except ValueError:
                                    timestamp = int(time.time())
                                
                                missing_thoughts.append({
                                    'instance': instance,
                                    'key': key_str,
                                    'thought_id': thought_id,
                                    'content': thought_data['thought'],
                                    'timestamp': timestamp
                                })
                    except Exception as e:
                        print(f"Error reading thought {key_str}: {e}")
                        continue
            
            return missing_thoughts
            
        except Exception as e:
            print(f"Error finding missing embeddings for {instance}: {e}")
            return []
    
    def get_federation_summary(self) -> Dict:
        """Get a summary of the entire federation"""
        try:
            instances = self.discover_federation_instances()
            
            total_thoughts = sum(i.thoughts_count for i in instances)
            total_embeddings = sum(i.embeddings_count for i in instances)
            total_missing = sum(i.missing_embeddings for i in instances)
            
            coverage_percentage = (total_embeddings / total_thoughts * 100) if total_thoughts > 0 else 0
            
            return {
                'federation_summary': {
                    'total_instances': len(instances),
                    'total_thoughts': total_thoughts,
                    'total_embeddings': total_embeddings,
                    'total_missing': total_missing,
                    'coverage_percentage': round(coverage_percentage, 2)
                },
                'instances': [
                    {
                        'name': i.name,
                        'thoughts': i.thoughts_count,
                        'embeddings': i.embeddings_count,
                        'missing': i.missing_embeddings,
                        'coverage': round((i.embeddings_count / i.thoughts_count * 100) if i.thoughts_count > 0 else 0, 2),
                        'last_activity': i.last_activity.isoformat() if i.last_activity else None
                    }
                    for i in instances
                ],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def monitor_new_instances(self) -> List[str]:
        """Monitor for new federation instances that weren't previously known"""
        try:
            current_instances = {i.name for i in self.discover_federation_instances()}
            new_instances = current_instances - self.known_instances
            
            if new_instances:
                print(f"Discovered new federation instances: {list(new_instances)}")
                
            return list(new_instances)
            
        except Exception as e:
            print(f"Error monitoring new instances: {e}")
            return []


def main():
    """CLI interface for federation auto-discovery"""
    import sys
    import os
    
    if len(sys.argv) < 2:
        print("Usage: python3 federation_auto_discovery.py <command>")
        print("Commands:")
        print("  discover                     - Discover all federation instances")
        print("  summary                      - Get federation summary")
        print("  missing <instance>           - List missing embeddings for instance")
        print("  monitor                      - Monitor for new instances")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Setup Redis connection
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    redis_client = redis.from_url(redis_url)
    
    discovery = FederationAutoDiscovery(redis_client)
    
    if command == "discover":
        instances = discovery.discover_federation_instances()
        print(f"\nDiscovered {len(instances)} federation instances:")
        for instance in instances:
            print(f"  {instance.name}: {instance.thoughts_count} thoughts, "
                  f"{instance.embeddings_count} embeddings, "
                  f"{instance.missing_embeddings} missing")
    
    elif command == "summary":
        summary = discovery.get_federation_summary()
        print(json.dumps(summary, indent=2))
    
    elif command == "missing":
        if len(sys.argv) < 3:
            print("Usage: missing <instance_name>")
            sys.exit(1)
        
        instance = sys.argv[2]
        missing = discovery.get_thoughts_without_embeddings(instance)
        print(f"Found {len(missing)} thoughts without embeddings for {instance}:")
        for thought in missing[:10]:  # Show first 10
            content_preview = thought['content'][:100] + "..." if len(thought['content']) > 100 else thought['content']
            print(f"  {thought['thought_id']}: {content_preview}")
        
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
    
    elif command == "monitor":
        print("Monitoring for new federation instances...")
        discovery.discover_federation_instances()  # Initial discovery
        
        while True:
            new_instances = discovery.monitor_new_instances()
            if new_instances:
                print(f"New instances detected: {new_instances}")
            time.sleep(30)  # Check every 30 seconds
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
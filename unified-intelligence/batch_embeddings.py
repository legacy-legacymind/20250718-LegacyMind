#!/usr/bin/env python3
"""
Batch embedding generator for unified-intelligence
Finds all thoughts without embeddings and generates them in batches.
"""

import sys
import json
import os
import time
import redis
from datetime import datetime
from simple_embeddings import SimpleEmbeddingService


class BatchEmbeddingProcessor:
    def __init__(self, redis_url: str, openai_api_key: str, instance: str = "Claude"):
        """Initialize the batch embedding processor"""
        self.redis_client = redis.from_url(redis_url)
        self.embedding_service = SimpleEmbeddingService(redis_url, openai_api_key, instance)
        self.instance = instance
        
    def get_thoughts_without_embeddings(self) -> list:
        """Find all thoughts that don't have embeddings"""
        try:
            # Get all thought keys
            thought_pattern = f"{self.instance}:Thoughts:*"
            thought_keys = self.redis_client.keys(thought_pattern)
            
            # Get all embedding keys
            embedding_pattern = f"{self.instance}:embeddings:*"
            embedding_keys = self.redis_client.keys(embedding_pattern)
            
            # Extract thought IDs that have embeddings
            embedded_thought_ids = set()
            for key in embedding_keys:
                # Extract thought_id from embedding key
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                thought_id = key_str.split(':')[-1]  # Get the UUID part
                embedded_thought_ids.add(thought_id)
            
            # Find thoughts without embeddings
            missing_embeddings = []
            for thought_key in thought_keys:
                key_str = thought_key.decode('utf-8') if isinstance(thought_key, bytes) else thought_key
                thought_id = key_str.split(':')[-1]  # Get the UUID part
                
                if thought_id not in embedded_thought_ids:
                    # Get the thought data (stored as JSON string, not Redis JSON)
                    try:
                        thought_data_str = self.redis_client.get(key_str)
                        if thought_data_str:
                            thought_data = json.loads(thought_data_str)
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
                                
                                missing_embeddings.append({
                                    'key': key_str,
                                    'thought_id': thought_id,
                                    'content': thought_data['thought'],
                                    'timestamp': timestamp
                                })
                    except Exception as e:
                        print(f"Error reading thought {key_str}: {e}", file=sys.stderr)
                        continue
            
            return missing_embeddings
            
        except Exception as e:
            print(f"Error finding thoughts without embeddings: {e}", file=sys.stderr)
            return []
    
    def process_batch(self, thoughts: list, batch_size: int = 10, delay: float = 0.1) -> dict:
        """Process thoughts in batches with rate limiting"""
        results = {
            'total': len(thoughts),
            'processed': 0,
            'errors': 0,
            'success': 0
        }
        
        print(f"Processing {len(thoughts)} thoughts in batches of {batch_size}")
        
        for i in range(0, len(thoughts), batch_size):
            batch = thoughts[i:i + batch_size]
            print(f"Processing batch {i//batch_size + 1}: thoughts {i+1}-{min(i+batch_size, len(thoughts))}")
            
            for thought in batch:
                try:
                    success = self.embedding_service.store_thought_embedding(
                        thought['thought_id'],
                        thought['content'],
                        thought['timestamp']
                    )
                    
                    if success:
                        results['success'] += 1
                        print(f"✓ Generated embedding for thought {thought['thought_id']}")
                    else:
                        results['errors'] += 1
                        print(f"✗ Failed to generate embedding for thought {thought['thought_id']}")
                    
                    results['processed'] += 1
                    
                    # Rate limiting
                    time.sleep(delay)
                    
                except Exception as e:
                    results['errors'] += 1
                    results['processed'] += 1
                    print(f"✗ Error processing thought {thought['thought_id']}: {e}", file=sys.stderr)
            
            # Longer delay between batches
            if i + batch_size < len(thoughts):
                print(f"Batch complete. Waiting {delay * 10}s before next batch...")
                time.sleep(delay * 10)
        
        return results
    
    def analyze_current_state(self) -> dict:
        """Analyze the current state of thoughts and embeddings"""
        try:
            # Count thoughts
            thought_pattern = f"{self.instance}:Thoughts:*"
            thought_count = len(self.redis_client.keys(thought_pattern))
            
            # Count embeddings
            embedding_pattern = f"{self.instance}:embeddings:*"
            embedding_count = len(self.redis_client.keys(embedding_pattern))
            
            # Find missing embeddings
            missing = self.get_thoughts_without_embeddings()
            
            return {
                'total_thoughts': thought_count,
                'total_embeddings': embedding_count,
                'missing_embeddings': len(missing),
                'coverage_percentage': (embedding_count / thought_count * 100) if thought_count > 0 else 0
            }
            
        except Exception as e:
            print(f"Error analyzing current state: {e}", file=sys.stderr)
            return {}


def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: python3 batch_embeddings.py <command> [args...]", file=sys.stderr)
        print("Commands:", file=sys.stderr)
        print("  analyze                     - Show current state", file=sys.stderr)
        print("  process [batch_size] [delay] - Process all missing embeddings", file=sys.stderr)
        print("  list                        - List thoughts without embeddings", file=sys.stderr)
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Get configuration
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    instance = os.getenv('INSTANCE_ID', 'Claude')
    
    # Get API key from environment or Redis
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        try:
            temp_redis = redis.from_url(redis_url)
            openai_api_key = temp_redis.get('config:openai_api_key')
            if openai_api_key:
                openai_api_key = openai_api_key.decode('utf-8') if isinstance(openai_api_key, bytes) else openai_api_key
        except Exception as e:
            print(f"Error retrieving API key from Redis: {e}", file=sys.stderr)
    
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not found in environment or Redis", file=sys.stderr)
        sys.exit(1)
    
    processor = BatchEmbeddingProcessor(redis_url, openai_api_key, instance)
    
    if command == "analyze":
        state = processor.analyze_current_state()
        print(json.dumps(state, indent=2))
    
    elif command == "process":
        batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        delay = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
        
        missing = processor.get_thoughts_without_embeddings()
        if not missing:
            print("No thoughts found that are missing embeddings.")
            sys.exit(0)
        
        print(f"Found {len(missing)} thoughts without embeddings")
        print(f"Batch size: {batch_size}, Delay: {delay}s")
        
        # Confirm before processing
        response = input("Proceed with batch processing? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            sys.exit(0)
        
        results = processor.process_batch(missing, batch_size, delay)
        print("\nBatch processing complete:")
        print(json.dumps(results, indent=2))
    
    elif command == "list":
        missing = processor.get_thoughts_without_embeddings()
        print(f"Found {len(missing)} thoughts without embeddings:")
        for thought in missing[:10]:  # Show first 10
            content_preview = thought['content'][:100] + "..." if len(thought['content']) > 100 else thought['content']
            print(f"  {thought['thought_id']}: {content_preview}")
        
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
    
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
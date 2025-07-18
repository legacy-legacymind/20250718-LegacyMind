#!/usr/bin/env python3
"""
Enhanced Embedding Service with Binary Storage Support
Integrates Phase 1B binary vector storage with existing embedding functionality.
Provides 75% memory reduction while maintaining backward compatibility.
"""

import sys
import json
import os
import redis
import numpy as np
import re
import time
from typing import List, Dict, Optional, Tuple, Union
from openai import OpenAI

# Add the current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from binary_vector_storage import BinaryVectorStorage


class EnhancedEmbeddingService:
    """
    Enhanced embedding service with binary storage support.
    
    Features:
    - Binary storage for 75% memory reduction
    - Backward compatibility with JSON embeddings
    - Hybrid search supporting both storage formats
    - Migration utilities for existing embeddings
    - Performance optimizations
    """
    
    def __init__(
        self,
        redis_url: str,
        openai_api_key: str,
        instance: str,
        use_binary_storage: bool = True,
        auto_migrate: bool = False
    ):
        """
        Initialize the enhanced embedding service.
        
        Args:
            redis_url: Redis connection URL
            openai_api_key: OpenAI API key
            instance: Federation instance name
            use_binary_storage: Whether to use binary storage for new embeddings
            auto_migrate: Whether to automatically migrate JSON embeddings to binary
        """
        self.redis_client = redis.from_url(redis_url)
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.instance = instance
        self.use_binary_storage = use_binary_storage
        self.auto_migrate = auto_migrate
        
        # Initialize binary storage
        self.binary_storage = BinaryVectorStorage(self.redis_client, instance)
        
        # Performance counters
        self.stats = {
            'embeddings_generated': 0,
            'binary_stored': 0,
            'json_stored': 0,
            'migrations_performed': 0,
            'memory_saved_bytes': 0
        }
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and normalize text before embedding generation"""
        if not text:
            return ""
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        # Remove excessive punctuation
        text = re.sub(r'[.]{2,}', '.', text)
        text = re.sub(r'[!]{2,}', '!', text)
        text = re.sub(r'[?]{2,}', '?', text)
        
        return text
    
    def generate_embedding(self, text: str, model: str = "text-embedding-3-small") -> Optional[List[float]]:
        """Generate embedding using OpenAI with performance tracking"""
        try:
            # Preprocess text before sending to API
            processed_text = self._preprocess_text(text)
            
            start_time = time.time()
            response = self.openai_client.embeddings.create(
                model=model,
                input=processed_text
            )
            generation_time = time.time() - start_time
            
            embedding = response.data[0].embedding
            self.stats['embeddings_generated'] += 1
            
            print(f"Generated embedding in {generation_time:.3f}s for text length {len(processed_text)}")
            return embedding
            
        except Exception as e:
            print(f"Error generating embedding: {e}", file=sys.stderr)
            return None
    
    def store_thought_embedding(
        self,
        thought_id: str,
        content: str,
        timestamp: int,
        model: str = "text-embedding-3-small",
        force_binary: Optional[bool] = None
    ) -> bool:
        """
        Store thought with embedding using optimal storage format.
        
        Args:
            thought_id: Unique identifier for the thought
            content: Text content to embed
            timestamp: Unix timestamp
            model: OpenAI model to use
            force_binary: Force binary storage (overrides instance setting)
            
        Returns:
            True if storage successful, False otherwise
        """
        try:
            # Generate embedding
            embedding = self.generate_embedding(content, model)
            if embedding is None:
                return False
            
            # Determine storage format
            use_binary = force_binary if force_binary is not None else self.use_binary_storage
            
            if use_binary:
                # Store in binary format (Phase 1B optimization)
                metadata = {
                    'content': content,
                    'timestamp': timestamp,
                    'provider': 'openai',
                    'model': model,
                    'enhanced_service': True
                }
                
                success = self.binary_storage.store_embedding_binary(
                    thought_id, embedding, metadata, model
                )
                
                if success:
                    self.stats['binary_stored'] += 1
                    # Estimate memory savings (JSON ~4KB vs binary ~1KB)
                    self.stats['memory_saved_bytes'] += 3072  # Approximate 75% savings
                    
                    # Also store in sorted set for quick retrieval
                    set_key = f"{self.instance}:embedding_index"
                    self.redis_client.zadd(set_key, {thought_id: timestamp})
                    
                    print(f"✓ Stored embedding for {thought_id} in binary format (75% memory savings)")
                
                return success
            
            else:
                # Store in legacy JSON format
                embedding_data = {
                    "thought_id": thought_id,
                    "content": content,
                    "embedding": embedding,
                    "timestamp": timestamp,
                    "instance": self.instance,
                    "provider": "openai",
                    "model": model,
                    "enhanced_service": True
                }
                
                # Store in Redis
                key = f"{self.instance}:embeddings:{thought_id}"
                self.redis_client.set(key, json.dumps(embedding_data))
                
                # Also store in sorted set for quick retrieval
                set_key = f"{self.instance}:embedding_index"
                self.redis_client.zadd(set_key, {thought_id: timestamp})
                
                self.stats['json_stored'] += 1
                print(f"✓ Stored embedding for {thought_id} in JSON format")
                return True
            
        except Exception as e:
            print(f"Error storing thought embedding: {e}", file=sys.stderr)
            return False
    
    def retrieve_embedding(self, thought_id: str) -> Optional[Tuple[np.ndarray, Dict]]:
        """
        Retrieve embedding from either binary or JSON storage.
        
        Args:
            thought_id: Unique identifier for the thought
            
        Returns:
            Tuple of (embedding_array, metadata) or None if not found
        """
        try:
            # Try binary storage first (more efficient)
            result = self.binary_storage.retrieve_embedding_binary(thought_id)
            if result:
                embedding, metadata = result
                return embedding, metadata
            
            # Fall back to JSON storage
            json_key = f"{self.instance}:embeddings:{thought_id}"
            json_data = self.redis_client.get(json_key)
            
            if json_data:
                data = json.loads(json_data)
                embedding = np.array(data['embedding'], dtype=np.float32)
                metadata = {
                    'thought_id': data.get('thought_id'),
                    'content': data.get('content'),
                    'timestamp': data.get('timestamp'),
                    'model': data.get('model'),
                    'provider': data.get('provider'),
                    'storage_format': 'json',
                    'instance': data.get('instance')
                }
                
                # Auto-migrate if enabled
                if self.auto_migrate:
                    print(f"Auto-migrating {thought_id} to binary storage...")
                    self.binary_storage.migrate_existing_embedding(thought_id)
                    self.stats['migrations_performed'] += 1
                
                return embedding, metadata
            
            return None
            
        except Exception as e:
            print(f"Error retrieving embedding for {thought_id}: {e}")
            return None
    
    def semantic_search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.5,
        search_both_formats: bool = True
    ) -> List[Dict]:
        """
        Perform semantic search across both binary and JSON embeddings.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            search_both_formats: Whether to search both binary and JSON formats
            
        Returns:
            List of search results with similarity scores
        """
        try:
            query_embedding = self.generate_embedding(query)
            if query_embedding is None:
                return []
            
            query_vector = np.array(query_embedding, dtype=np.float32)
            similarities = []
            
            # Search binary embeddings
            if search_both_formats:
                binary_pattern = f"{self.instance}:embeddings:binary:*"
                binary_keys = self.redis_client.keys(binary_pattern)
                
                for key in binary_keys:
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    thought_id = key_str.split(':')[-1]
                    
                    result = self.binary_storage.retrieve_embedding_binary(thought_id)
                    if result:
                        stored_embedding, metadata = result
                        similarity = self._cosine_similarity(query_vector, stored_embedding)
                        
                        if similarity >= threshold:
                            similarities.append({
                                "thought_id": thought_id,
                                "content": metadata.get('content', ''),
                                "timestamp": metadata.get('timestamp', 0),
                                "similarity": float(similarity),
                                "storage_format": "binary",
                                "model": metadata.get('model', 'unknown')
                            })
            
            # Search JSON embeddings (for backward compatibility)
            json_pattern = f"{self.instance}:embeddings:*"
            json_keys = self.redis_client.keys(json_pattern)
            
            for key in json_keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                
                # Skip binary and metadata keys
                if ':binary:' in key_str or ':meta:' in key_str:
                    continue
                
                try:
                    data_str = self.redis_client.get(key)
                    if data_str:
                        data = json.loads(data_str)
                        stored_embedding = np.array(data["embedding"], dtype=np.float32)
                        
                        similarity = self._cosine_similarity(query_vector, stored_embedding)
                        
                        if similarity >= threshold:
                            similarities.append({
                                "thought_id": data["thought_id"],
                                "content": data["content"],
                                "timestamp": data["timestamp"],
                                "similarity": float(similarity),
                                "storage_format": "json",
                                "model": data.get("model", "unknown")
                            })
                except Exception as e:
                    print(f"Error processing JSON key {key_str}: {e}")
                    continue
            
            # Remove duplicates (prefer binary format)
            seen_thoughts = set()
            deduplicated = []
            
            # Sort by similarity first, then prefer binary format
            similarities.sort(key=lambda x: (-x["similarity"], x["storage_format"] == "json"))
            
            for result in similarities:
                thought_id = result["thought_id"]
                if thought_id not in seen_thoughts:
                    seen_thoughts.add(thought_id)
                    deduplicated.append(result)
            
            # Sort by similarity and return top results
            deduplicated.sort(key=lambda x: x["similarity"], reverse=True)
            print(f"Found {len(deduplicated)} results above threshold {threshold}")
            
            return deduplicated[:limit]
            
        except Exception as e:
            print(f"Error in semantic search: {e}", file=sys.stderr)
            return []
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.
        OpenAI embeddings are pre-normalized, so we can use simple dot product.
        """
        try:
            # Ensure both are numpy arrays
            if not isinstance(a, np.ndarray):
                a = np.array(a, dtype=np.float32)
            if not isinstance(b, np.ndarray):
                b = np.array(b, dtype=np.float32)
            
            # OpenAI embeddings are pre-normalized, so dot product is sufficient
            return float(np.dot(a, b))
        except Exception:
            return 0.0
    
    def get_service_stats(self) -> Dict:
        """Get performance and usage statistics"""
        try:
            # Get storage statistics
            storage_stats = self.binary_storage.get_storage_stats()
            
            # Combine with service stats
            combined_stats = {
                'service_stats': self.stats.copy(),
                'storage_stats': storage_stats,
                'configuration': {
                    'instance': self.instance,
                    'use_binary_storage': self.use_binary_storage,
                    'auto_migrate': self.auto_migrate
                },
                'timestamp': time.time()
            }
            
            return combined_stats
            
        except Exception as e:
            return {'error': str(e)}
    
    def migrate_all_embeddings(self, batch_size: int = 100) -> Dict:
        """Migrate all JSON embeddings to binary format"""
        try:
            print("Starting migration of all embeddings to binary format...")
            stats = self.binary_storage.batch_migrate_embeddings(batch_size)
            self.stats['migrations_performed'] += stats.get('migrated', 0)
            return stats
        except Exception as e:
            return {'error': str(e)}
    
    def optimize_storage(self) -> Dict:
        """Run storage optimization including migration and cleanup"""
        try:
            optimization_results = {
                'migration_stats': {},
                'cleanup_stats': {},
                'final_stats': {}
            }
            
            # Migrate JSON embeddings to binary
            if self.use_binary_storage:
                print("Step 1: Migrating JSON embeddings to binary format...")
                migration_stats = self.migrate_all_embeddings()
                optimization_results['migration_stats'] = migration_stats
            
            # Get final statistics
            final_stats = self.get_service_stats()
            optimization_results['final_stats'] = final_stats
            
            # Calculate total memory saved
            migrated = optimization_results['migration_stats'].get('migrated', 0)
            memory_saved_mb = (migrated * 3072) / (1024 * 1024)  # 3KB per embedding saved
            
            optimization_results['summary'] = {
                'embeddings_migrated': migrated,
                'estimated_memory_saved_mb': round(memory_saved_mb, 2),
                'storage_format': 'binary' if self.use_binary_storage else 'json'
            }
            
            return optimization_results
            
        except Exception as e:
            return {'error': str(e)}


def main():
    """CLI interface for enhanced embedding service"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Embedding Service with Binary Storage')
    parser.add_argument('command', choices=['store', 'search', 'stats', 'migrate', 'optimize', 'test'])
    parser.add_argument('--instance', default=None, help='Federation instance name')
    parser.add_argument('--binary', action='store_true', help='Use binary storage')
    parser.add_argument('--auto-migrate', action='store_true', help='Auto-migrate JSON to binary')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for operations')
    
    # Command-specific arguments
    parser.add_argument('--thought-id', help='Thought ID for store command')
    parser.add_argument('--content', help='Content for store command')
    parser.add_argument('--timestamp', type=int, help='Timestamp for store command')
    parser.add_argument('--query', help='Query for search command')
    parser.add_argument('--limit', type=int, default=10, help='Limit for search command')
    parser.add_argument('--threshold', type=float, default=0.5, help='Threshold for search command')
    
    args = parser.parse_args()
    
    # Get configuration
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    instance = args.instance or os.getenv('INSTANCE_ID', 'Claude')
    
    # Get OpenAI API key
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        try:
            temp_redis = redis.from_url(redis_url)
            openai_api_key = temp_redis.get('config:openai_api_key')
            if openai_api_key:
                openai_api_key = openai_api_key.decode('utf-8') if isinstance(openai_api_key, bytes) else openai_api_key
        except Exception:
            pass
    
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not found", file=sys.stderr)
        sys.exit(1)
    
    # Initialize service
    service = EnhancedEmbeddingService(
        redis_url=redis_url,
        openai_api_key=openai_api_key,
        instance=instance,
        use_binary_storage=args.binary,
        auto_migrate=args.auto_migrate
    )
    
    # Execute command
    if args.command == 'store':
        if not all([args.thought_id, args.content, args.timestamp]):
            print("Error: store requires --thought-id, --content, and --timestamp")
            sys.exit(1)
        
        success = service.store_thought_embedding(args.thought_id, args.content, args.timestamp)
        print(json.dumps({"success": success}))
    
    elif args.command == 'search':
        if not args.query:
            print("Error: search requires --query")
            sys.exit(1)
        
        results = service.semantic_search(args.query, args.limit, args.threshold)
        print(json.dumps({"results": results}, indent=2))
    
    elif args.command == 'stats':
        stats = service.get_service_stats()
        print(json.dumps(stats, indent=2))
    
    elif args.command == 'migrate':
        stats = service.migrate_all_embeddings(args.batch_size)
        print(json.dumps(stats, indent=2))
    
    elif args.command == 'optimize':
        results = service.optimize_storage()
        print(json.dumps(results, indent=2))
    
    elif args.command == 'test':
        # Run comprehensive test
        test_id = f"test_{int(time.time())}"
        test_content = "This is a test embedding for the enhanced service with binary storage optimization."
        
        print("Testing enhanced embedding service...")
        
        # Test storage
        success = service.store_thought_embedding(test_id, test_content, int(time.time()))
        print(f"Storage test: {'✓' if success else '✗'}")
        
        # Test retrieval
        result = service.retrieve_embedding(test_id)
        print(f"Retrieval test: {'✓' if result else '✗'}")
        
        # Test search
        search_results = service.semantic_search("test embedding", limit=5)
        print(f"Search test: {'✓' if search_results else '✗'}")
        
        # Get stats
        stats = service.get_service_stats()
        print("Service statistics:")
        print(json.dumps(stats, indent=2))
        
        # Cleanup
        if args.binary:
            service.redis_client.delete(f"{instance}:embeddings:binary:{test_id}")
            service.redis_client.delete(f"{instance}:embeddings:meta:{test_id}")
        else:
            service.redis_client.delete(f"{instance}:embeddings:{test_id}")
        
        print("Test cleanup complete")


if __name__ == "__main__":
    main()
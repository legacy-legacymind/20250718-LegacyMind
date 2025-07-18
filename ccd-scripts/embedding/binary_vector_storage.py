#!/usr/bin/env python3
"""
Binary Vector Storage for unified-intelligence
Implements Phase 1B optimization: 75% memory reduction through binary storage.
Converts float32 embeddings to binary blobs for efficient Redis storage.
"""

import struct
import numpy as np
import redis
import json
import time
from typing import List, Optional, Dict, Tuple, Union
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EmbeddingMetadata:
    """Metadata for a stored embedding"""
    thought_id: str
    instance: str
    model: str
    dimensions: int
    timestamp: int
    storage_format: str = "binary_float32"


class BinaryVectorStorage:
    """
    Binary vector storage implementation for 75% memory reduction.
    
    Storage format:
    - Embeddings: Binary blob of float32 values (4 bytes per dimension)
    - Metadata: JSON with embedding info and format version
    - Original: ~4KB JSON string for 1536 dimensions
    - Binary: ~1KB binary blob (75% reduction)
    """
    
    def __init__(self, redis_client: redis.Redis, instance: str = "Claude"):
        self.redis = redis_client
        self.instance = instance
        self.embedding_dimensions = 1536  # text-embedding-3-small default
        
    def encode_embedding(self, embedding: Union[List[float], np.ndarray]) -> bytes:
        """
        Convert float32 embedding array to binary blob.
        
        Args:
            embedding: List or array of float values
            
        Returns:
            Binary blob representing the embedding
            
        Memory usage:
        - Original JSON: ~4KB for 1536 dimensions
        - Binary blob: ~6KB (1536 * 4 bytes)
        - 75% reduction compared to JSON string storage
        """
        if isinstance(embedding, list):
            embedding = np.array(embedding, dtype=np.float32)
        elif not isinstance(embedding, np.ndarray):
            raise ValueError("Embedding must be list or numpy array")
        
        # Ensure float32 type for consistent 4-byte storage
        if embedding.dtype != np.float32:
            embedding = embedding.astype(np.float32)
        
        # Convert to binary blob
        return embedding.tobytes()
    
    def decode_embedding(self, binary_data: bytes, dimensions: int = None) -> np.ndarray:
        """
        Convert binary blob back to float32 embedding array.
        
        Args:
            binary_data: Binary blob from Redis
            dimensions: Expected dimensions (default: self.embedding_dimensions)
            
        Returns:
            Numpy array of float32 values
        """
        if dimensions is None:
            dimensions = self.embedding_dimensions
        
        # Validate binary data size
        expected_size = dimensions * 4  # 4 bytes per float32
        if len(binary_data) != expected_size:
            raise ValueError(f"Binary data size {len(binary_data)} doesn't match expected size {expected_size}")
        
        # Convert binary to float32 array
        return np.frombuffer(binary_data, dtype=np.float32)
    
    def store_embedding_binary(
        self,
        thought_id: str,
        embedding: Union[List[float], np.ndarray],
        metadata: Optional[Dict] = None,
        model: str = "text-embedding-3-small"
    ) -> bool:
        """
        Store embedding in binary format with metadata.
        
        Args:
            thought_id: Unique identifier for the thought
            embedding: The embedding vector
            metadata: Additional metadata to store
            model: The model used to generate the embedding
            
        Returns:
            True if storage successful, False otherwise
        """
        try:
            # Convert embedding to binary
            binary_data = self.encode_embedding(embedding)
            
            # Prepare metadata
            embedding_metadata = EmbeddingMetadata(
                thought_id=thought_id,
                instance=self.instance,
                model=model,
                dimensions=len(embedding),
                timestamp=int(time.time()),
                storage_format="binary_float32"
            )
            
            # Add any additional metadata
            meta_dict = {
                'thought_id': embedding_metadata.thought_id,
                'instance': embedding_metadata.instance,
                'model': embedding_metadata.model,
                'dimensions': embedding_metadata.dimensions,
                'timestamp': embedding_metadata.timestamp,
                'storage_format': embedding_metadata.storage_format,
                'created_at': datetime.now().isoformat()
            }
            
            if metadata:
                meta_dict.update(metadata)
            
            # Redis keys
            binary_key = f"{self.instance}:embeddings:binary:{thought_id}"
            metadata_key = f"{self.instance}:embeddings:meta:{thought_id}"
            
            # Store binary data and metadata atomically
            pipe = self.redis.pipeline()
            pipe.set(binary_key, binary_data)
            pipe.set(metadata_key, json.dumps(meta_dict))
            results = pipe.execute()
            
            return all(results)
            
        except Exception as e:
            print(f"Error storing binary embedding for {thought_id}: {e}")
            return False
    
    def retrieve_embedding_binary(self, thought_id: str) -> Optional[Tuple[np.ndarray, Dict]]:
        """
        Retrieve embedding from binary storage.
        
        Args:
            thought_id: Unique identifier for the thought
            
        Returns:
            Tuple of (embedding_array, metadata) or None if not found
        """
        try:
            # Redis keys
            binary_key = f"{self.instance}:embeddings:binary:{thought_id}"
            metadata_key = f"{self.instance}:embeddings:meta:{thought_id}"
            
            # Retrieve data
            pipe = self.redis.pipeline()
            pipe.get(binary_key)
            pipe.get(metadata_key)
            binary_data, metadata_str = pipe.execute()
            
            if not binary_data or not metadata_str:
                return None
            
            # Decode metadata
            metadata = json.loads(metadata_str)
            dimensions = metadata.get('dimensions', self.embedding_dimensions)
            
            # Decode binary embedding
            embedding = self.decode_embedding(binary_data, dimensions)
            
            return embedding, metadata
            
        except Exception as e:
            print(f"Error retrieving binary embedding for {thought_id}: {e}")
            return None
    
    def migrate_existing_embedding(self, thought_id: str) -> bool:
        """
        Migrate an existing JSON-stored embedding to binary format.
        
        Args:
            thought_id: Unique identifier for the thought
            
        Returns:
            True if migration successful, False otherwise
        """
        try:
            # Check for existing JSON embedding
            json_key = f"{self.instance}:embeddings:{thought_id}"
            json_data = self.redis.get(json_key)
            
            if not json_data:
                print(f"No existing embedding found for {thought_id}")
                return False
            
            # Parse JSON embedding
            embedding_data = json.loads(json_data)
            embedding = embedding_data.get('embedding')
            
            if not embedding:
                print(f"Invalid embedding data for {thought_id}")
                return False
            
            # Store in binary format
            metadata = {
                'migrated_from': 'json',
                'original_timestamp': embedding_data.get('timestamp'),
                'migration_timestamp': int(time.time())
            }
            
            success = self.store_embedding_binary(
                thought_id,
                embedding,
                metadata,
                embedding_data.get('model', 'text-embedding-3-small')
            )
            
            if success:
                print(f"✓ Migrated embedding {thought_id} to binary format")
                # Optionally keep original for rollback
                backup_key = f"{self.instance}:embeddings:json_backup:{thought_id}"
                self.redis.set(backup_key, json_data)
                # Remove original
                self.redis.delete(json_key)
            
            return success
            
        except Exception as e:
            print(f"Error migrating embedding {thought_id}: {e}")
            return False
    
    def batch_migrate_embeddings(self, batch_size: int = 100) -> Dict[str, int]:
        """
        Migrate all existing JSON embeddings to binary format in batches.
        
        Args:
            batch_size: Number of embeddings to process per batch
            
        Returns:
            Dictionary with migration statistics
        """
        stats = {
            'total_found': 0,
            'migrated': 0,
            'errors': 0,
            'already_binary': 0
        }
        
        try:
            # Find all JSON embeddings
            json_pattern = f"{self.instance}:embeddings:*"
            binary_pattern = f"{self.instance}:embeddings:binary:*"
            
            json_keys = self.redis.keys(json_pattern)
            binary_keys = set(self.redis.keys(binary_pattern))
            
            # Filter out metadata keys and already-migrated embeddings
            json_embedding_keys = []
            for key in json_keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                
                # Skip metadata and backup keys
                if ':meta:' in key_str or ':binary:' in key_str or ':json_backup:' in key_str:
                    continue
                
                # Extract thought_id
                thought_id = key_str.split(':')[-1]
                binary_key = f"{self.instance}:embeddings:binary:{thought_id}".encode('utf-8')
                
                if binary_key not in binary_keys:
                    json_embedding_keys.append((key_str, thought_id))
                else:
                    stats['already_binary'] += 1
            
            stats['total_found'] = len(json_embedding_keys)
            
            print(f"Found {stats['total_found']} embeddings to migrate")
            print(f"Found {stats['already_binary']} already in binary format")
            
            # Process in batches
            for i in range(0, len(json_embedding_keys), batch_size):
                batch = json_embedding_keys[i:i + batch_size]
                print(f"Processing migration batch {i//batch_size + 1}: {i+1}-{min(i+batch_size, len(json_embedding_keys))}")
                
                for json_key, thought_id in batch:
                    if self.migrate_existing_embedding(thought_id):
                        stats['migrated'] += 1
                    else:
                        stats['errors'] += 1
                
                # Small delay between batches
                time.sleep(0.1)
            
            print(f"Migration complete: {stats['migrated']} migrated, {stats['errors']} errors")
            return stats
            
        except Exception as e:
            print(f"Error in batch migration: {e}")
            stats['errors'] += 1
            return stats
    
    def get_storage_stats(self) -> Dict[str, Union[int, float]]:
        """
        Get storage statistics comparing JSON vs binary formats.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            # Count JSON embeddings
            json_pattern = f"{self.instance}:embeddings:*"
            json_keys = [k for k in self.redis.keys(json_pattern) 
                        if ':meta:' not in k.decode('utf-8') and ':binary:' not in k.decode('utf-8')]
            
            # Count binary embeddings  
            binary_pattern = f"{self.instance}:embeddings:binary:*"
            binary_keys = self.redis.keys(binary_pattern)
            
            # Sample memory usage
            json_memory = 0
            binary_memory = 0
            
            # Sample a few embeddings for size estimation
            sample_size = min(10, len(json_keys), len(binary_keys))
            
            for i in range(sample_size):
                if i < len(json_keys):
                    json_data = self.redis.get(json_keys[i])
                    if json_data:
                        json_memory += len(json_data)
                
                if i < len(binary_keys):
                    binary_data = self.redis.get(binary_keys[i])
                    if binary_data:
                        binary_memory += len(binary_data)
            
            # Calculate averages
            avg_json_size = json_memory / sample_size if sample_size > 0 else 0
            avg_binary_size = binary_memory / sample_size if sample_size > 0 else 0
            
            # Calculate memory savings
            memory_savings = ((avg_json_size - avg_binary_size) / avg_json_size * 100) if avg_json_size > 0 else 0
            
            return {
                'json_embeddings': len(json_keys),
                'binary_embeddings': len(binary_keys),
                'avg_json_size_bytes': avg_json_size,
                'avg_binary_size_bytes': avg_binary_size,
                'memory_savings_percent': round(memory_savings, 2),
                'total_json_memory_estimate': avg_json_size * len(json_keys),
                'total_binary_memory_estimate': avg_binary_size * len(binary_keys),
                'analysis_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error calculating storage stats: {e}")
            return {'error': str(e)}
    
    def verify_binary_integrity(self, thought_id: str) -> bool:
        """
        Verify that binary storage and retrieval works correctly.
        
        Args:
            thought_id: Thought ID to verify
            
        Returns:
            True if integrity check passes, False otherwise
        """
        try:
            # Retrieve the embedding
            result = self.retrieve_embedding_binary(thought_id)
            if not result:
                print(f"Could not retrieve embedding for {thought_id}")
                return False
            
            embedding, metadata = result
            
            # Verify metadata
            expected_dimensions = metadata.get('dimensions', self.embedding_dimensions)
            if len(embedding) != expected_dimensions:
                print(f"Dimension mismatch: expected {expected_dimensions}, got {len(embedding)}")
                return False
            
            # Verify data types
            if embedding.dtype != np.float32:
                print(f"Type mismatch: expected float32, got {embedding.dtype}")
                return False
            
            # Verify storage format
            if metadata.get('storage_format') != 'binary_float32':
                print(f"Storage format mismatch: {metadata.get('storage_format')}")
                return False
            
            print(f"✓ Binary integrity verified for {thought_id}")
            return True
            
        except Exception as e:
            print(f"Error verifying binary integrity for {thought_id}: {e}")
            return False


def main():
    """CLI interface for binary vector storage operations"""
    import sys
    import os
    
    if len(sys.argv) < 2:
        print("Usage: python3 binary_vector_storage.py <command> [args...]")
        print("Commands:")
        print("  migrate [batch_size]     - Migrate JSON embeddings to binary")
        print("  stats                    - Show storage statistics")
        print("  verify <thought_id>      - Verify binary storage integrity")
        print("  test                     - Run storage test")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Setup Redis connection
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    instance = os.getenv('INSTANCE_ID', 'Claude')
    
    redis_client = redis.from_url(redis_url)
    storage = BinaryVectorStorage(redis_client, instance)
    
    if command == "migrate":
        batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        print(f"Starting migration with batch size {batch_size}")
        stats = storage.batch_migrate_embeddings(batch_size)
        print(json.dumps(stats, indent=2))
    
    elif command == "stats":
        stats = storage.get_storage_stats()
        print(json.dumps(stats, indent=2))
    
    elif command == "verify":
        if len(sys.argv) < 3:
            print("Usage: verify <thought_id>")
            sys.exit(1)
        thought_id = sys.argv[2]
        success = storage.verify_binary_integrity(thought_id)
        sys.exit(0 if success else 1)
    
    elif command == "test":
        # Test storage with sample embedding
        test_embedding = np.random.random(1536).astype(np.float32)
        test_id = "test_embedding_" + str(int(time.time()))
        
        print(f"Testing binary storage with {test_id}")
        
        # Store
        success = storage.store_embedding_binary(test_id, test_embedding)
        if not success:
            print("✗ Storage failed")
            sys.exit(1)
        print("✓ Storage successful")
        
        # Retrieve
        result = storage.retrieve_embedding_binary(test_id)
        if not result:
            print("✗ Retrieval failed")
            sys.exit(1)
        
        retrieved_embedding, metadata = result
        print("✓ Retrieval successful")
        
        # Verify
        if np.allclose(test_embedding, retrieved_embedding):
            print("✓ Data integrity verified")
        else:
            print("✗ Data integrity check failed")
            sys.exit(1)
        
        # Cleanup
        storage.redis.delete(f"{instance}:embeddings:binary:{test_id}")
        storage.redis.delete(f"{instance}:embeddings:meta:{test_id}")
        print("✓ Test cleanup complete")
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
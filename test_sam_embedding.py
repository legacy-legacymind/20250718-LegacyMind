#!/usr/bin/env python3
"""
Test script to verify Sam's Redis keys and test embedding functionality
"""

import redis
import json
import sys
from qdrant_client import QdrantClient

def test_redis_connection():
    """Test Redis connection and check Sam's keys"""
    print("Testing Redis connection...")
    
    try:
        r = redis.Redis(
            host="127.0.0.1",
            port=6379,
            password="legacymind_redis_pass",
            decode_responses=True
        )
        
        # Test connection
        r.ping()
        print("✓ Redis connection successful")
        
        # Check Sam's keys
        sam_keys = {
            'Sam:Identity': 'Identity data',
            'Sam:Context:BrainDump': 'Brain dump context',
            'Sam:Context:Expectations': 'Expectations context'
        }
        
        print("\nChecking Sam's Redis keys:")
        for key, description in sam_keys.items():
            key_type = r.type(key)
            if key_type == 'none':
                print(f"✗ {key} - NOT FOUND")
            else:
                print(f"✓ {key} - {key_type} ({description})")
                
                # Show sample data
                if key_type == 'hash':
                    data = r.hgetall(key)
                    print(f"  Fields: {list(data.keys())[:5]}...")
                elif key_type == 'string':
                    data = r.get(key)
                    print(f"  Length: {len(data)} chars")
                elif key_type == 'ReJSON-RL':
                    try:
                        json_data = r.execute_command('JSON.GET', key, '.')
                        print(f"  JSON Length: {len(json_data)} chars")
                    except:
                        print(f"  Could not read JSON data")
        
        return True
        
    except Exception as e:
        print(f"✗ Redis connection failed: {e}")
        return False

def test_qdrant_connection():
    """Test Qdrant connection and check collections"""
    print("\nTesting Qdrant connection...")
    
    try:
        client = QdrantClient(host="localhost", port=6333)
        
        # Get collections
        collections = client.get_collections()
        print("✓ Qdrant connection successful")
        
        # Check for Sam's collections
        sam_collections = ['Sam_identity', 'Sam_context']
        existing_collections = [c.name for c in collections.collections]
        
        print("\nChecking Sam's Qdrant collections:")
        for collection in sam_collections:
            if collection in existing_collections:
                # Get collection info
                info = client.get_collection(collection)
                point_count = info.points_count
                print(f"✓ {collection} - EXISTS ({point_count} points)")
            else:
                print(f"✗ {collection} - NOT FOUND")
        
        return True
        
    except Exception as e:
        print(f"✗ Qdrant connection failed: {e}")
        return False

def create_test_data():
    """Create test data in Redis if Sam's keys don't exist"""
    print("\nCreating test data...")
    
    try:
        r = redis.Redis(
            host="127.0.0.1",
            port=6379,
            password="legacymind_redis_pass",
            decode_responses=True
        )
        
        # Check if keys exist
        if r.exists('Sam:Identity') == 0:
            # Create test identity data
            identity_data = {
                "name": "Sam",
                "role": "Human Operator",
                "federation_leader": "true",
                "instances": "CC, CCD, CCS, DT, CCB",
                "created_at": "2025-01-20"
            }
            r.hset('Sam:Identity', mapping=identity_data)
            print("✓ Created Sam:Identity test data")
        
        if r.exists('Sam:Context:BrainDump') == 0:
            # Create test brain dump
            brain_dump = {
                "current_project": "LegacyMind Federation",
                "focus_areas": "UnifiedIntelligence, embedding systems, federation coordination",
                "recent_thoughts": "Working on identity storage and embedding infrastructure",
                "timestamp": "2025-01-20T10:00:00"
            }
            r.set('Sam:Context:BrainDump', json.dumps(brain_dump))
            print("✓ Created Sam:Context:BrainDump test data")
        
        if r.exists('Sam:Context:Expectations') == 0:
            # Create test expectations
            expectations = {
                "short_term": "Complete identity embedding system",
                "long_term": "Full federation memory integration",
                "quality": "Robust, scalable, production-ready",
                "timeline": "Q1 2025"
            }
            r.set('Sam:Context:Expectations', json.dumps(expectations))
            print("✓ Created Sam:Context:Expectations test data")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to create test data: {e}")
        return False

def test_embedding_service():
    """Test the embedding service with a single run"""
    print("\nTesting embedding service...")
    
    try:
        from sam_embedding_service import SamEmbeddingService
        
        # Initialize service
        service = SamEmbeddingService(
            scan_interval=30,
            batch_size=50
        )
        
        # Setup collections
        service.setup_qdrant_collections()
        print("✓ Qdrant collections setup complete")
        
        # Run single scan
        print("\nRunning single embedding scan...")
        service.run_single_scan()
        
        # Check stats
        stats = service.stats
        print(f"\nEmbedding Stats:")
        print(f"  Items found: {stats.total_items_found}")
        print(f"  Items processed: {stats.new_items_processed}")
        print(f"  Embeddings generated: {stats.embeddings_generated}")
        print(f"  Qdrant writes: {stats.qdrant_writes}")
        print(f"  Errors: {stats.errors}")
        
        return True
        
    except Exception as e:
        print(f"✗ Embedding service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("Sam Embedding System Test Suite")
    print("=" * 50)
    
    # Test Redis
    if not test_redis_connection():
        print("\n❌ Redis test failed. Please ensure Redis is running.")
        sys.exit(1)
    
    # Test Qdrant
    if not test_qdrant_connection():
        print("\n❌ Qdrant test failed. Please ensure Qdrant is running.")
        sys.exit(1)
    
    # Ask about creating test data
    create_test = input("\nCreate test data if missing? (y/n): ")
    if create_test.lower() == 'y':
        create_test_data()
    
    # Ask about running embedding service
    run_embedding = input("\nRun embedding service test? (y/n): ")
    if run_embedding.lower() == 'y':
        test_embedding_service()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    main()
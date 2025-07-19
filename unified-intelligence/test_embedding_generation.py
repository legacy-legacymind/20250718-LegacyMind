#!/usr/bin/env python3
"""
Test embedding generation directly
"""
import os
from simple_embeddings import SimpleEmbeddingService

def test_embedding_generation():
    """Test if embedding generation is working"""
    print("🧪 Testing embedding generation...")
    
    # Setup
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    # Get API key from Redis
    import redis
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    api_key = client.get('config:openai_api_key')
    
    if not api_key:
        print("❌ No API key found")
        return
    
    print(f"✅ API key found ({len(api_key)} chars)")
    
    # Create service
    service = SimpleEmbeddingService(redis_url, api_key, "Claude")
    
    # Test embedding generation
    test_text = "This is a test about Qdrant vector database installation"
    print(f"Testing with: '{test_text}'")
    
    try:
        embedding = service.generate_embedding(test_text)
        if embedding:
            print(f"✅ Generated embedding: {len(embedding)} dimensions")
            print(f"First 5 values: {embedding[:5]}")
            return True
        else:
            print("❌ Embedding generation returned None")
            return False
    except Exception as e:
        print(f"❌ Error generating embedding: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_embedding_generation()
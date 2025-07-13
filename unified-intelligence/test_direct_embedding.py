#!/usr/bin/env python3
"""
Direct test of embedding generation without SimpleEmbeddingService
"""

import asyncio
import json
import os
import redis.asyncio as redis
from openai import OpenAI

async def test_direct_embedding():
    """Test embedding generation directly"""
    print("Testing direct embedding generation...")
    
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    # Get OpenAI API key from Redis
    test_redis = redis.from_url(redis_url, decode_responses=True)
    openai_api_key = await test_redis.get('config:openai_api_key')
    await test_redis.aclose()
    
    if not openai_api_key:
        print("❌ No OpenAI API key found")
        return False
    
    print(f"✅ OpenAI API key found ({len(openai_api_key)} chars)")
    
    try:
        # Create OpenAI client
        client = OpenAI(api_key=openai_api_key)
        print("✅ OpenAI client created")
        
        # Generate embedding
        test_text = "This is a test for direct embedding generation."
        print(f"🔄 Generating embedding for: '{test_text}'")
        
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=test_text
        )
        
        embedding = response.data[0].embedding
        print(f"✅ Embedding generated: {len(embedding)} dimensions")
        
        # Store in Redis directly
        thought_id = "direct-test-123"
        instance = "Claude"
        timestamp = 1234567890
        
        embedding_data = {
            "thought_id": thought_id,
            "content": test_text,
            "embedding": embedding,
            "timestamp": timestamp,
            "instance": instance
        }
        
        # Store in Redis
        store_redis = redis.from_url(redis_url, decode_responses=True)
        key = f"{instance}:embeddings:{thought_id}"
        await store_redis.set(key, json.dumps(embedding_data))
        
        # Verify storage
        stored_data = await store_redis.get(key)
        if stored_data:
            parsed_data = json.loads(stored_data)
            stored_embedding_length = len(parsed_data.get('embedding', []))
            print(f"✅ Embedding stored and verified: {stored_embedding_length} dimensions")
            
            # Clean up
            await store_redis.delete(key)
            print("🧹 Cleaned up test data")
        
        await store_redis.aclose()
        return True
        
    except Exception as e:
        print(f"❌ Direct embedding test failed: {e}")
        return False

async def main():
    """Run direct embedding test"""
    print("Direct Embedding Generation Test")
    print("=" * 40)
    
    success = await test_direct_embedding()
    
    print("\n" + "=" * 40)
    if success:
        print("✅ Direct embedding test PASSED!")
        print("   OpenAI API and Redis storage working correctly.")
    else:
        print("❌ Direct embedding test FAILED!")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
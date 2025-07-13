#!/usr/bin/env python3
"""
Test single embedding generation with the background service
"""

import asyncio
import logging
import os
import sys
import time
import json
import redis.asyncio as redis
from background_embedding_service import BackgroundEmbeddingService, EmbeddingTask, EmbeddingStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_single_embedding():
    """Test processing a single embedding with the background service"""
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    instance = "Claude"
    
    # Get OpenAI API key
    test_redis = redis.from_url(redis_url, decode_responses=True)
    openai_api_key = await test_redis.get('config:openai_api_key')
    await test_redis.aclose()
    
    if not openai_api_key:
        print("❌ No OpenAI API key found in Redis")
        return False
    
    print(f"✅ Found OpenAI API key ({len(openai_api_key)} characters)")
    
    try:
        # Create service
        service = BackgroundEmbeddingService(redis_url, openai_api_key, instance)
        
        # Create a test task
        test_task = EmbeddingTask(
            thought_id="test-embedding-" + str(int(time.time())),
            instance=instance,
            content="This is a test thought for background embedding generation.",
            timestamp=int(time.time()),
            status=EmbeddingStatus.PENDING
        )
        
        print(f"🧠 Created test task: {test_task.thought_id}")
        
        # Test the embedding generation process
        print("🔄 Processing embedding task...")
        success = await service.process_embedding_task(test_task)
        
        if success:
            print("✅ Embedding generated successfully!")
            
            # Verify it was stored in Redis
            embedding_key = f"{instance}:embeddings:{test_task.thought_id}"
            test_redis = redis.from_url(redis_url, decode_responses=True)
            embedding_data = await test_redis.get(embedding_key)
            await test_redis.aclose()
            
            if embedding_data:
                data = json.loads(embedding_data)
                embedding_length = len(data.get('embedding', []))
                print(f"✅ Embedding stored in Redis with {embedding_length} dimensions")
                
                # Clean up test data
                test_redis = redis.from_url(redis_url, decode_responses=True)
                await test_redis.delete(embedding_key)
                await test_redis.delete(f"embedding_queue:{test_task.thought_id}")
                await test_redis.aclose()
                print("🧹 Cleaned up test data")
                
                return True
            else:
                print("❌ Embedding not found in Redis")
                return False
        else:
            print("❌ Embedding generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def main():
    """Run the single embedding test"""
    print("Background Embedding Service - Single Embedding Test")
    print("=" * 60)
    
    success = await test_single_embedding()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Single embedding test PASSED!")
        print("   The background service is ready for production use.")
    else:
        print("❌ Single embedding test FAILED!")
        print("   Check the error messages above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
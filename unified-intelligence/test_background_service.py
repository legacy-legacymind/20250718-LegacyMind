#!/usr/bin/env python3
"""
Test script for Background Embedding Service
"""

import asyncio
import os
import sys
import redis.asyncio as redis
from background_embedding_service import BackgroundEmbeddingService

async def test_service_initialization():
    """Test that the service can initialize properly"""
    print("Testing Background Embedding Service initialization...")
    
    # Get configuration
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    instance = "Claude"
    
    # Mock OpenAI API key for testing
    openai_api_key = "test-key"
    
    try:
        # Test Redis connection
        test_redis = redis.from_url(redis_url, decode_responses=True)
        await test_redis.ping()
        print("✅ Redis connection successful")
        await test_redis.close()
        
        # Test service initialization (without starting the consumer loops)
        service = BackgroundEmbeddingService(redis_url, openai_api_key, instance)
        print("✅ Background service initialized successfully")
        
        # Test consumer group creation
        await service.ensure_consumer_group()
        print("✅ Consumer group created/verified")
        
        # Test metrics collection (without OpenAI API calls)
        metrics = await service.collect_metrics()
        print(f"✅ Metrics collection successful: {metrics}")
        
        await service.cleanup()
        print("✅ Service cleanup successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def test_stream_reading():
    """Test reading from Redis Streams"""
    print("\nTesting Redis Streams reading...")
    
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    try:
        test_redis = redis.from_url(redis_url, decode_responses=True)
        
        # Check stream exists and has data
        stream_key = "Claude:events"
        stream_length = await test_redis.xlen(stream_key)
        print(f"✅ Stream '{stream_key}' length: {stream_length}")
        
        if stream_length > 0:
            # Read latest event
            events = await test_redis.xrevrange(stream_key, count=1)
            if events:
                event_id, fields = events[0]
                print(f"✅ Latest event: {event_id}")
                print(f"   Fields: {fields}")
                
                # Check if it's a thought_created event
                if fields.get('event_type') == 'thought_created':
                    print("✅ Found thought_created event")
                else:
                    print(f"ℹ️  Event type: {fields.get('event_type')}")
        
        await test_redis.close()
        return True
        
    except Exception as e:
        print(f"❌ Stream reading test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("Background Embedding Service Test Suite")
    print("=" * 50)
    
    test1_passed = await test_service_initialization()
    test2_passed = await test_stream_reading()
    
    print("\n" + "=" * 50)
    if test1_passed and test2_passed:
        print("✅ All tests passed! Background service is ready.")
        return 0
    else:
        print("❌ Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
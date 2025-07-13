#!/usr/bin/env python3
"""
Simple test for Background Embedding Service core functionality
"""

import asyncio
import os
import sys
import redis.asyncio as redis

async def test_redis_connection():
    """Test Redis connection and streams"""
    print("Testing Redis connection and streams...")
    
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    try:
        test_redis = redis.from_url(redis_url, decode_responses=True)
        
        # Test basic connection
        await test_redis.ping()
        print("✅ Redis connection successful")
        
        # Test stream operations
        stream_key = "Claude:events"
        stream_length = await test_redis.xlen(stream_key)
        print(f"✅ Stream '{stream_key}' length: {stream_length}")
        
        # Test consumer group creation
        consumer_group = "test_embedding_processors"
        try:
            await test_redis.xgroup_create(stream_key, consumer_group, id="0", mkstream=True)
            print(f"✅ Created test consumer group: {consumer_group}")
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                print(f"✅ Test consumer group already exists: {consumer_group}")
            else:
                raise
        
        # Test reading from stream
        events = await test_redis.xreadgroup(
            consumer_group,
            "test_consumer",
            {stream_key: ">"},
            count=1,
            block=100  # 100ms timeout
        )
        
        if events:
            for stream_name, messages in events:
                print(f"✅ Read {len(messages)} events from stream")
                for message_id, fields in messages:
                    print(f"   Event: {message_id}, Type: {fields.get('event_type')}")
                    # Acknowledge the message
                    await test_redis.xack(stream_key, consumer_group, message_id)
        else:
            print("ℹ️  No new events in stream (expected)")
        
        # Cleanup test consumer group
        try:
            await test_redis.xgroup_destroy(stream_key, consumer_group)
            print("✅ Cleaned up test consumer group")
        except Exception:
            pass  # Group might not exist
        
        await test_redis.aclose()
        print("✅ Redis connection closed")
        
        return True
        
    except Exception as e:
        print(f"❌ Redis test failed: {e}")
        return False

async def test_background_service_core():
    """Test core background service functionality without OpenAI"""
    print("\nTesting background service core functionality...")
    
    try:
        # Import the service class
        from background_embedding_service import EmbeddingTask, EmbeddingStatus
        
        # Test dataclass creation
        task = EmbeddingTask(
            thought_id="test-123",
            instance="Claude",
            content="Test content",
            timestamp=1234567890,
            status=EmbeddingStatus.PENDING
        )
        
        print(f"✅ Created embedding task: {task.thought_id}")
        print(f"   Status: {task.status.value}")
        print(f"   Created at: {task.created_at}")
        
        # Test status transitions
        task.status = EmbeddingStatus.PROCESSING
        task.retry_count += 1
        print(f"✅ Status transition: {task.status.value}, retries: {task.retry_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Background service core test failed: {e}")
        return False

async def main():
    """Run simplified tests"""
    print("Background Embedding Service - Core Tests")
    print("=" * 50)
    
    test1_passed = await test_redis_connection()
    test2_passed = await test_background_service_core()
    
    print("\n" + "=" * 50)
    if test1_passed and test2_passed:
        print("✅ Core tests passed! Background service Redis integration is ready.")
        print("\nNext: Test with actual OpenAI API key for full functionality.")
        return 0
    else:
        print("❌ Some core tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
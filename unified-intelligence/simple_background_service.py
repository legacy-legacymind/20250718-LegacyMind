#!/usr/bin/env python3
"""
Simplified background service to isolate the async issues
"""

import asyncio
import logging
import os
import redis.asyncio as redis
import redis.exceptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleBackgroundService:
    def __init__(self):
        redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        redis_url = f"redis://:{redis_password}@localhost:6379/0"
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.consumer_group = "simple_embedding_processors"
        self.consumer_name = "simple_embedder"
        self.stream_key = "Claude:events"
        
    async def test_stream_consumer(self):
        """Test just the stream consumer logic"""
        logger.info("Testing stream consumer...")
        
        try:
            # Ensure consumer group
            try:
                await self.redis.xgroup_create(
                    self.stream_key,
                    self.consumer_group,
                    id="0",
                    mkstream=True
                )
                logger.info("Created consumer group")
            except redis.exceptions.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    logger.info("Consumer group already exists")
                else:
                    raise
            
            # Read events
            logger.info("Reading from stream...")
            events = await self.redis.xreadgroup(
                self.consumer_group,
                self.consumer_name,
                {self.stream_key: ">"},
                count=5,
                block=1000
            )
            
            logger.info(f"Read {len(events)} event groups")
            
            for stream_name, messages in events:
                logger.info(f"Stream: {stream_name}, Messages: {len(messages)}")
                for message_id, fields in messages:
                    logger.info(f"Event: {message_id}, Type: {fields.get('event_type')}")
                    
                    # Acknowledge message
                    await self.redis.xack(self.stream_key, self.consumer_group, message_id)
                    logger.info(f"Acknowledged: {message_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Stream consumer test failed: {e}")
            return False
    
    async def test_keys_operation(self):
        """Test the keys operation that was failing"""
        logger.info("Testing keys operation...")
        
        try:
            keys = await self.redis.keys("embedding_queue:*")
            logger.info(f"Found {len(keys)} queue keys")
            return True
        except Exception as e:
            logger.error(f"Keys operation failed: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup"""
        await self.redis.aclose()

async def main():
    """Test the simplified service"""
    service = SimpleBackgroundService()
    
    try:
        logger.info("Testing simplified background service components...")
        
        # Test individual components
        keys_ok = await service.test_keys_operation()
        stream_ok = await service.test_stream_consumer()
        
        if keys_ok and stream_ok:
            logger.info("✅ All components work individually")
        else:
            logger.error("❌ Some components failed")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        await service.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""
Working Background Embedding Service - Fixed async issues
"""

import asyncio
import logging
import json
import time
import os
import sys
import redis.asyncio as redis
import redis.exceptions
from simple_embeddings import SimpleEmbeddingService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorkingBackgroundService:
    def __init__(self):
        redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        redis_url = f"redis://:{redis_password}@localhost:6379/0"
        self.redis = redis.from_url(redis_url, decode_responses=True)
        
        # Get OpenAI API key from Redis
        self.openai_api_key = None
        self.instance = "Claude"
        self.consumer_group = "embedding_processors"
        self.consumer_name = f"embedder_{os.getpid()}"
        self.stream_key = f"{self.instance}:events"
        
        # Initialize embedding service later after we get API key
        self.embedding_service = None
        
    async def initialize(self):
        """Initialize the service with API key"""
        try:
            # Get API key from Redis
            api_key = await self.redis.get('config:openai_api_key')
            if not api_key:
                logger.error("No OpenAI API key found in Redis")
                return False
            
            self.openai_api_key = api_key
            # Create sync redis URL for SimpleEmbeddingService
            redis_url = f"redis://:{os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')}@localhost:6379/0"
            self.embedding_service = SimpleEmbeddingService(redis_url, api_key, self.instance)
            
            logger.info(f"Initialized with API key ({len(api_key)} chars)")
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    async def ensure_consumer_group(self):
        """Create consumer group if needed"""
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
    
    async def process_one_batch(self):
        """Process one batch of events"""
        try:
            # Read events
            events = await self.redis.xreadgroup(
                self.consumer_group,
                self.consumer_name,
                {self.stream_key: ">"},
                count=5,
                block=1000
            )
            
            processed = 0
            for stream_name, messages in events:
                for message_id, fields in messages:
                    success = await self.process_single_event(message_id, fields)
                    if success:
                        processed += 1
                        await self.redis.xack(self.stream_key, self.consumer_group, message_id)
            
            if processed > 0:
                logger.info(f"Processed {processed} events")
            
            return processed
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            return 0
    
    async def process_single_event(self, message_id: str, fields: dict):
        """Process a single event"""
        try:
            event_type = fields.get('event_type')
            if event_type != 'thought_created':
                return True  # Skip non-thought events
            
            thought_id = fields.get('thought_id')
            if not thought_id:
                logger.warning(f"Event missing thought_id: {message_id}")
                return True  # Skip malformed events
            
            # Check if embedding already exists
            embedding_key = f"{self.instance}:embeddings:{thought_id}"
            exists = await self.redis.exists(embedding_key)
            if exists:
                logger.debug(f"Embedding already exists for {thought_id}")
                return True
            
            # Fetch thought content
            thought_key = f"{self.instance}:Thoughts:{thought_id}"
            thought_data_str = await self.redis.get(thought_key)
            if not thought_data_str:
                logger.error(f"Thought not found: {thought_key}")
                return False
            
            # Parse thought content
            thought_data = json.loads(thought_data_str)
            content = thought_data.get('thought', '')
            if not content:
                logger.error(f"Empty thought content for {thought_id}")
                return False
            
            # Parse timestamp
            timestamp_str = fields.get('timestamp', '')
            try:
                if timestamp_str:
                    from datetime import datetime
                    timestamp = int(datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp())
                else:
                    timestamp = int(time.time())
            except ValueError:
                timestamp = int(time.time())
            
            # Generate embedding
            logger.info(f"Generating embedding for {thought_id}...")
            success = await asyncio.get_event_loop().run_in_executor(
                None,
                self.embedding_service.store_thought_embedding,
                thought_id,
                content,
                timestamp
            )
            
            if success:
                logger.info(f"✅ Generated embedding for {thought_id}")
                return True
            else:
                logger.error(f"❌ Failed to generate embedding for {thought_id}")
                return False
                
        except Exception as e:
            logger.error(f"Event processing error for {message_id}: {e}")
            return False
    
    async def run_continuous(self):
        """Run the service continuously"""
        logger.info("Starting continuous processing...")
        
        consecutive_empty = 0
        max_empty = 5  # Stop after 5 consecutive empty batches
        
        while consecutive_empty < max_empty:
            processed = await self.process_one_batch()
            
            if processed == 0:
                consecutive_empty += 1
                if consecutive_empty >= max_empty:
                    logger.info("No more events to process, stopping")
                    break
                await asyncio.sleep(2)  # Wait before checking again
            else:
                consecutive_empty = 0  # Reset counter on successful processing
                await asyncio.sleep(0.1)  # Brief pause between batches
        
        logger.info("Continuous processing complete")
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            await self.redis.aclose()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def main():
    """Main entry point"""
    service = WorkingBackgroundService()
    
    try:
        logger.info("Starting Working Background Embedding Service")
        
        # Initialize
        if not await service.initialize():
            logger.error("Service initialization failed")
            return
        
        # Set up consumer group
        await service.ensure_consumer_group()
        
        # Process events
        await service.run_continuous()
        
        logger.info("Service completed successfully")
        
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
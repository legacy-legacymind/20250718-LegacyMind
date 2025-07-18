#!/usr/bin/env python3
"""
Simplified Federation Embedding Service - Fix async issues
"""

import asyncio
import logging
import os
import redis.asyncio as redis
from typing import Dict, Set
from simple_embeddings import SimpleEmbeddingService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleFederationEmbedding:
    def __init__(self, redis_url: str, openai_api_key: str):
        self.redis_url = redis_url
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.openai_api_key = openai_api_key
        self.known_instances: Set[str] = set()
        self.embedding_services: Dict[str, SimpleEmbeddingService] = {}
        self.consumer_group = "federation_embedding"
        self.consumer_name = f"fed_embed_{os.getpid()}"
        
    async def discover_and_setup_instances(self):
        """Discover instances and set up embedding services"""
        logger.info("Discovering federation instances...")
        
        # Get stream keys
        stream_keys = await self.redis.keys("*:events")
        
        for stream_key in stream_keys:
            instance = stream_key.split(':')[0]
            if instance and instance not in ['temp', 'test', 'TEST_IDENTITY']:
                if instance not in self.known_instances:
                    logger.info(f"Setting up instance: {instance}")
                    
                    # Create embedding service
                    embedding_service = SimpleEmbeddingService(self.redis_url, self.openai_api_key, instance)
                    self.embedding_services[instance] = embedding_service
                    
                    # Create consumer group
                    try:
                        await self.redis.xgroup_create(stream_key, self.consumer_group, "0", mkstream=True)
                        logger.info(f"Created consumer group for {instance}")
                    except redis.ResponseError as e:
                        if "BUSYGROUP" not in str(e):
                            logger.error(f"Consumer group error for {instance}: {e}")
                    
                    self.known_instances.add(instance)
        
        logger.info(f"Active instances: {sorted(self.known_instances)}")
    
    async def process_all_instances(self):
        """Process events from all instances"""
        for instance in list(self.known_instances):
            stream_key = f"{instance}:events"
            
            try:
                # Read events
                result = await self.redis.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {stream_key: ">"},
                    count=5,
                    block=50
                )
                
                if result:
                    for stream, events in result:
                        for event_id, fields in events:
                            if fields.get('type') == 'thought_created':
                                thought_id = fields.get('thought_id')
                                if thought_id and instance in self.embedding_services:
                                    # Process embedding
                                    embedding_service = self.embedding_services[instance]
                                    loop = asyncio.get_event_loop()
                                    await loop.run_in_executor(None, embedding_service.process_thought, thought_id)
                                    logger.info(f"Processed embedding for {instance}:{thought_id}")
                            
                            # Acknowledge
                            await self.redis.xack(stream_key, self.consumer_group, event_id)
                            
            except Exception as e:
                if "NOGROUP" in str(e):
                    try:
                        await self.redis.xgroup_create(stream_key, self.consumer_group, "0", mkstream=True)
                    except:
                        pass
                else:
                    logger.error(f"Error processing {instance}: {e}")
    
    async def run(self):
        """Main service loop"""
        logger.info("Starting Simple Federation Embedding Service")
        
        await self.discover_and_setup_instances()
        
        while True:
            try:
                await self.process_all_instances()
                await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Service error: {e}")
                await asyncio.sleep(5)
        
        await self.redis.aclose()

async def main():
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    # Get API key
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        temp_redis = redis.from_url(redis_url, decode_responses=True)
        openai_api_key = await temp_redis.get('config:openai_api_key')
        await temp_redis.aclose()
    
    if not openai_api_key:
        logger.error("No OpenAI API key found")
        return
    
    service = SimpleFederationEmbedding(redis_url, openai_api_key)
    await service.run()

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""Test script to debug async Redis issues"""

import asyncio
import redis.asyncio as redis
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_redis_operations():
    redis_url = "redis://:legacymind_redis_pass@localhost:6379/0"
    
    # Create client same way as BackgroundEmbeddingService
    client = redis.from_url(redis_url, decode_responses=True)
    
    logger.info(f"Client type: {type(client)}")
    logger.info(f"Client class: {client.__class__}")
    
    try:
        # Test basic operations
        logger.info("Testing ping...")
        result = await client.ping()
        logger.info(f"Ping result: {result}")
        
        # Test keys operation
        logger.info("Testing keys...")
        keys = await client.keys("test*")
        logger.info(f"Keys result type: {type(keys)}")
        logger.info(f"Keys: {keys}")
        
        # Test xreadgroup
        logger.info("Testing xreadgroup...")
        try:
            events = await client.xreadgroup(
                "test_group",
                "test_consumer", 
                {"Claude:events": ">"},
                count=1,
                block=100
            )
            logger.info(f"Events type: {type(events)}")
            logger.info(f"Events: {events}")
        except Exception as e:
            logger.error(f"xreadgroup error: {e}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(test_redis_operations())
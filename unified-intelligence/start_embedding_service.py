#!/usr/bin/env python3
"""
Production startup script for Background Embedding Service
"""

import asyncio
import logging
import signal
import sys
import os
import redis.asyncio as redis
from background_embedding_service import BackgroundEmbeddingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('embedding_service.log')
    ]
)

logger = logging.getLogger(__name__)

class EmbeddingServiceManager:
    def __init__(self):
        self.service = None
        self.running = False
        
    async def start(self):
        """Start the embedding service with proper configuration"""
        logger.info("Starting Background Embedding Service Manager...")
        
        # Get configuration
        redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        redis_url = f"redis://:{redis_password}@localhost:6379/0"
        instance = os.getenv('INSTANCE_ID', 'Claude')
        
        # Get OpenAI API key
        openai_api_key = await self.get_openai_api_key(redis_url)
        if not openai_api_key:
            logger.error("Failed to retrieve OpenAI API key")
            return False
        
        logger.info(f"Retrieved OpenAI API key ({len(openai_api_key)} characters)")
        
        # Test Redis connection
        if not await self.test_redis_connection(redis_url):
            logger.error("Redis connection test failed")
            return False
        
        # Create and start service
        try:
            self.service = BackgroundEmbeddingService(redis_url, openai_api_key, instance)
            self.running = True
            
            # Set up signal handlers
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            logger.info("Starting background service...")
            await self.service.start()
            
        except Exception as e:
            logger.error(f"Service failed: {e}")
            return False
            
        return True
    
    async def get_openai_api_key(self, redis_url: str) -> str:
        """Get OpenAI API key from environment or Redis"""
        # First try environment
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            logger.info("Using OpenAI API key from environment")
            return api_key
        
        # Try Redis
        try:
            sync_redis = redis.from_url(redis_url, decode_responses=True)
            api_key = await sync_redis.get('config:openai_api_key')
            await sync_redis.aclose()
            
            if api_key:
                logger.info("Retrieved OpenAI API key from Redis")
                return api_key
        except Exception as e:
            logger.error(f"Error retrieving API key from Redis: {e}")
        
        return None
    
    async def test_redis_connection(self, redis_url: str) -> bool:
        """Test Redis connection"""
        try:
            test_redis = redis.from_url(redis_url, decode_responses=True)
            await test_redis.ping()
            
            # Check if events stream exists
            stream_key = "Claude:events"
            stream_length = await test_redis.xlen(stream_key)
            logger.info(f"Redis connection OK. Stream '{stream_key}' has {stream_length} events")
            
            await test_redis.aclose()
            return True
        except Exception as e:
            logger.error(f"Redis connection test failed: {e}")
            return False
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        
        if self.service:
            # Trigger service shutdown
            # Note: This is a synchronous handler, so we can't await here
            # The service should check self.running in its loops
            pass

async def main():
    """Main entry point"""
    logger.info("Background Embedding Service - Production Start")
    logger.info("=" * 60)
    
    manager = EmbeddingServiceManager()
    
    try:
        success = await manager.start()
        if success:
            logger.info("Service completed successfully")
        else:
            logger.error("Service failed to start")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 7):
        print("Error: Python 3.7+ required")
        sys.exit(1)
    
    # Run service
    asyncio.run(main())
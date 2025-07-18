#!/usr/bin/env python3
"""
Startup script for Federation Embedding Service
Replaces single-instance embedding services with federation-wide auto-discovery
"""

import asyncio
import logging
import signal
import sys
import os
from federation_embedding_service import FederationEmbeddingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('federation_embedding_service.log')
    ]
)

logger = logging.getLogger(__name__)

class FederationServiceManager:
    def __init__(self):
        self.service = None
        self.running = False
        
    async def start(self):
        """Start the federation embedding service"""
        logger.info("Starting Federation Embedding Service Manager...")
        
        # Get configuration
        redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        redis_url = f"redis://:{redis_password}@localhost:6379/0"
        
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
        
        # Create and start federation service
        try:
            self.service = FederationEmbeddingService(redis_url, openai_api_key)
            self.running = True
            
            # Set up signal handlers
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            logger.info("Starting federation embedding service...")
            await self.service.start()
            
        except Exception as e:
            logger.error(f"Federation service failed: {e}")
            return False
            
        return True
    
    async def get_openai_api_key(self, redis_url: str) -> str:
        """Get OpenAI API key from environment or Redis"""
        import redis.asyncio as redis
        
        # First try environment
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            logger.info("Using OpenAI API key from environment")
            return api_key
        
        # Try Redis
        try:
            r = redis.from_url(redis_url, decode_responses=True)
            api_key = await r.get('config:openai_api_key')
            await r.aclose()
            
            if api_key:
                logger.info("Retrieved OpenAI API key from Redis")
                return api_key
        except Exception as e:
            logger.error(f"Error retrieving API key from Redis: {e}")
        
        return None
    
    async def test_redis_connection(self, redis_url: str) -> bool:
        """Test Redis connection and check for federation instances"""
        import redis.asyncio as redis
        
        try:
            r = redis.from_url(redis_url, decode_responses=True)
            await r.ping()
            
            # Check for federation event streams
            stream_keys = await r.keys("*:events")
            instances = [key.split(':')[0] for key in stream_keys if ':' in key]
            
            logger.info(f"Redis connection OK. Found federation instances: {sorted(instances)}")
            
            await r.aclose()
            return True
        except Exception as e:
            logger.error(f"Redis connection test failed: {e}")
            return False
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down federation service...")
        self.running = False

async def main():
    """Main entry point"""
    logger.info("Federation Embedding Service - Production Start")
    logger.info("Auto-Discovery Multi-Instance Processing")
    logger.info("=" * 60)
    
    manager = FederationServiceManager()
    
    try:
        success = await manager.start()
        if success:
            logger.info("Federation service completed successfully")
        else:
            logger.error("Federation service failed to start")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Federation service interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 7):
        print("Error: Python 3.7+ required")
        sys.exit(1)
    
    # Run federation service
    asyncio.run(main())
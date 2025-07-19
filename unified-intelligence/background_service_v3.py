#!/usr/bin/env python3
"""
Background Embedding Service v3 - With Provider Fallback
Includes OpenAI primary and Groq fallback support
"""

import asyncio
import logging
import json
import time
import os
import sys
import yaml
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
import redis.asyncio as redis
import redis.exceptions
from embedding_service_with_fallback import EmbeddingServiceWithFallback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"

@dataclass
class ServiceMetrics:
    total_processed: int = 0
    openai_success: int = 0
    openai_failures: int = 0
    groq_success: int = 0
    groq_failures: int = 0
    last_openai_failure: Optional[float] = None
    last_groq_failure: Optional[float] = None
    current_provider: str = "openai"

class BackgroundEmbeddingServiceV3:
    def __init__(self, config_path: str = "config.yaml"):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize Redis
        redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        redis_url = f"redis://:{redis_password}@localhost:6379/0"
        self.redis = redis.from_url(redis_url, decode_responses=True)
        
        # Initialize metrics
        self.metrics = ServiceMetrics()
        
        # Consumer configuration
        self.instance = os.getenv('INSTANCE_ID', 'Claude')
        self.consumer_group = self.config['embedding_service']['consumer']['group_name']
        self.consumer_name = f"{self.config['embedding_service']['consumer']['consumer_prefix']}_{os.getpid()}"
        self.stream_key = f"{self.instance}:events"
        
        # Initialize embedding service (later after getting API keys)
        self.embedding_service = None
        
    async def initialize(self):
        """Initialize the service with API keys"""
        try:
            # Get API keys
            openai_key = await self._get_api_key('primary')
            groq_key = await self._get_api_key('fallback')
            
            if not openai_key:
                logger.error("No OpenAI API key found")
                return False
            
            # Create embedding service with fallback
            sync_redis_url = f"redis://:{os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')}@localhost:6379/0"
            self.embedding_service = EmbeddingServiceWithFallback(
                sync_redis_url, 
                openai_key, 
                groq_key,  # Can be None if not available
                self.instance
            )
            
            logger.info(f"Initialized with OpenAI key ({len(openai_key)} chars)")
            if groq_key:
                logger.info(f"Groq fallback available ({len(groq_key)} chars)")
            else:
                logger.warning("Groq fallback not available")
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    async def _get_api_key(self, provider_type: str) -> Optional[str]:
        """Get API key for a provider from Redis or environment"""
        provider_config = self.config['embedding_service']['providers'][provider_type]
        
        if provider_config['api_key_source'] == 'redis':
            key = await self.redis.get(provider_config['api_key_field'])
            return key if key else None
        else:
            # Get from environment
            env_var = f"{provider_config['provider'].upper()}_API_KEY"
            return os.getenv(env_var)
    
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
    
    async def process_batch(self):
        """Process a batch of events with fallback support"""
        try:
            # Read events
            events = await self.redis.xreadgroup(
                self.consumer_group,
                self.consumer_name,
                {self.stream_key: ">"},
                count=self.config['embedding_service']['processing']['batch_size'],
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
                await self.update_metrics()
            
            return processed
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            return 0
    
    async def process_single_event(self, message_id: str, fields: dict):
        """Process a single event with provider fallback"""
        try:
            # Check event type
            if fields.get('event_type') != 'thought_created':
                return True
            
            thought_id = fields.get('thought_id')
            if not thought_id:
                return True
            
            # Check if embedding exists
            embedding_key = f"{self.instance}:embeddings:{thought_id}"
            if await self.redis.exists(embedding_key):
                return True
            
            # Get thought content
            thought_key = f"{self.instance}:Thoughts:{thought_id}"
            thought_data_str = await self.redis.get(thought_key)
            if not thought_data_str:
                logger.error(f"Thought not found: {thought_key}")
                return False
            
            # Parse content
            thought_data = json.loads(thought_data_str)
            content = thought_data.get('thought', '')
            if not content:
                return False
            
            # Parse timestamp
            timestamp = self._parse_timestamp(fields.get('timestamp', ''))
            
            # Generate embedding with fallback support
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.embedding_service.store_thought_embedding,
                thought_id,
                content,
                timestamp
            )
            
            # Track metrics
            if result.get('success'):
                self.metrics.total_processed += 1
                provider = result.get('provider', 'unknown')
                
                if provider == 'openai':
                    self.metrics.openai_success += 1
                elif provider == 'groq_fallback':
                    self.metrics.groq_success += 1
                    logger.warning(f"Used Groq fallback for {thought_id}")
                
                logger.info(f"✅ {thought_id} (provider: {provider})")
                return True
            else:
                logger.error(f"❌ Failed: {thought_id} - {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"Event processing error: {e}")
            return False
    
    def _parse_timestamp(self, timestamp_str: str) -> int:
        """Parse timestamp from various formats"""
        try:
            if timestamp_str:
                from datetime import datetime
                return int(datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp())
            else:
                return int(time.time())
        except ValueError:
            return int(time.time())
    
    async def update_metrics(self):
        """Update service metrics in Redis"""
        try:
            metrics_data = {
                "timestamp": time.time(),
                "total_processed": self.metrics.total_processed,
                "openai_success": self.metrics.openai_success,
                "openai_failures": self.metrics.openai_failures,
                "groq_success": self.metrics.groq_success,
                "groq_failures": self.metrics.groq_failures,
                "current_provider": self.metrics.current_provider,
                "consumer": self.consumer_name
            }
            
            metrics_key = f"embedding_service_metrics:v3:{self.consumer_name}"
            await self.redis.set(metrics_key, json.dumps(metrics_data), ex=300)
            
            # Log provider usage if tracking enabled
            if self.config['embedding_service']['monitoring']['track_provider_usage']:
                if self.metrics.groq_success > 0:
                    fallback_rate = self.metrics.groq_success / self.metrics.total_processed * 100
                    logger.info(f"Fallback usage: {fallback_rate:.1f}% ({self.metrics.groq_success}/{self.metrics.total_processed})")
                    
        except Exception as e:
            logger.error(f"Metrics update error: {e}")
    
    async def run_continuous(self):
        """Run the service continuously"""
        logger.info("Starting continuous processing with fallback support...")
        
        while True:
            processed = await self.process_batch()
            
            if processed == 0:
                await asyncio.sleep(2)
            else:
                # Brief pause between batches
                delay = self.config['embedding_service']['processing']['rate_limit_delay']
                await asyncio.sleep(delay)
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            await self.update_metrics()
            await self.redis.aclose()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def main():
    """Main entry point"""
    service = BackgroundEmbeddingServiceV3()
    
    try:
        logger.info("Starting Background Embedding Service v3 (with fallback)")
        
        # Initialize
        if not await service.initialize():
            logger.error("Service initialization failed")
            return
        
        # Set up consumer group
        await service.ensure_consumer_group()
        
        # Process events
        await service.run_continuous()
        
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
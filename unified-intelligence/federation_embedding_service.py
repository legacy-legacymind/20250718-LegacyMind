#!/usr/bin/env python3
"""
Federation-wide Embedding Service for UnifiedIntelligence
Automatically discovers and processes all federation instances
Handles future instances dynamically without configuration changes

Author: CCD (Database & Architecture Specialist)  
Date: 2025-07-17
"""

import asyncio
import logging
import json
import time
import os
import sys
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import redis.asyncio as redis
import redis.exceptions
from simple_embeddings import SimpleEmbeddingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmbeddingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class InstanceMetrics:
    instance: str
    processed_count: int = 0
    failed_count: int = 0
    last_activity: float = 0
    stream_length: int = 0
    pending_events: int = 0

class FederationEmbeddingService:
    def __init__(self, redis_url: str, openai_api_key: str):
        self.redis_url = redis_url
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.openai_api_key = openai_api_key
        
        # Federation management
        self.known_instances: Set[str] = set()
        self.instance_metrics: Dict[str, InstanceMetrics] = {}
        self.embedding_services: Dict[str, SimpleEmbeddingService] = {}
        
        # Configuration
        self.max_retries = 3
        self.rate_limit_delay = 0.1  # 100ms between API calls
        self.consumer_group = "federation_embedding_processors"
        self.consumer_name = f"fed_embedder_{os.getpid()}"
        self.discovery_interval = 30  # seconds between instance discovery
        
        # Global metrics
        self.total_processed = 0
        self.total_failed = 0
        self.service_start_time = time.time()
        
    async def start(self):
        """Main federation service loop"""
        logger.info("Starting Federation Embedding Service")
        logger.info(f"Consumer: {self.consumer_name}")
        logger.info("Auto-discovering federation instances...")
        
        try:
            # Initial discovery
            await self.discover_instances()
            
            # Start concurrent tasks
            await asyncio.gather(
                self.instance_discovery_loop(),
                self.federation_stream_processor(),
                self.metrics_reporter(),
                self.health_monitor(),
                return_exceptions=True
            )
        except KeyboardInterrupt:
            logger.info("Shutting down gracefully...")
        except Exception as e:
            logger.error(f"Federation service crashed: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def discover_instances(self):
        """Discover all federation instances by scanning for event streams"""
        try:
            # Get all keys matching instance event stream pattern
            stream_pattern = "*:events"
            stream_keys = await self.redis.keys(stream_pattern)
            
            new_instances = set()
            for stream_key in stream_keys:
                # Extract instance name from stream key (e.g., "CC:events" -> "CC")
                instance = stream_key.split(':')[0]
                if instance and instance not in ['temp', 'test']:  # Filter out temp streams
                    new_instances.add(instance)
            
            # Add newly discovered instances
            for instance in new_instances:
                if instance not in self.known_instances:
                    await self.add_instance(instance)
            
            # Remove instances that no longer have streams (cleanup)
            missing_instances = self.known_instances - new_instances
            for instance in missing_instances:
                await self.remove_instance(instance)
                
            logger.info(f"Active federation instances: {sorted(self.known_instances)}")
            
        except Exception as e:
            logger.error(f"Instance discovery failed: {e}")
    
    async def add_instance(self, instance: str):
        """Add a new instance to the federation"""
        logger.info(f"Adding new instance: {instance}")
        
        try:
            # Create embedding service for this instance
            sync_redis_url = self.redis_url
            embedding_service = SimpleEmbeddingService(sync_redis_url, self.openai_api_key, instance)
            self.embedding_services[instance] = embedding_service
            
            # Initialize metrics
            self.instance_metrics[instance] = InstanceMetrics(instance=instance)
            
            # Ensure consumer group exists for this instance
            stream_key = f"{instance}:events"
            try:
                await self.redis.xgroup_create(stream_key, self.consumer_group, "0", mkstream=True)
                logger.info(f"Created consumer group for {instance}")
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    logger.error(f"Failed to create consumer group for {instance}: {e}")
            
            self.known_instances.add(instance)
            logger.info(f"Successfully added instance: {instance}")
            
        except Exception as e:
            logger.error(f"Failed to add instance {instance}: {e}")
    
    async def remove_instance(self, instance: str):
        """Remove an instance from the federation"""
        logger.info(f"Removing inactive instance: {instance}")
        
        if instance in self.embedding_services:
            del self.embedding_services[instance]
        if instance in self.instance_metrics:
            del self.instance_metrics[instance]
        
        self.known_instances.discard(instance)
    
    async def instance_discovery_loop(self):
        """Periodically discover new instances"""
        while True:
            await asyncio.sleep(self.discovery_interval)
            await self.discover_instances()
    
    async def federation_stream_processor(self):
        """Process events from all federation instance streams"""
        while True:
            try:
                # Process each known instance  
                instances_copy = list(self.known_instances)
                for instance in instances_copy:
                    await self.process_instance_events(instance)
                    
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Federation stream processor error: {e}")
                await asyncio.sleep(1)  # Backoff on error
    
    async def process_instance_events(self, instance: str):
        """Process pending events for a specific instance"""
        stream_key = f"{instance}:events"
        
        try:
            # Read pending events
            result = await self.redis.xreadgroup(
                self.consumer_group,
                self.consumer_name,
                {stream_key: ">"},
                count=10,
                block=100  # 100ms block
            )
            
            if not result:
                return
            
            for stream, events in result:
                for event_id, fields in events:
                    try:
                        await self.process_event(instance, event_id, fields)
                        
                        # Acknowledge successful processing
                        await self.redis.xack(stream_key, self.consumer_group, event_id)
                        
                        # Update metrics
                        self.instance_metrics[instance].processed_count += 1
                        self.instance_metrics[instance].last_activity = time.time()
                        self.total_processed += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to process event {event_id} for {instance}: {e}")
                        self.instance_metrics[instance].failed_count += 1
                        self.total_failed += 1
                        
        except Exception as e:
            if "NOGROUP" in str(e):
                # Consumer group doesn't exist, recreate it
                try:
                    await self.redis.xgroup_create(stream_key, self.consumer_group, "0", mkstream=True)
                except:
                    pass
            else:
                logger.error(f"Error reading from {instance} stream: {e}")
    
    async def process_event(self, instance: str, event_id: str, fields: Dict):
        """Process a single embedding event"""
        event_type = fields.get('type')
        
        if event_type == 'thought_created':
            thought_id = fields.get('thought_id')
            if thought_id and instance in self.embedding_services:
                # Generate embedding using the instance-specific service
                embedding_service = self.embedding_services[instance]
                await self.generate_embedding_async(embedding_service, thought_id)
                
    async def generate_embedding_async(self, embedding_service, thought_id: str):
        """Generate embedding asynchronously (wrapper for sync service)"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, embedding_service.process_thought, thought_id)
        
        # Rate limiting
        await asyncio.sleep(self.rate_limit_delay)
    
    async def metrics_reporter(self):
        """Report federation-wide metrics periodically"""
        while True:
            await asyncio.sleep(60)  # Report every minute
            
            uptime = time.time() - self.service_start_time
            logger.info("=== Federation Embedding Service Metrics ===")
            logger.info(f"Uptime: {uptime:.1f}s")
            logger.info(f"Total Processed: {self.total_processed}")
            logger.info(f"Total Failed: {self.total_failed}")
            logger.info(f"Active Instances: {len(self.known_instances)}")
            
            for instance, metrics in self.instance_metrics.items():
                logger.info(f"  {instance}: {metrics.processed_count} processed, {metrics.failed_count} failed")
    
    async def health_monitor(self):
        """Monitor federation health and instance activity"""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            
            current_time = time.time()
            inactive_threshold = 3600  # 1 hour
            
            for instance, metrics in self.instance_metrics.items():
                time_since_activity = current_time - metrics.last_activity
                if time_since_activity > inactive_threshold:
                    logger.warning(f"Instance {instance} has been inactive for {time_since_activity:.1f}s")
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            await self.redis.aclose()
            logger.info("Federation embedding service cleaned up")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def main():
    """Main entry point"""
    logger.info("Federation Embedding Service - Multi-Instance Auto-Discovery")
    logger.info("=" * 70)
    
    # Get configuration
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    # Get OpenAI API key
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        # Try Redis
        try:
            temp_redis = redis.from_url(redis_url, decode_responses=True)
            openai_api_key = await temp_redis.get('config:openai_api_key')
            await temp_redis.aclose()
        except Exception as e:
            logger.error(f"Failed to get OpenAI API key: {e}")
            sys.exit(1)
    
    if not openai_api_key:
        logger.error("OpenAI API key not found in environment or Redis")
        sys.exit(1)
    
    # Create and start federation service
    try:
        service = FederationEmbeddingService(redis_url, openai_api_key)
        await service.start()
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""
Background Embedding Service for UnifiedIntelligence
Processes thought embedding generation asynchronously via Redis Streams

Author: CCD (Database & Architecture Specialist)
Date: 2025-07-13
Phase: 2 - Background Service Core
"""

import asyncio
import logging
import json
import time
import os
import sys
from typing import Dict, List, Optional
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
class EmbeddingTask:
    thought_id: str
    instance: str
    content: str
    timestamp: int
    status: EmbeddingStatus
    retry_count: int = 0
    last_error: Optional[str] = None
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

class BackgroundEmbeddingService:
    def __init__(self, redis_url: str, openai_api_key: str, instance: str = "Claude"):
        self.redis_url = redis_url
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.openai_api_key = openai_api_key
        self.instance = instance
        # Create sync redis URL for SimpleEmbeddingService
        sync_redis_url = redis_url
        self.embedding_service = SimpleEmbeddingService(sync_redis_url, openai_api_key, instance)
        
        # Configuration
        self.max_retries = 3
        self.rate_limit_delay = 0.1  # 100ms between API calls
        self.consumer_group = "embedding_processors"
        self.consumer_name = f"embedder_{os.getpid()}"
        self.stream_key = f"{instance}:events"
        
        # Metrics
        self.processed_count = 0
        self.failed_count = 0
        self.last_metrics_report = time.time()
        
    async def start(self):
        """Main service loop"""
        logger.info(f"Starting Background Embedding Service for instance: {self.instance}")
        logger.info(f"Consumer: {self.consumer_name}")
        logger.info(f"Stream: {self.stream_key}")
        
        try:
            # Initialize consumer group if it doesn't exist
            await self.ensure_consumer_group()
            
            # Start concurrent tasks
            await asyncio.gather(
                self.stream_consumer(),
                self.retry_processor(),
                self.metrics_reporter(),
                return_exceptions=True
            )
        except KeyboardInterrupt:
            logger.info("Shutting down gracefully...")
        except Exception as e:
            logger.error(f"Service crashed: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def ensure_consumer_group(self):
        """Create consumer group if it doesn't exist"""
        try:
            # Try to create the consumer group
            await self.redis.xgroup_create(
                self.stream_key,
                self.consumer_group,
                id="0",
                mkstream=True
            )
            logger.info(f"Created consumer group: {self.consumer_group}")
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"Consumer group already exists: {self.consumer_group}")
            else:
                raise
    
    async def stream_consumer(self):
        """Consume Redis Streams for new thought events"""
        logger.info("Starting stream consumer...")
        
        while True:
            try:
                # Read from stream
                events = await self.redis.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.stream_key: ">"},
                    count=10,
                    block=1000  # 1 second timeout
                )
                
                for stream_name, messages in events:
                    for message_id, fields in messages:
                        await self.process_event(message_id, fields)
                        
            except redis.exceptions.ConnectionError as e:
                logger.error(f"Redis connection error: {e}")
                await asyncio.sleep(5)  # Backoff
            except Exception as e:
                logger.error(f"Stream consumer error: {e}")
                await asyncio.sleep(5)  # Backoff
    
    async def process_event(self, message_id: str, fields: Dict):
        """Process a single stream event"""
        try:
            event_type = fields.get('event_type')
            if event_type != 'thought_created':
                # Acknowledge non-thought events
                await self.redis.xack(self.stream_key, self.consumer_group, message_id)
                return
                
            # Extract event data
            thought_id = fields.get('thought_id')
            instance = fields.get('instance', self.instance)
            timestamp_str = fields.get('timestamp', '')
            
            if not thought_id:
                logger.warning(f"Event missing thought_id: {message_id}")
                await self.redis.xack(self.stream_key, self.consumer_group, message_id)
                return
            
            # Parse timestamp
            try:
                if timestamp_str:
                    # Convert ISO timestamp to epoch seconds
                    from datetime import datetime
                    timestamp = int(datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp())
                else:
                    timestamp = int(time.time())
            except ValueError:
                timestamp = int(time.time())
            
            # Check if embedding already exists
            if await self.embedding_already_exists(thought_id, instance):
                logger.debug(f"Embedding already exists for {thought_id}, skipping")
                await self.redis.xack(self.stream_key, self.consumer_group, message_id)
                return
            
            # Create embedding task
            task = EmbeddingTask(
                thought_id=thought_id,
                instance=instance,
                content="",  # Will fetch from Redis
                timestamp=timestamp,
                status=EmbeddingStatus.PENDING
            )
            
            # Process immediately
            success = await self.process_embedding_task(task)
            
            if success:
                # Acknowledge message only on success
                await self.redis.xack(self.stream_key, self.consumer_group, message_id)
                logger.info(f"Successfully processed embedding for {thought_id}")
            else:
                # Leave message in stream for retry
                logger.warning(f"Failed to process embedding for {thought_id}, will retry")
            
        except Exception as e:
            logger.error(f"Event processing error for {message_id}: {e}")
    
    async def embedding_already_exists(self, thought_id: str, instance: str) -> bool:
        """Check if embedding already exists for this thought"""
        try:
            key = f"{instance}:embeddings:{thought_id}"
            exists = await self.redis.exists(key)
            return bool(exists)
        except Exception as e:
            logger.error(f"Error checking embedding existence: {e}")
            return False
    
    async def process_embedding_task(self, task: EmbeddingTask) -> bool:
        """Process a single embedding task"""
        try:
            # Update status
            task.status = EmbeddingStatus.PROCESSING
            await self.update_task_status(task)
            
            # Fetch thought content if not provided
            if not task.content:
                task.content = await self.fetch_thought_content(task.thought_id, task.instance)
                if not task.content:
                    raise Exception("Failed to fetch thought content")
            
            # Rate limiting
            await asyncio.sleep(self.rate_limit_delay)
            
            # Generate embedding synchronously (SimpleEmbeddingService is sync)
            success = await asyncio.get_event_loop().run_in_executor(
                None,
                self.embedding_service.store_thought_embedding,
                task.thought_id,
                task.content,
                task.timestamp
            )
            
            if success:
                task.status = EmbeddingStatus.COMPLETED
                self.processed_count += 1
                logger.info(f"Generated embedding for thought {task.thought_id}")
                return True
            else:
                raise Exception("Embedding generation returned False")
                
        except Exception as e:
            task.status = EmbeddingStatus.FAILED
            task.last_error = str(e)
            task.retry_count += 1
            self.failed_count += 1
            
            logger.error(f"Embedding task failed for {task.thought_id}: {e}")
            
            if task.retry_count <= self.max_retries:
                task.status = EmbeddingStatus.RETRYING
                await self.schedule_retry(task)
                logger.info(f"Scheduled retry {task.retry_count}/{self.max_retries} for {task.thought_id}")
            else:
                await self.move_to_dead_letter_queue(task)
                logger.error(f"Max retries exceeded for {task.thought_id}, moved to dead letter queue")
                
        finally:
            await self.update_task_status(task)
            
        return False
    
    async def fetch_thought_content(self, thought_id: str, instance: str) -> str:
        """Fetch thought content from Redis"""
        try:
            key = f"{instance}:Thoughts:{thought_id}"
            thought_data_str = await self.redis.get(key)
            
            if thought_data_str:
                thought_data = json.loads(thought_data_str)
                return thought_data.get('thought', '')
            else:
                logger.error(f"Thought not found in Redis: {key}")
                return ""
                
        except Exception as e:
            logger.error(f"Error fetching thought content for {thought_id}: {e}")
            return ""
    
    async def update_task_status(self, task: EmbeddingTask):
        """Update task status in Redis"""
        try:
            status_key = f"embedding_queue:{task.thought_id}"
            status_data = {
                "status": task.status.value,
                "retry_count": str(task.retry_count),
                "last_error": task.last_error or "",
                "updated_at": str(time.time()),
                "created_at": str(task.created_at)
            }
            
            for field, value in status_data.items():
                await self.redis.hset(status_key, field, value)
            await self.redis.expire(status_key, 86400)  # 24 hour TTL
        except Exception as e:
            logger.error(f"Error updating task status: {e}")
    
    async def schedule_retry(self, task: EmbeddingTask):
        """Schedule task for retry"""
        try:
            retry_delay = min(60 * (2 ** task.retry_count), 300)  # Exponential backoff, max 5 min
            retry_time = time.time() + retry_delay
            
            retry_key = f"embedding_retry_queue:{int(retry_time)}:{task.thought_id}"
            task_data = json.dumps(asdict(task), default=str)
            await self.redis.set(retry_key, task_data, ex=3600)  # 1 hour TTL
            
            logger.info(f"Scheduled retry for {task.thought_id} in {retry_delay} seconds")
        except Exception as e:
            logger.error(f"Error scheduling retry: {e}")
    
    async def move_to_dead_letter_queue(self, task: EmbeddingTask):
        """Move failed task to dead letter queue"""
        try:
            dlq_key = f"embedding_dlq:{task.thought_id}"
            task_data = json.dumps(asdict(task), default=str)
            await self.redis.set(dlq_key, task_data)
            await self.redis.expire(dlq_key, 604800)  # 7 days TTL
            
            logger.error(f"Moved {task.thought_id} to dead letter queue")
        except Exception as e:
            logger.error(f"Error moving to dead letter queue: {e}")
    
    async def retry_processor(self):
        """Process retry queue"""
        logger.info("Starting retry processor...")
        
        while True:
            try:
                current_time = int(time.time())
                
                # Look for retry keys that are ready to process
                pattern = f"embedding_retry_queue:*"
                keys = await self.redis.keys(pattern)
                
                for key in keys:
                    try:
                        # Extract retry time from key
                        key_parts = key.split(':')
                        if len(key_parts) >= 3:
                            retry_time = int(key_parts[2])
                            
                            if current_time >= retry_time:
                                # Time to retry
                                task_data_str = await self.redis.get(key)
                                if task_data_str:
                                    task_data = json.loads(task_data_str)
                                    task = EmbeddingTask(**task_data)
                                    
                                    success = await self.process_embedding_task(task)
                                    if success or task.retry_count > self.max_retries:
                                        await self.redis.delete(key)
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Invalid retry key format: {key}, deleting")
                        await self.redis.delete(key)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Retry processor error: {e}")
                await asyncio.sleep(60)
    
    async def metrics_reporter(self):
        """Report service metrics"""
        logger.info("Starting metrics reporter...")
        
        while True:
            try:
                metrics = await self.collect_metrics()
                await self.publish_metrics(metrics)
                self.last_metrics_report = time.time()
                await asyncio.sleep(60)  # Report every minute
                
            except Exception as e:
                logger.error(f"Metrics reporter error: {e}")
                await asyncio.sleep(60)
    
    async def collect_metrics(self) -> Dict:
        """Collect embedding service metrics"""
        try:
            # Count tasks by status
            queue_pattern = "embedding_queue:*"
            queue_keys = await self.redis.keys(queue_pattern)
            
            pending = 0
            processing = 0
            completed = 0
            failed = 0
            
            for key in queue_keys:
                status_data = await self.redis.hget(key, "status")
                if status_data == "pending":
                    pending += 1
                elif status_data == "processing":
                    processing += 1
                elif status_data == "completed":
                    completed += 1
                elif status_data == "failed":
                    failed += 1
            
            # Count retry queue
            retry_keys = await self.redis.keys("embedding_retry_queue:*")
            retry_count = len(retry_keys)
            
            # Count dead letter queue
            dlq_keys = await self.redis.keys("embedding_dlq:*")
            dlq_count = len(dlq_keys)
            
            return {
                "timestamp": time.time(),
                "instance": self.instance,
                "consumer": self.consumer_name,
                "queue_pending": pending,
                "queue_processing": processing,
                "queue_completed": completed,
                "queue_failed": failed,
                "retry_queue": retry_count,
                "dead_letter_queue": dlq_count,
                "processed_total": self.processed_count,
                "failed_total": self.failed_count,
                "uptime_seconds": time.time() - self.last_metrics_report
            }
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return {"error": str(e)}
    
    async def publish_metrics(self, metrics: Dict):
        """Publish metrics to Redis"""
        try:
            metrics_key = f"embedding_service_metrics:{self.consumer_name}"
            await self.redis.set(metrics_key, json.dumps(metrics), ex=300)  # 5 minute TTL
            
            # Also log key metrics
            if "error" not in metrics:
                logger.info(
                    f"Metrics: processed={metrics['processed_total']}, "
                    f"failed={metrics['failed_total']}, "
                    f"pending={metrics['queue_pending']}, "
                    f"retry={metrics['retry_queue']}, "
                    f"dlq={metrics['dead_letter_queue']}"
                )
        except Exception as e:
            logger.error(f"Error publishing metrics: {e}")
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            logger.info("Cleaning up resources...")
            await self.redis.aclose()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def main():
    """Main entry point"""
    # Get configuration from environment
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    instance = os.getenv('INSTANCE_ID', 'Claude')
    
    # Get OpenAI API key
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    # If not in environment, try Redis
    if not openai_api_key:
        try:
            sync_redis = redis.from_url(redis_url.replace('redis://', 'redis://'), decode_responses=True)
            openai_api_key = sync_redis.get('config:openai_api_key')
            if openai_api_key:
                logger.info(f"Retrieved OPENAI_API_KEY from Redis ({len(openai_api_key)} chars)")
            sync_redis.close()
        except Exception as e:
            logger.error(f"Error retrieving API key from Redis: {e}")
    
    if not openai_api_key:
        logger.error("Error: OPENAI_API_KEY not found in environment or Redis")
        sys.exit(1)
    
    # Create and start service
    service = BackgroundEmbeddingService(redis_url, openai_api_key, instance)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
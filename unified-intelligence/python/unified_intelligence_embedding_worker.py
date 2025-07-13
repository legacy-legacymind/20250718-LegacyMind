#!/usr/bin/env python3
"""
Unified Intelligence Embedding Worker

Background service that processes embedding requests from Redis streams,
generates embeddings using OpenAI text-embedding-3-small, and stores
vectors in RedisVL index for semantic search capabilities.

Supports multiple Claude instances: CC, CCI, DT
Uses asyncio for concurrent processing with proper error handling.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import redis.asyncio as redis
from redisvl.extensions.cache.llm import SemanticCache
from redisvl.utils.vectorize import OpenAITextVectorizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/samuelatagana/Projects/LegacyMind/unified-intelligence/logs/embedding_worker.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class EmbeddingWorker:
    """Async worker for processing embedding requests via Redis streams."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", openai_api_key: str = None, 
                 password: str = None):
        self.redis_url = redis_url
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.password = password or "legacymind_redis_pass"
        self.redis_client = None
        self.vectorizer = None
        self.semantic_cache = None
        self.running = False
        
        # Stream configuration
        self.embedding_stream = "unified_intelligence:embedding_requests"
        self.consumer_group = "embedding_workers"
        self.consumer_name = f"worker_{int(time.time())}"
        
        # Supported instances
        self.instances = ["CC", "CCI", "DT"]
        
    async def initialize(self):
        """Initialize Redis connection and vectorizer."""
        try:
            self.redis_client = redis.from_url(
                self.redis_url, 
                password=self.password,
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("✅ Connected to Redis")
            
            # Initialize OpenAI vectorizer
            if not self.openai_api_key:
                raise ValueError("OpenAI API key required")
                
            self.vectorizer = OpenAITextVectorizer(
                model="text-embedding-3-small",  # 1536 dims, $0.02/1M tokens
                api_config={"api_key": self.openai_api_key}
            )
            
            # Initialize semantic cache for performance optimization
            self.semantic_cache = SemanticCache(
                name="unified_intelligence_cache",
                redis_url=self.redis_url,
                password=self.password,
                distance_threshold=0.1,  # Cache hits for very similar queries
                ttl=3600  # 1 hour cache TTL
            )
            
            logger.info("✅ Initialized vectorizer and semantic cache")
            
            # Create consumer group if it doesn't exist
            try:
                await self.redis_client.xgroup_create(
                    self.embedding_stream, 
                    self.consumer_group, 
                    id="0", 
                    mkstream=True
                )
                logger.info(f"✅ Created consumer group: {self.consumer_group}")
            except redis.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    logger.info(f"✅ Consumer group {self.consumer_group} already exists")
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            raise
    
    async def process_embedding_request(self, message_id: str, fields: Dict[str, str]):
        """Process a single embedding request."""
        try:
            # Parse request
            instance = fields.get("instance", "").upper()
            text = fields.get("text", "")
            thought_id = fields.get("thought_id", "")
            chain_id = fields.get("chain_id")
            
            if not instance or instance not in self.instances:
                raise ValueError(f"Invalid instance: {instance}. Must be one of {self.instances}")
            
            if not text.strip():
                raise ValueError("Empty text provided for embedding")
            
            logger.info(f"🔄 Processing embedding for {instance}: {thought_id}")
            
            # Check semantic cache first (15x performance improvement)
            cached_result = await self.semantic_cache.check(prompt=text)
            if cached_result:
                logger.info(f"⚡ Cache hit for {instance}: {thought_id}")
                vector = cached_result[0]["vector"]
            else:
                # Generate embedding
                vector = await self.vectorizer.aembed(text)
                
                # Store in cache for future use
                await self.semantic_cache.store(
                    prompt=text,
                    response=json.dumps({"vector": vector, "model": "text-embedding-3-small"}),
                    vector=vector
                )
                logger.info(f"🎯 Generated embedding for {instance}: {thought_id}")
            
            # Store vector in instance-specific index
            vector_key = f"{instance}/vectors/{thought_id}"
            vector_data = {
                "vector": vector,
                "text": text,
                "instance": instance,
                "thought_id": thought_id,
                "chain_id": chain_id,
                "timestamp": datetime.utcnow().isoformat(),
                "model": "text-embedding-3-small",
                "dimensions": len(vector)
            }
            
            # Store using Redis JSON
            await self.redis_client.json().set(vector_key, "$", vector_data)
            
            # Add to vector index for search
            await self.add_to_vector_index(instance, thought_id, vector, {
                "text": text,
                "instance": instance,
                "chain_id": chain_id or "",
                "timestamp": vector_data["timestamp"]
            })
            
            # Acknowledge message processing
            await self.redis_client.xack(
                self.embedding_stream, 
                self.consumer_group, 
                message_id
            )
            
            logger.info(f"✅ Completed embedding for {instance}: {thought_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to process {message_id}: {e}")
            # Message will remain in pending state for retry
            
    async def add_to_vector_index(self, instance: str, thought_id: str, 
                                 vector: List[float], metadata: Dict[str, str]):
        """Add vector to RedisVL search index."""
        try:
            # Use consistent naming with vector service
            index_key = f"{instance.lower()}_thoughts_index"
            doc_key = f"{instance}/vectors/{thought_id}"
            
            # Create document for vector index
            doc = {
                "id": thought_id,
                "vector": vector,
                **metadata
            }
            
            # Add to search index (this may need adjustment based on actual RedisVL schema)
            # For now, store as JSON with vector field for retrieval
            await self.redis_client.json().set(doc_key, "$", doc)
            
            logger.debug(f"📝 Added {thought_id} to {index_key}")
            
        except Exception as e:
            logger.error(f"❌ Failed to add {thought_id} to vector index: {e}")
    
    async def process_messages(self):
        """Main message processing loop."""
        logger.info(f"🚀 Starting message processing as {self.consumer_name}")
        
        while self.running:
            try:
                # Read from stream with consumer group
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.embedding_stream: ">"},
                    count=10,  # Process up to 10 messages at once
                    block=1000  # Block for 1 second
                )
                
                if messages:
                    # Process messages concurrently
                    tasks = []
                    for stream, stream_messages in messages:
                        for message_id, fields in stream_messages:
                            task = asyncio.create_task(
                                self.process_embedding_request(message_id, fields)
                            )
                            tasks.append(task)
                    
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                        
            except asyncio.CancelledError:
                logger.info("🛑 Message processing cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in message processing loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def handle_pending_messages(self):
        """Process any pending messages from previous runs."""
        try:
            # Get pending messages for this consumer
            pending = await self.redis_client.xpending_range(
                self.embedding_stream,
                self.consumer_group,
                min="-",
                max="+",
                count=100
            )
            
            if pending:
                logger.info(f"📥 Found {len(pending)} pending messages")
                
                for msg_info in pending:
                    message_id = msg_info["message_id"]
                    
                    # Get message content
                    messages = await self.redis_client.xrange(
                        self.embedding_stream,
                        min=message_id,
                        max=message_id
                    )
                    
                    if messages:
                        _, fields = messages[0]
                        await self.process_embedding_request(message_id, fields)
                        
        except Exception as e:
            logger.error(f"❌ Error processing pending messages: {e}")
    
    async def run(self):
        """Main worker run loop."""
        self.running = True
        
        try:
            await self.initialize()
            await self.handle_pending_messages()
            await self.process_messages()
            
        except KeyboardInterrupt:
            logger.info("🛑 Received shutdown signal")
        except Exception as e:
            logger.error(f"❌ Worker error: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Clean shutdown of worker."""
        logger.info("🔄 Shutting down worker...")
        self.running = False
        
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✅ Redis connection closed")


async def main():
    """Main entry point."""
    # Configuration
    REDIS_URL = "redis://localhost:6379"
    OPENAI_API_KEY = "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"
    
    # Create worker
    worker = EmbeddingWorker(
        redis_url=REDIS_URL,
        openai_api_key=OPENAI_API_KEY
    )
    
    # Setup signal handling for graceful shutdown
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("🔔 Received shutdown signal")
        asyncio.create_task(worker.shutdown())
    
    for sig in [signal.SIGTERM, signal.SIGINT]:
        loop.add_signal_handler(sig, signal_handler)
    
    # Run worker
    await worker.run()


if __name__ == "__main__":
    # Ensure log directory exists
    os.makedirs("/Users/samuelatagana/Projects/LegacyMind/unified-intelligence/logs", exist_ok=True)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Worker stopped by user")
    except Exception as e:
        logger.error(f"💥 Worker crashed: {e}")
        sys.exit(1)
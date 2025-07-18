#!/usr/bin/env python3
"""
Embedding Recovery Service for Phase 3
Automatically reprocesses Groq fallback embeddings with OpenAI when it's back online
"""

import os
import sys
import asyncio
import redis
import json
import time
import struct
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from dual_storage_service import DualStorageEmbeddingService


class EmbeddingRecoveryService:
    """
    Service to automatically upgrade Groq fallback embeddings to OpenAI when available
    """
    
    def __init__(self, redis_url: str, openai_api_key: str = None):
        self.redis_url = redis_url
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.openai_api_key = openai_api_key
        
        # Initialize OpenAI service if available
        self.openai_service = None
        if openai_api_key:
            try:
                self.openai_service = DualStorageEmbeddingService(redis_url, openai_api_key)
                print("✅ OpenAI service initialized for recovery")
            except Exception as e:
                print(f"⚠️ OpenAI service not available: {e}")
        
        # Recovery metrics
        self.recovery_stats = {
            'fallback_embeddings_found': 0,
            'recovery_attempts': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'api_errors': 0,
            'last_recovery_run': None
        }
        
        # Recovery queue
        self.recovery_queue_key = "embedding_recovery_queue"
        self.recovery_status_key = "embedding_recovery_status"
        
        # Configuration
        self.batch_size = 10  # Process in small batches
        self.recovery_interval = 300  # 5 minutes between recovery runs
        self.max_retries = 3
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def is_openai_available(self) -> bool:
        """Check if OpenAI service is available"""
        return self.openai_service is not None
    
    async def queue_for_recovery(self, thought_id: str, instance: str, content: str, metadata: Dict = None):
        """
        Queue a fallback embedding for recovery when OpenAI is back online
        """
        try:
            recovery_item = {
                'thought_id': thought_id,
                'instance': instance,
                'content': content,
                'metadata': metadata or {},
                'queued_at': datetime.utcnow().isoformat(),
                'retry_count': 0,
                'provider': 'groq_fallback'
            }
            
            # Add to recovery queue
            self.redis.lpush(self.recovery_queue_key, json.dumps(recovery_item))
            
            # Track in status
            self.redis.hset(
                self.recovery_status_key,
                thought_id,
                json.dumps({
                    'status': 'queued',
                    'instance': instance,
                    'queued_at': datetime.utcnow().isoformat()
                })
            )
            
            self.logger.info(f"Queued {thought_id} for recovery")
            
        except Exception as e:
            self.logger.error(f"Failed to queue {thought_id} for recovery: {e}")
    
    async def find_fallback_embeddings(self) -> List[Dict]:
        """
        Find all embeddings that were generated with Groq fallback
        """
        fallback_embeddings = []
        
        try:
            # Check all instances
            instances = ["CC", "CCI", "CCD", "CCS", "DT", "Claude"]
            
            for instance in instances:
                # Get embedding metadata
                metadata_key = f"embedding_metadata:{instance}"
                metadata_items = self.redis.hgetall(metadata_key)
                
                for thought_id, metadata_json in metadata_items.items():
                    try:
                        metadata = json.loads(metadata_json)
                        
                        # Check if this was a fallback embedding
                        if metadata.get('provider') == 'groq_fallback':
                            # Get the original content
                            thought_key = f"thoughts:{instance}"
                            thought_data = self.redis.hget(thought_key, thought_id)
                            
                            if thought_data:
                                thought = json.loads(thought_data)
                                content = thought.get('thought', thought.get('content', ''))
                                
                                if content:
                                    fallback_embeddings.append({
                                        'thought_id': thought_id,
                                        'instance': instance,
                                        'content': content,
                                        'metadata': metadata,
                                        'original_timestamp': metadata.get('timestamp')
                                    })
                    except Exception as e:
                        self.logger.warning(f"Error processing metadata for {thought_id}: {e}")
            
            self.recovery_stats['fallback_embeddings_found'] = len(fallback_embeddings)
            self.logger.info(f"Found {len(fallback_embeddings)} fallback embeddings")
            
        except Exception as e:
            self.logger.error(f"Error finding fallback embeddings: {e}")
        
        return fallback_embeddings
    
    async def recover_embedding(self, item: Dict) -> bool:
        """
        Recover a single embedding by regenerating with OpenAI
        """
        if not self.is_openai_available():
            return False
        
        thought_id = item['thought_id']
        instance = item['instance']
        content = item['content']
        
        try:
            self.recovery_stats['recovery_attempts'] += 1
            
            # Generate new embedding with OpenAI
            result = await self.openai_service.generate_embedding_with_cache(content)
            
            if not result.embedding:
                self.logger.error(f"Failed to generate OpenAI embedding for {thought_id}")
                self.recovery_stats['failed_recoveries'] += 1
                return False
            
            # Store the new embedding (replacing the fallback one)
            binary_data = struct.pack(f'{len(result.embedding)}f', *result.embedding)
            
            # Update Redis with new embedding
            pipeline = self.redis.pipeline()
            
            # Replace binary embedding
            pipeline.hset(f"embeddings:{instance}", thought_id, binary_data)
            
            # Update metadata
            new_metadata = {
                'thought_id': thought_id,
                'instance': instance,
                'timestamp': datetime.utcnow().isoformat(),
                'vector_size': len(result.embedding),
                'content_hash': item.get('metadata', {}).get('content_hash', ''),
                'provider': 'openai',
                'recovered_from': 'groq_fallback',
                'recovery_timestamp': datetime.utcnow().isoformat(),
                'original_timestamp': item.get('original_timestamp')
            }
            
            pipeline.hset(
                f"embedding_metadata:{instance}",
                thought_id,
                json.dumps(new_metadata)
            )
            
            # Update recovery metrics
            pipeline.hincrby("embedding_metrics", "recovered_embeddings", 1)
            pipeline.hincrby("embedding_metrics", f"{instance}_recovered", 1)
            
            pipeline.execute()
            
            # Update recovery status
            self.redis.hset(
                self.recovery_status_key,
                thought_id,
                json.dumps({
                    'status': 'recovered',
                    'instance': instance,
                    'recovered_at': datetime.utcnow().isoformat(),
                    'original_provider': 'groq_fallback'
                })
            )
            
            self.recovery_stats['successful_recoveries'] += 1
            self.logger.info(f"Successfully recovered {thought_id} from Groq to OpenAI")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error recovering {thought_id}: {e}")
            self.recovery_stats['failed_recoveries'] += 1
            self.recovery_stats['api_errors'] += 1
            return False
    
    async def process_recovery_queue(self):
        """
        Process the recovery queue in batches
        """
        if not self.is_openai_available():
            self.logger.warning("OpenAI not available, skipping recovery queue processing")
            return
        
        processed = 0
        
        try:
            # Process items from queue
            while processed < self.batch_size:
                # Get next item from queue
                item_json = self.redis.rpop(self.recovery_queue_key)
                if not item_json:
                    break
                
                try:
                    item = json.loads(item_json)
                    
                    # Check retry count
                    if item.get('retry_count', 0) >= self.max_retries:
                        self.logger.warning(f"Max retries exceeded for {item['thought_id']}")
                        continue
                    
                    # Attempt recovery
                    success = await self.recover_embedding(item)
                    
                    if not success:
                        # Re-queue with incremented retry count
                        item['retry_count'] = item.get('retry_count', 0) + 1
                        item['last_attempt'] = datetime.utcnow().isoformat()
                        
                        if item['retry_count'] < self.max_retries:
                            self.redis.lpush(self.recovery_queue_key, json.dumps(item))
                    
                    processed += 1
                    
                except Exception as e:
                    self.logger.error(f"Error processing recovery item: {e}")
                    processed += 1
            
            if processed > 0:
                self.logger.info(f"Processed {processed} recovery items")
                
        except Exception as e:
            self.logger.error(f"Error processing recovery queue: {e}")
    
    async def run_recovery_scan(self):
        """
        Scan for fallback embeddings and queue them for recovery
        """
        self.logger.info("Starting recovery scan...")
        
        # Find all fallback embeddings
        fallback_embeddings = await self.find_fallback_embeddings()
        
        # Queue them for recovery
        for embedding in fallback_embeddings:
            await self.queue_for_recovery(
                embedding['thought_id'],
                embedding['instance'],
                embedding['content'],
                embedding['metadata']
            )
        
        self.logger.info(f"Queued {len(fallback_embeddings)} embeddings for recovery")
    
    async def recovery_loop(self):
        """
        Main recovery loop that runs periodically
        """
        self.logger.info("Starting embedding recovery service...")
        
        while True:
            try:
                self.recovery_stats['last_recovery_run'] = datetime.utcnow().isoformat()
                
                # Process existing recovery queue
                await self.process_recovery_queue()
                
                # Look for new fallback embeddings to recover
                await self.run_recovery_scan()
                
                # Wait before next run
                await asyncio.sleep(self.recovery_interval)
                
            except Exception as e:
                self.logger.error(f"Error in recovery loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    def get_recovery_stats(self) -> Dict:
        """Get recovery service statistics"""
        stats = self.recovery_stats.copy()
        
        # Add queue status
        try:
            queue_length = self.redis.llen(self.recovery_queue_key)
            stats['queue_length'] = queue_length
            
            # Get recovery status summary
            status_items = self.redis.hgetall(self.recovery_status_key)
            
            status_summary = {
                'queued': 0,
                'recovered': 0,
                'failed': 0
            }
            
            for status_json in status_items.values():
                try:
                    status = json.loads(status_json)
                    status_type = status.get('status', 'unknown')
                    if status_type in status_summary:
                        status_summary[status_type] += 1
                except:
                    pass
            
            stats['status_summary'] = status_summary
            
        except Exception as e:
            self.logger.error(f"Error getting recovery stats: {e}")
        
        return stats


async def main():
    """Test the recovery service"""
    # Get configuration
    redis_password = os.getenv("REDIS_PASSWORD", "")
    redis_url = f"redis://:{redis_password}@localhost:6379" if redis_password else "redis://localhost:6379"
    
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if not openai_api_key:
        print("❌ No OpenAI API key found - recovery service disabled")
        return
    
    # Initialize recovery service
    recovery_service = EmbeddingRecoveryService(redis_url, openai_api_key)
    
    # Run one-time recovery scan
    print("🔄 Running one-time recovery scan...")
    await recovery_service.run_recovery_scan()
    await recovery_service.process_recovery_queue()
    
    # Show stats
    stats = recovery_service.get_recovery_stats()
    print(f"📊 Recovery stats: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
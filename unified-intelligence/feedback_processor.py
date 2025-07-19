#!/usr/bin/env python3.11
"""
Feedback Event Processor - Phase 2 Implementation
Processes feedback events from Redis Streams to improve semantic search quality
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any
import redis
from datetime import datetime

# Import Phase 2 components
from relevance_calculator import RelevanceCalculator
from tag_index_manager import TagIndexManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FeedbackProcessor:
    """
    Processes feedback events from Redis Streams to improve semantic search quality.
    
    Phase 2 Implementation:
    - Consumer group setup
    - Enhanced event processing with relevance calculations
    - Tag index management
    - Comprehensive feedback analysis
    - Event acknowledgment
    - Advanced monitoring
    """
    
    def __init__(self, redis_url: str = None, consumer_group: str = "feedback_processor"):
        """Initialize the feedback processor."""
        self.redis_url = redis_url or self._get_redis_url()
        self.consumer_group = consumer_group
        self.consumer_name = f"feedback_processor_{int(time.time())}"
        self.client = None
        self.running = False
        
        # Phase 2: Initialize processing components
        self.relevance_calculator = RelevanceCalculator(redis_url)
        self.tag_manager = TagIndexManager(redis_url)
        
        # Event type handlers
        self.event_handlers = {
            'thought_created': self._handle_thought_created,
            'search_performed': self._handle_search_performed,
            'thought_accessed': self._handle_thought_accessed,
            'feedback_provided': self._handle_feedback_provided,
        }
        
        # Statistics
        self.stats = {
            'events_processed': 0,
            'events_failed': 0,
            'start_time': None,
            'last_processed': None,
            'relevance_updates': 0,
            'tag_operations': 0,
            'feedback_processed': 0,
        }
    
    def _get_redis_url(self) -> str:
        """Get Redis URL from environment."""
        password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        return f"redis://:{password}@localhost:6379/0"
    
    async def initialize(self):
        """Initialize Redis connection and consumer groups."""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            
            # Test connection
            await asyncio.to_thread(self.client.ping)
            logger.info("✅ Redis connection established")
            
            # Phase 2: Initialize processing components
            await self.relevance_calculator.initialize()
            await self.tag_manager.initialize()
            logger.info("✅ Processing components initialized")
            
            # Setup consumer groups for all instances
            await self._setup_consumer_groups()
            
            # Log initialization
            self.stats['start_time'] = datetime.now()
            logger.info(f"🚀 Feedback processor initialized: {self.consumer_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            raise
    
    async def _setup_consumer_groups(self):
        """Create consumer groups for all federation instances."""
        instances = ['CC', 'CCD', 'CCI']  # Federation instances
        
        for instance in instances:
            stream_key = f"{instance}:feedback_events"
            
            try:
                # Create consumer group (start from beginning for Phase 1)
                await asyncio.to_thread(
                    self.client.xgroup_create,
                    stream_key,
                    self.consumer_group,
                    id='0',
                    mkstream=True
                )
                logger.info(f"✅ Created consumer group for {instance}")
                
            except redis.RedisError as e:
                if "BUSYGROUP" in str(e):
                    logger.info(f"📌 Consumer group already exists for {instance}")
                else:
                    logger.error(f"❌ Failed to create consumer group for {instance}: {e}")
                    raise
    
    async def start_processing(self):
        """Start the main event processing loop."""
        self.running = True
        logger.info("🔄 Starting feedback event processing...")
        
        while self.running:
            try:
                await self._process_events()
                await asyncio.sleep(1)  # Brief pause between cycles
                
            except Exception as e:
                logger.error(f"❌ Error in processing loop: {e}")
                self.stats['events_failed'] += 1
                await asyncio.sleep(5)  # Longer pause on error
    
    async def _process_events(self):
        """Process events from all federation instances."""
        instances = ['CC', 'CCD', 'CCI']
        
        for instance in instances:
            stream_key = f"{instance}:feedback_events"
            
            try:
                # Check for pending messages first (recovery)
                pending_messages = await self._read_pending_messages(stream_key)
                
                if pending_messages:
                    await self._process_messages(instance, pending_messages)
                
                # Read new messages
                new_messages = await self._read_new_messages(stream_key)
                
                if new_messages:
                    await self._process_messages(instance, new_messages)
                    
            except Exception as e:
                logger.error(f"❌ Error processing {instance} events: {e}")
                self.stats['events_failed'] += 1
    
    async def _read_pending_messages(self, stream_key: str) -> List[Dict]:
        """Read pending messages for recovery."""
        try:
            # Read pending messages for this consumer
            result = await asyncio.to_thread(
                self.client.xreadgroup,
                self.consumer_group,
                self.consumer_name,
                {stream_key: '0'},
                count=10,
                block=None
            )
            
            messages = []
            if result:
                for stream_name, stream_messages in result:
                    for message_id, fields in stream_messages:
                        messages.append({
                            'id': message_id,
                            'fields': fields,
                            'stream': stream_name
                        })
            
            if messages:
                logger.info(f"📥 Found {len(messages)} pending messages in {stream_key}")
                
            return messages
            
        except Exception as e:
            logger.error(f"❌ Error reading pending messages from {stream_key}: {e}")
            return []
    
    async def _read_new_messages(self, stream_key: str) -> List[Dict]:
        """Read new messages from stream."""
        try:
            # Read new messages with blocking
            result = await asyncio.to_thread(
                self.client.xreadgroup,
                self.consumer_group,
                self.consumer_name,
                {stream_key: '>'},
                count=10,
                block=1000  # 1 second timeout
            )
            
            messages = []
            if result:
                for stream_name, stream_messages in result:
                    for message_id, fields in stream_messages:
                        messages.append({
                            'id': message_id,
                            'fields': fields,
                            'stream': stream_name
                        })
            
            return messages
            
        except Exception as e:
            logger.error(f"❌ Error reading new messages from {stream_key}: {e}")
            return []
    
    async def _process_messages(self, instance: str, messages: List[Dict]):
        """Process a batch of messages."""
        for message in messages:
            try:
                await self._process_single_message(instance, message)
                
                # Acknowledge message
                await asyncio.to_thread(
                    self.client.xack,
                    message['stream'],
                    self.consumer_group,
                    message['id']
                )
                
                self.stats['events_processed'] += 1
                self.stats['last_processed'] = datetime.now()
                
            except Exception as e:
                logger.error(f"❌ Error processing message {message['id']}: {e}")
                self.stats['events_failed'] += 1
    
    async def _process_single_message(self, instance: str, message: Dict):
        """Process a single feedback event message."""
        try:
            fields = message['fields']
            event_type = fields.get('event_type')
            
            if not event_type:
                logger.warning(f"⚠️ Message {message['id']} missing event_type")
                return
            
            # Get event handler
            handler = self.event_handlers.get(event_type)
            if not handler:
                logger.warning(f"⚠️ No handler for event type: {event_type}")
                return
            
            # Parse event data
            event_data = {}
            for key, value in fields.items():
                if key != 'event_type':
                    try:
                        # Try to parse as JSON
                        event_data[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        # Store as string
                        event_data[key] = value
            
            # Process event
            await handler(instance, event_data)
            
            logger.debug(f"✅ Processed {event_type} event from {instance}")
            
        except Exception as e:
            logger.error(f"❌ Error processing single message: {e}")
            raise
    
    # Event Handlers (Phase 2 - Enhanced Implementation)
    
    async def _handle_thought_created(self, instance: str, data: Dict):
        """Handle thought creation event with metadata processing."""
        thought_id = data.get('thought_id')
        importance = data.get('importance', 5)
        tags = data.get('tags', [])
        content = data.get('content', '')
        
        logger.info(f"🧠 Thought created: {instance}:{thought_id} (importance: {importance})")
        
        try:
            # Phase 2: Store metadata and update indexes
            
            # Extract additional tags from content if available
            if content:
                extracted_tags = await self.tag_manager.extract_tags_from_content(content)
                combined_tags = list(set(tags + extracted_tags))
                logger.debug(f"   Combined tags: {combined_tags}")
            else:
                combined_tags = tags
            
            # Update thought metadata with tags
            if combined_tags:
                await self.tag_manager._update_thought_tags(instance, thought_id, combined_tags)
                await self.tag_manager._update_tag_indexes(instance, thought_id, combined_tags)
                self.stats['tag_operations'] += 1
                logger.info(f"   Updated tag indexes with {len(combined_tags)} tags")
            
            # Store metadata for relevance calculation
            meta_key = f"{instance}:thought_meta:{thought_id}"
            metadata = {
                'importance': str(importance),
                'created_at': datetime.now().isoformat(),
                'tags': json.dumps(combined_tags),
                'tag_count': str(len(combined_tags))
            }
            
            # Add relevance tracking data
            if data.get('relevance'):
                metadata['relevance'] = str(data['relevance'])
            if data.get('category'):
                metadata['category'] = data['category']
            
            await asyncio.to_thread(
                self.client.hset,
                meta_key,
                mapping=metadata
            )
            
            logger.debug(f"✅ Stored metadata for thought {thought_id}")
            
        except Exception as e:
            logger.error(f"❌ Error processing thought creation: {e}")
            raise
    
    async def _handle_search_performed(self, instance: str, data: Dict):
        """Handle search performance event with pattern tracking."""
        search_id = data.get('search_id')
        query = data.get('query', '')
        results_count = data.get('results_count', 0)
        thought_ids = data.get('thought_ids', [])
        
        logger.info(f"🔍 Search performed: {instance} (id: {search_id}, results: {results_count})")
        
        try:
            # Phase 2: Store search patterns and analyze quality
            
            # Store search session data
            search_key = f"{instance}:search_sessions:{search_id}"
            search_data = {
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'results_count': str(results_count),
                'thought_ids': json.dumps(thought_ids),
                'instance': instance
            }
            
            await asyncio.to_thread(
                self.client.hset,
                search_key,
                mapping=search_data
            )
            
            # Track query patterns for clustering
            query_key = f"{instance}:query_patterns"
            await asyncio.to_thread(
                self.client.zincrby,
                query_key,
                1,
                query.lower()[:100]  # Limit query length
            )
            
            # Track search quality metrics
            quality_key = f"{instance}:search_quality"
            await asyncio.to_thread(
                self.client.lpush,
                quality_key,
                json.dumps({
                    'search_id': search_id,
                    'query_length': len(query),
                    'results_count': results_count,
                    'timestamp': datetime.now().isoformat()
                })
            )
            
            # Limit quality metrics to last 1000 searches
            await asyncio.to_thread(self.client.ltrim, quality_key, 0, 999)
            
            logger.debug(f"✅ Stored search patterns for {search_id}")
            
            if query:
                logger.info(f"   Query: {query[:100]}...")
                
        except Exception as e:
            logger.error(f"❌ Error processing search event: {e}")
            raise
    
    async def _handle_thought_accessed(self, instance: str, data: Dict):
        """Handle thought access event with relevance scoring."""
        thought_id = data.get('thought_id')
        search_id = data.get('search_id')
        action = data.get('action', 'viewed')
        dwell_time = data.get('dwell_time', 0)
        
        logger.info(f"👁️ Thought accessed: {instance}:{thought_id} (action: {action})")
        
        try:
            # Phase 2: Update relevance scores and track usage patterns
            
            # Store access event for relevance calculation
            access_key = f"{instance}:thought_access:{thought_id}"
            access_data = {
                'timestamp': datetime.now().isoformat(),
                'action': action,
                'search_id': search_id or 'direct',
                'dwell_time': str(dwell_time)
            }
            
            await asyncio.to_thread(
                self.client.lpush,
                access_key,
                json.dumps(access_data)
            )
            
            # Limit to last 100 access events per thought
            await asyncio.to_thread(self.client.ltrim, access_key, 0, 99)
            
            # Update search session with access data if from search
            if search_id:
                session_key = f"{instance}:search_sessions:{search_id}"
                session_access_key = f"{session_key}:accessed"
                
                await asyncio.to_thread(
                    self.client.hset,
                    session_access_key,
                    thought_id,
                    json.dumps({
                        'action': action,
                        'timestamp': datetime.now().isoformat(),
                        'dwell_time': dwell_time
                    })
                )
            
            # Calculate updated relevance score
            relevance_metrics = await self.relevance_calculator.calculate_thought_relevance(thought_id, instance)
            
            if 'error' not in relevance_metrics:
                self.stats['relevance_updates'] += 1
                logger.debug(f"✅ Updated relevance score for {thought_id}: {relevance_metrics.get('relevance_score', 'N/A')}")
            else:
                logger.warning(f"⚠️ Failed to update relevance for {thought_id}: {relevance_metrics['error']}")
            
            # Track usage patterns for co-occurrence analysis
            if search_id:
                pattern_key = f"{instance}:usage_patterns:{search_id}"
                await asyncio.to_thread(
                    self.client.sadd,
                    pattern_key,
                    thought_id
                )
                # Expire pattern data after 7 days
                await asyncio.to_thread(self.client.expire, pattern_key, 604800)
            
            if search_id:
                logger.info(f"   From search: {search_id}")
                
        except Exception as e:
            logger.error(f"❌ Error processing thought access: {e}")
            raise
    
    async def _handle_feedback_provided(self, instance: str, data: Dict):
        """Handle explicit feedback event with relevance adjustment."""
        search_id = data.get('search_id')
        thought_id = data.get('thought_id')
        feedback = data.get('feedback', 'neutral')
        feedback_score = data.get('feedback_score', 0)
        
        logger.info(f"👍 Feedback provided: {instance} (search: {search_id}, feedback: {feedback})")
        
        try:
            # Phase 2: Apply feedback to relevance calculations
            
            # Store explicit feedback
            feedback_key = f"{instance}:explicit_feedback:{thought_id}"
            feedback_data = {
                'timestamp': datetime.now().isoformat(),
                'feedback': feedback,
                'search_id': search_id or 'direct',
                'score': str(feedback_score)
            }
            
            await asyncio.to_thread(
                self.client.lpush,
                feedback_key,
                json.dumps(feedback_data)
            )
            
            # Limit to last 50 feedback events per thought
            await asyncio.to_thread(self.client.ltrim, feedback_key, 0, 49)
            
            # Update search session with feedback
            if search_id:
                session_key = f"{instance}:search_sessions:{search_id}"
                session_feedback_key = f"{session_key}:feedback"
                
                await asyncio.to_thread(
                    self.client.hset,
                    session_feedback_key,
                    thought_id,
                    json.dumps({
                        'feedback': feedback,
                        'timestamp': datetime.now().isoformat(),
                        'score': feedback_score
                    })
                )
            
            # Apply immediate relevance boost/penalty
            if thought_id:
                relevance_metrics = await self.relevance_calculator.calculate_thought_relevance(thought_id, instance)
                
                if 'error' not in relevance_metrics:
                    self.stats['relevance_updates'] += 1
                    self.stats['feedback_processed'] += 1
                    
                    current_score = relevance_metrics.get('relevance_score', 1.0)
                    logger.info(f"✅ Applied feedback to {thought_id}: score = {current_score}")
                else:
                    logger.warning(f"⚠️ Failed to apply feedback for {thought_id}: {relevance_metrics['error']}")
            
            # Track feedback patterns for query improvement
            feedback_pattern_key = f"{instance}:feedback_patterns"
            pattern_data = {
                'feedback_type': feedback,
                'search_id': search_id,
                'timestamp': datetime.now().isoformat()
            }
            
            await asyncio.to_thread(
                self.client.lpush,
                feedback_pattern_key,
                json.dumps(pattern_data)
            )
            
            # Limit feedback patterns to last 1000 events
            await asyncio.to_thread(self.client.ltrim, feedback_pattern_key, 0, 999)
            
            if thought_id:
                logger.info(f"   Thought: {thought_id}")
                
        except Exception as e:
            logger.error(f"❌ Error processing feedback: {e}")
            raise
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive processor statistics."""
        uptime = None
        if self.stats['start_time']:
            uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        return {
            'consumer_name': self.consumer_name,
            'consumer_group': self.consumer_group,
            'events_processed': self.stats['events_processed'],
            'events_failed': self.stats['events_failed'],
            'relevance_updates': self.stats['relevance_updates'],
            'tag_operations': self.stats['tag_operations'],
            'feedback_processed': self.stats['feedback_processed'],
            'uptime_seconds': uptime,
            'last_processed': self.stats['last_processed'].isoformat() if self.stats['last_processed'] else None,
            'running': self.running,
            'processing_rate': round(self.stats['events_processed'] / max(1, uptime or 1), 2) if uptime else 0,
            'error_rate': round(self.stats['events_failed'] / max(1, self.stats['events_processed']), 3) if self.stats['events_processed'] else 0
        }
    
    async def stop(self):
        """Stop the processor."""
        self.running = False
        logger.info("🛑 Feedback processor stopped")
    
    def __del__(self):
        """Cleanup."""
        if self.client:
            self.client.close()

# Basic monitoring functions

async def get_stream_info(redis_url: str = None) -> Dict[str, Any]:
    """Get information about feedback streams."""
    redis_url = redis_url or f"redis://:{os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    info = {}
    instances = ['CC', 'CCD', 'CCI']
    
    for instance in instances:
        stream_key = f"{instance}:feedback_events"
        
        try:
            # Get stream length
            length = await asyncio.to_thread(client.xlen, stream_key)
            
            # Get consumer groups
            groups = await asyncio.to_thread(client.xinfo_groups, stream_key)
            
            info[instance] = {
                'stream_key': stream_key,
                'length': length,
                'groups': groups
            }
            
        except redis.RedisError as e:
            info[instance] = {
                'stream_key': stream_key,
                'error': str(e)
            }
    
    client.close()
    return info

async def main():
    """Main function for running the feedback processor."""
    processor = FeedbackProcessor()
    
    try:
        await processor.initialize()
        await processor.start_processing()
        
    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal")
        await processor.stop()
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        await processor.stop()
        raise

if __name__ == "__main__":
    asyncio.run(main())
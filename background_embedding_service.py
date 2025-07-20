#!/usr/bin/env python3
"""
Background Embedding Service
Automatically processes thoughts from Redis → OpenAI → Qdrant
Does NOT touch UI MCP - keeps it fast
"""

import redis
import openai
import json
import time
import logging
import asyncio
import os
import signal
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
from qdrant_client import QdrantClient, models
from qdrant_client.models import VectorParams, Distance, PointStruct
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('background_embedding.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ProcessingStats:
    """Track processing statistics"""
    total_thoughts_found: int = 0
    new_thoughts_processed: int = 0
    embeddings_generated: int = 0
    qdrant_writes: int = 0
    errors: int = 0
    start_time: datetime = None
    last_run: datetime = None
    
    def to_dict(self):
        return asdict(self)

class BackgroundEmbeddingService:
    """
    Background service that monitors Redis for new thoughts and embeds them in Qdrant
    """
    
    def __init__(self, 
                 redis_host: str = "127.0.0.1",
                 redis_port: int = 6379,
                 redis_password: str = "legacymind_redis_pass",
                 qdrant_host: str = "localhost",
                 qdrant_port: int = 6333,
                 openai_api_key: str = None,
                 scan_interval: int = 30,
                 batch_size: int = 50):
        
        self.scan_interval = scan_interval
        self.batch_size = batch_size
        self.stats = ProcessingStats()
        
        # Initialize Redis
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True
        )
        
        # Initialize Qdrant
        self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
        
        # Initialize OpenAI
        if not openai_api_key:
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                # Try to get from Redis
                try:
                    openai_api_key = self.redis_client.get('config:openai_api_key')
                    if isinstance(openai_api_key, bytes):
                        openai_api_key = openai_api_key.decode('utf-8')
                    # Handle environment variable format
                    if openai_api_key and openai_api_key.startswith('${') and openai_api_key.endswith('}'):
                        env_var = openai_api_key[2:-1]  # Remove ${ and }
                        openai_api_key = os.getenv(env_var)
                except:
                    pass
                    
        if not openai_api_key:
            raise ValueError("OpenAI API key not provided")
            
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        
        # Known instances to process
        self.instances = ["CC", "CCI", "CCD", "CCS", "DT", "CCB"]
        
        # State management
        self.running = True
        self.state_file = 'embedding_service_state.json'
        self.load_state()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        logger.info("Background Embedding Service initialized")
    
    def setup_qdrant_collections(self):
        """Setup instance-specific collections in Qdrant"""
        logger.info("Setting up Qdrant collections...")
        
        for instance in self.instances:
            # Create thoughts collection
            thoughts_collection = f"{instance}_thoughts"
            identity_collection = f"{instance}_identity"
            
            for collection_name in [thoughts_collection, identity_collection]:
                try:
                    # Check if collection exists
                    self.qdrant_client.get_collection(collection_name)
                    logger.info(f"Collection {collection_name} already exists")
                except:
                    # Create collection
                    self.qdrant_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=1536,  # OpenAI text-embedding-3-small
                            distance=Distance.COSINE
                        ),
                        optimizers_config=models.OptimizersConfigDiff(
                            default_segment_number=2,
                            memmap_threshold=20000,
                        ),
                        hnsw_config=models.HnswConfigDiff(
                            m=16,
                            ef_construct=100,
                            full_scan_threshold=10000,
                            on_disk=False
                        )
                    )
                    logger.info(f"Created Qdrant collection: {collection_name}")
    
    def get_processed_thoughts(self) -> Dict[str, Set[str]]:
        """Get set of already processed thought IDs per instance"""
        processed = {}
        
        for instance in self.instances:
            collection_name = f"{instance}_thoughts"
            try:
                # Get all point IDs from Qdrant collection
                result = self.qdrant_client.scroll(
                    collection_name=collection_name,
                    limit=10000,  # Adjust if you have more thoughts
                    with_payload=True,
                    with_vectors=False
                )
                
                thought_ids = set()
                for point in result[0]:
                    if 'thought_id' in point.payload:
                        thought_ids.add(point.payload['thought_id'])
                
                processed[instance] = thought_ids
                logger.info(f"Found {len(thought_ids)} processed thoughts for {instance}")
                
            except Exception as e:
                logger.warning(f"Could not get processed thoughts for {instance}: {e}")
                processed[instance] = set()
        
        return processed
    
    def get_processed_identity(self) -> Dict[str, Set[str]]:
        """Get set of already processed identity IDs per instance"""
        processed = {}
        
        for instance in self.instances:
            collection_name = f"{instance}_identity"
            try:
                # Get all point IDs from Qdrant collection
                result = self.qdrant_client.scroll(
                    collection_name=collection_name,
                    limit=10000,
                    with_payload=True,
                    with_vectors=False
                )
                
                identity_ids = set()
                for point in result[0]:
                    if 'identity_id' in point.payload:
                        identity_ids.add(point.payload['identity_id'])
                
                processed[instance] = identity_ids
                logger.info(f"Found {len(identity_ids)} processed identity items for {instance}")
                
            except Exception as e:
                logger.warning(f"Could not get processed identity for {instance}: {e}")
                processed[instance] = set()
        
        return processed
    
    def scan_redis_thoughts(self, instance: str) -> List[Dict[str, Any]]:
        """Scan Redis for thoughts from specific instance"""
        pattern = f"{instance}:Thoughts:*"  # Capital T pattern
        thoughts = []
        
        try:
            # Use SCAN for safe iteration
            for key in self.redis_client.scan_iter(pattern, count=1000):
                try:
                    # Check key type first
                    key_type = self.redis_client.type(key)
                    
                    content = None
                    if key_type == 'hash':
                        # Get hash data
                        hash_data = self.redis_client.hgetall(key)
                        # Look for thought content in common fields
                        for field in ['thought', 'content', 'text']:
                            if field in hash_data:
                                content = hash_data[field]
                                break
                        # If no content field found, try to get JSON string
                        if not content and hash_data:
                            content = str(hash_data.get(list(hash_data.keys())[0], ''))
                    elif key_type == 'string':
                        content = self.redis_client.get(key)
                        
                        # Try to parse as JSON if it's a string
                        if content:
                            try:
                                thought_data = json.loads(content)
                                if isinstance(thought_data, dict) and 'thought' in thought_data:
                                    content = thought_data['thought']
                                elif isinstance(thought_data, dict) and 'content' in thought_data:
                                    content = thought_data['content']
                                else:
                                    content = str(thought_data)
                            except:
                                # Content is just a string
                                pass
                    
                    elif key_type == 'ReJSON-RL':
                        # Handle RedisJSON type
                        try:
                            # Use JSON.GET to retrieve the thought
                            json_str = self.redis_client.execute_command('JSON.GET', key, '.')
                            if json_str:
                                thought_data = json.loads(json_str)
                                if isinstance(thought_data, dict) and 'thought' in thought_data:
                                    content = thought_data['thought']
                                elif isinstance(thought_data, dict) and 'content' in thought_data:
                                    content = thought_data['content']
                                else:
                                    # Try to get the thought field directly
                                    json_str = self.redis_client.execute_command('JSON.GET', key, '.thought')
                                    if json_str:
                                        content = json.loads(json_str)
                        except Exception as e:
                            logger.error(f"Error reading RedisJSON key {key}: {e}")
                    
                    if content:
                        # Extract thought ID from key
                        thought_id = key.split(':')[-1]
                        
                        thoughts.append({
                            'thought_id': thought_id,
                            'content': content,
                            'source_key': key,
                            'instance': instance
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing key {key}: {e}")
                    
        except Exception as e:
            logger.error(f"Error scanning Redis for {instance}: {e}")
        
        self.stats.total_thoughts_found += len(thoughts)
        return thoughts
    
    def scan_redis_identity(self, instance: str) -> List[Dict[str, Any]]:
        """Scan Redis for identity data from specific instance"""
        pattern = f"{instance}:identity:*"
        identity_items = []
        
        try:
            # Use SCAN for safe iteration
            for key in self.redis_client.scan_iter(pattern, count=1000):
                try:
                    # Check key type first
                    key_type = self.redis_client.type(key)
                    
                    content = None
                    if key_type == 'hash':
                        # Get hash data
                        hash_data = self.redis_client.hgetall(key)
                        # Convert entire identity structure to string for embedding
                        content = json.dumps(hash_data)
                    elif key_type == 'string':
                        content = self.redis_client.get(key)
                    elif key_type == 'ReJSON-RL':
                        # Handle RedisJSON type
                        try:
                            json_str = self.redis_client.execute_command('JSON.GET', key, '.')
                            if json_str:
                                content = json_str
                        except Exception as e:
                            logger.error(f"Error reading RedisJSON identity key {key}: {e}")
                    
                    if content:
                        # Extract identity ID from key
                        identity_id = key.split(':')[-1]
                        
                        identity_items.append({
                            'identity_id': identity_id,
                            'content': content,
                            'source_key': key,
                            'instance': instance
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing identity key {key}: {e}")
                    
        except Exception as e:
            logger.error(f"Error scanning Redis identity for {instance}: {e}")
        
        return identity_items
    
    def filter_new_identity(self, identity_items: List[Dict[str, Any]], processed_ids: Set[str]) -> List[Dict[str, Any]]:
        """Filter out identity items that have already been processed"""
        new_items = []
        
        for item in identity_items:
            if item['identity_id'] not in processed_ids:
                new_items.append(item)
        
        logger.info(f"Found {len(new_items)} new identity items out of {len(identity_items)} total")
        return new_items
    
    def filter_new_thoughts(self, thoughts: List[Dict[str, Any]], processed_ids: Set[str]) -> List[Dict[str, Any]]:
        """Filter out thoughts that have already been processed"""
        new_thoughts = []
        
        for thought in thoughts:
            if thought['thought_id'] not in processed_ids:
                new_thoughts.append(thought)
        
        logger.info(f"Found {len(new_thoughts)} new thoughts out of {len(thoughts)} total")
        return new_thoughts
    
    def generate_embeddings_batch(self, thoughts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate embeddings for a batch of thoughts"""
        if not thoughts:
            return []
        
        try:
            # Extract and clean content for batch processing
            contents = []
            for thought in thoughts:
                content = thought['content']
                # Clean content to handle Unicode/emoji issues
                if isinstance(content, str):
                    # Remove non-ASCII characters that cause encoding issues
                    content = ''.join(char for char in content if ord(char) < 128)
                contents.append(content)
            
            # Generate embeddings
            response = self.openai_client.embeddings.create(
                input=contents,
                model="text-embedding-3-small"
            )
            
            # Attach embeddings to thoughts
            for i, thought in enumerate(thoughts):
                thought['embedding'] = response.data[i].embedding
                thought['embedding_model'] = "text-embedding-3-small"
                thought['processed_at'] = datetime.now().isoformat()
            
            self.stats.embeddings_generated += len(thoughts)
            logger.info(f"Generated {len(thoughts)} embeddings")
            return thoughts
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            self.stats.errors += 1
            return []
    
    def store_in_qdrant(self, thoughts: List[Dict[str, Any]], instance: str):
        """Store thoughts with embeddings in Qdrant"""
        if not thoughts:
            return
        
        collection_name = f"{instance}_thoughts"
        points = []
        
        for thought in thoughts:
            if 'embedding' not in thought:
                continue
                
            # Create unique point ID (hash of thought_id)
            point_id = int(hashlib.md5(thought['thought_id'].encode()).hexdigest()[:8], 16)
            
            point = PointStruct(
                id=point_id,
                vector=thought['embedding'],
                payload={
                    "thought_id": thought['thought_id'],
                    "instance": instance,
                    "content": thought['content'],
                    "source_key": thought['source_key'],
                    "embedding_model": thought['embedding_model'],
                    "processed_at": thought['processed_at'],
                    "content_length": len(thought['content']),
                    "word_count": len(thought['content'].split())
                }
            )
            points.append(point)
        
        try:
            # Store in Qdrant
            self.qdrant_client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            self.stats.qdrant_writes += len(points)
            logger.info(f"Stored {len(points)} thoughts in {collection_name}")
            
        except Exception as e:
            logger.error(f"Error storing in Qdrant: {e}")
            self.stats.errors += 1
    
    def store_in_qdrant_identity(self, identity_items: List[Dict[str, Any]], instance: str):
        """Store identity data with embeddings in Qdrant"""
        if not identity_items:
            return
        
        collection_name = f"{instance}_identity"
        points = []
        
        for item in identity_items:
            if 'embedding' not in item:
                continue
                
            # Create unique point ID (hash of identity_id)
            point_id = int(hashlib.md5(item['identity_id'].encode()).hexdigest()[:8], 16)
            
            point = PointStruct(
                id=point_id,
                vector=item['embedding'],
                payload={
                    "identity_id": item['identity_id'],
                    "instance": instance,
                    "content": item['content'],
                    "source_key": item['source_key'],
                    "embedding_model": item['embedding_model'],
                    "processed_at": item['processed_at'],
                    "content_length": len(item['content']),
                    "data_type": "identity"
                }
            )
            points.append(point)
        
        try:
            # Store in Qdrant
            self.qdrant_client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            self.stats.qdrant_writes += len(points)
            logger.info(f"Stored {len(points)} identity items in {collection_name}")
            
        except Exception as e:
            logger.error(f"Error storing identity in Qdrant: {e}")
            self.stats.errors += 1
    
    def process_instance(self, instance: str, processed_thoughts: Set[str]):
        """Process all thoughts for a specific instance"""
        logger.info(f"Processing instance: {instance}")
        
        # Get all thoughts from Redis
        all_thoughts = self.scan_redis_thoughts(instance)
        if not all_thoughts:
            logger.info(f"No thoughts found for {instance}")
            return
        
        # Filter to new thoughts only
        new_thoughts = self.filter_new_thoughts(all_thoughts, processed_thoughts)
        if not new_thoughts:
            logger.info(f"No new thoughts to process for {instance}")
            return
        
        # Process in batches
        for i in range(0, len(new_thoughts), self.batch_size):
            batch = new_thoughts[i:i + self.batch_size]
            
            logger.info(f"Processing batch {i//self.batch_size + 1} for {instance}: {len(batch)} thoughts")
            
            # Generate embeddings
            batch_with_embeddings = self.generate_embeddings_batch(batch)
            
            if batch_with_embeddings:
                # Store in Qdrant
                self.store_in_qdrant(batch_with_embeddings, instance)
                self.stats.new_thoughts_processed += len(batch_with_embeddings)
            
            # Rate limiting - respect OpenAI limits
            time.sleep(3)  # 3 seconds between batches
    
    def process_identity(self, instance: str, processed_identity_ids: Set[str]):
        """Process all identity data for a specific instance"""
        logger.info(f"Processing identity for instance: {instance}")
        
        # Get all identity data from Redis
        all_identity = self.scan_redis_identity(instance)
        if not all_identity:
            logger.info(f"No identity data found for {instance}")
            return
        
        # Filter to new identity data only
        new_identity = self.filter_new_identity(all_identity, processed_identity_ids)
        if not new_identity:
            logger.info(f"No new identity data to process for {instance}")
            return
        
        # Process in batches
        for i in range(0, len(new_identity), self.batch_size):
            batch = new_identity[i:i + self.batch_size]
            
            logger.info(f"Processing identity batch {i//self.batch_size + 1} for {instance}: {len(batch)} items")
            
            # Generate embeddings
            batch_with_embeddings = self.generate_embeddings_batch(batch)
            
            if batch_with_embeddings:
                # Store in Qdrant identity collection
                self.store_in_qdrant_identity(batch_with_embeddings, instance)
                self.stats.new_thoughts_processed += len(batch_with_embeddings)
            
            # Rate limiting - respect OpenAI limits
            time.sleep(3)  # 3 seconds between batches
    
    def run_single_scan(self):
        """Run a single scan cycle"""
        logger.info("Starting background embedding scan...")
        self.stats.start_time = datetime.now()
        
        try:
            # Setup collections if needed
            self.setup_qdrant_collections()
            
            # Get already processed thoughts
            processed_thoughts = self.get_processed_thoughts()
            
            # Get already processed identity
            processed_identity = self.get_processed_identity()
            
            # Process each instance - both thoughts and identity
            for instance in self.instances:
                self.process_instance(instance, processed_thoughts.get(instance, set()))
                self.process_identity(instance, processed_identity.get(instance, set()))
            
            self.stats.last_run = datetime.now()
            
            # Log summary
            duration = (self.stats.last_run - self.stats.start_time).total_seconds()
            logger.info(f"Scan completed in {duration:.1f}s: "
                       f"{self.stats.new_thoughts_processed} thoughts processed, "
                       f"{self.stats.embeddings_generated} embeddings generated, "
                       f"{self.stats.qdrant_writes} Qdrant writes, "
                       f"{self.stats.errors} errors")
            
        except Exception as e:
            logger.error(f"Error in scan cycle: {e}")
            self.stats.errors += 1
    
    def save_stats(self):
        """Save processing statistics to Redis"""
        try:
            stats_key = "background_embedding:stats"
            self.redis_client.set(stats_key, json.dumps(self.stats.to_dict(), default=str))
        except Exception as e:
            logger.error(f"Error saving stats: {e}")
    
    def load_state(self):
        """Load persistent state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    logger.info(f"Loaded state: last run {state.get('last_run', 'unknown')}")
                    return state
        except Exception as e:
            logger.error(f"Error loading state: {e}")
        return {}
    
    def save_state(self):
        """Save persistent state to file"""
        try:
            state = {
                'last_run': datetime.now().isoformat(),
                'stats': self.stats.to_dict(),
                'instances_processed': self.instances
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        self.save_state()
        self.save_stats()
        logger.info("Shutdown complete")
        sys.exit(0)
    
    def run_continuous(self):
        """Run continuous background processing"""
        logger.info(f"Starting continuous background embedding service (scan every {self.scan_interval}s)")
        
        while self.running:
            try:
                self.run_single_scan()
                self.save_stats()
                self.save_state()
                
                # Sleep with interrupt checking
                for i in range(self.scan_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Background embedding service stopped by user")
                self.handle_shutdown(signal.SIGINT, None)
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(60)  # Wait before retry

def main():
    """CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Background Embedding Service')
    parser.add_argument('--scan-interval', type=int, default=30, help='Scan interval in seconds')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for processing')
    parser.add_argument('--single-run', action='store_true', help='Run once instead of continuously')
    parser.add_argument('--setup-only', action='store_true', help='Just setup Qdrant collections and exit')
    
    args = parser.parse_args()
    
    # Initialize service
    service = BackgroundEmbeddingService(
        scan_interval=args.scan_interval,
        batch_size=args.batch_size
    )
    
    if args.setup_only:
        service.setup_qdrant_collections()
        print("Qdrant collections setup complete")
        return
    
    if args.single_run:
        service.run_single_scan()
        service.save_stats()
    else:
        service.run_continuous()

if __name__ == "__main__":
    main()
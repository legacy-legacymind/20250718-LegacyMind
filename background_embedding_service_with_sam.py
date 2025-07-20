#!/usr/bin/env python3
"""
Enhanced Background Embedding Service with Sam's Data Support
Automatically processes thoughts from Redis → OpenAI → Qdrant
Includes support for Sam's identity and context data
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
    sam_items_processed: int = 0
    start_time: datetime = None
    last_run: datetime = None
    
    def to_dict(self):
        return asdict(self)

class BackgroundEmbeddingService:
    """
    Background service that monitors Redis for new thoughts and embeds them in Qdrant
    Enhanced with Sam's identity and context data support
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
        
        # Sam's specific Redis keys
        self.sam_keys = {
            'identity': 'Sam:Identity',
            'brain_dump': 'Sam:Context:BrainDump',
            'expectations': 'Sam:Context:Expectations'
        }
        
        # State management
        self.running = True
        self.state_file = 'embedding_service_state.json'
        self.load_state()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        logger.info("Enhanced Background Embedding Service initialized")
    
    def setup_qdrant_collections(self):
        """Setup instance-specific collections and Sam's collections in Qdrant"""
        logger.info("Setting up Qdrant collections...")
        
        # Instance collections
        for instance in self.instances:
            # Create thoughts collection
            thoughts_collection = f"{instance}_thoughts"
            identity_collection = f"{instance}_identity"
            
            for collection_name in [thoughts_collection, identity_collection]:
                self._create_collection_if_not_exists(collection_name)
        
        # Sam's collections
        for collection_name in ['Sam_identity', 'Sam_context']:
            self._create_collection_if_not_exists(collection_name)
    
    def _create_collection_if_not_exists(self, collection_name: str):
        """Create a Qdrant collection if it doesn't exist"""
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
    
    def get_processed_sam_items(self) -> Set[str]:
        """Get set of already processed Sam items"""
        processed_items = set()
        
        for collection_name in ['Sam_identity', 'Sam_context']:
            try:
                result = self.qdrant_client.scroll(
                    collection_name=collection_name,
                    limit=10000,
                    with_payload=True,
                    with_vectors=False
                )
                
                for point in result[0]:
                    if 'item_id' in point.payload:
                        processed_items.add(point.payload['item_id'])
                
            except Exception as e:
                logger.warning(f"Could not get processed items for {collection_name}: {e}")
        
        logger.info(f"Found {len(processed_items)} processed Sam items")
        return processed_items
    
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
    
    def fetch_sam_data(self) -> List[Dict[str, Any]]:
        """Fetch Sam's identity and context data from Redis"""
        sam_items = []
        
        for key_name, redis_key in self.sam_keys.items():
            try:
                # Check key type
                key_type = self.redis_client.type(redis_key)
                
                if key_type == 'none':
                    logger.warning(f"Key {redis_key} does not exist")
                    continue
                
                content = None
                if key_type == 'hash':
                    # Get hash data
                    hash_data = self.redis_client.hgetall(redis_key)
                    content = json.dumps(hash_data)
                elif key_type == 'string':
                    content = self.redis_client.get(redis_key)
                elif key_type == 'ReJSON-RL':
                    # Handle RedisJSON type
                    try:
                        json_str = self.redis_client.execute_command('JSON.GET', redis_key, '.')
                        if json_str:
                            content = json_str
                    except Exception as e:
                        logger.error(f"Error reading RedisJSON key {redis_key}: {e}")
                
                if content:
                    item_id = f'sam_{key_name}'
                    collection = 'Sam_identity' if key_name == 'identity' else 'Sam_context'
                    
                    sam_items.append({
                        'item_id': item_id,
                        'content': content,
                        'source_key': redis_key,
                        'data_type': key_name,
                        'collection': collection
                    })
                    logger.info(f"Retrieved Sam's {key_name} data")
                
            except Exception as e:
                logger.error(f"Error fetching {redis_key}: {e}")
        
        return sam_items
    
    def filter_new_thoughts(self, thoughts: List[Dict[str, Any]], processed_ids: Set[str]) -> List[Dict[str, Any]]:
        """Filter out thoughts that have already been processed"""
        new_thoughts = []
        
        for thought in thoughts:
            if thought['thought_id'] not in processed_ids:
                new_thoughts.append(thought)
        
        logger.info(f"Found {len(new_thoughts)} new thoughts out of {len(thoughts)} total")
        return new_thoughts
    
    def filter_new_sam_items(self, items: List[Dict[str, Any]], processed_ids: Set[str]) -> List[Dict[str, Any]]:
        """Filter out Sam items that have already been processed"""
        new_items = []
        
        for item in items:
            if item['item_id'] not in processed_ids:
                new_items.append(item)
        
        if new_items:
            logger.info(f"Found {len(new_items)} new Sam items out of {len(items)} total")
        return new_items
    
    def generate_embeddings_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate embeddings for a batch of items"""
        if not items:
            return []
        
        try:
            # Extract and clean content for batch processing
            contents = []
            for item in items:
                content = item['content']
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
            
            # Attach embeddings to items
            for i, item in enumerate(items):
                item['embedding'] = response.data[i].embedding
                item['embedding_model'] = "text-embedding-3-small"
                item['processed_at'] = datetime.now().isoformat()
            
            self.stats.embeddings_generated += len(items)
            logger.info(f"Generated {len(items)} embeddings")
            return items
            
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
    
    def store_sam_items_in_qdrant(self, items: List[Dict[str, Any]]):
        """Store Sam's items with embeddings in appropriate Qdrant collections"""
        if not items:
            return
        
        # Group items by collection
        collections = {}
        for item in items:
            if 'embedding' not in item:
                continue
            
            collection = item['collection']
            if collection not in collections:
                collections[collection] = []
            collections[collection].append(item)
        
        # Store in each collection
        for collection_name, collection_items in collections.items():
            points = []
            
            for item in collection_items:
                # Create unique point ID
                point_id = int(hashlib.md5(item['item_id'].encode()).hexdigest()[:8], 16)
                
                point = PointStruct(
                    id=point_id,
                    vector=item['embedding'],
                    payload={
                        "item_id": item['item_id'],
                        "content": item['content'],
                        "source_key": item['source_key'],
                        "data_type": item['data_type'],
                        "embedding_model": item['embedding_model'],
                        "processed_at": item['processed_at'],
                        "content_length": len(item['content'])
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
                self.stats.sam_items_processed += len(points)
                logger.info(f"Stored {len(points)} Sam items in {collection_name}")
                
            except Exception as e:
                logger.error(f"Error storing Sam items in Qdrant collection {collection_name}: {e}")
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
    
    def process_sam_data(self, processed_sam_ids: Set[str]):
        """Process Sam's identity and context data"""
        logger.info("Processing Sam's data...")
        
        # Fetch Sam's data from Redis
        all_sam_items = self.fetch_sam_data()
        if not all_sam_items:
            logger.info("No Sam data found")
            return
        
        # Filter to new items only
        new_sam_items = self.filter_new_sam_items(all_sam_items, processed_sam_ids)
        if not new_sam_items:
            logger.info("No new Sam data to process")
            return
        
        # Process all at once (typically small dataset)
        logger.info(f"Processing {len(new_sam_items)} Sam data items")
        
        # Generate embeddings
        items_with_embeddings = self.generate_embeddings_batch(new_sam_items)
        
        if items_with_embeddings:
            # Store in Qdrant
            self.store_sam_items_in_qdrant(items_with_embeddings)
    
    def run_single_scan(self):
        """Run a single scan cycle"""
        logger.info("Starting enhanced background embedding scan...")
        self.stats.start_time = datetime.now()
        
        try:
            # Setup collections if needed
            self.setup_qdrant_collections()
            
            # Get already processed thoughts
            processed_thoughts = self.get_processed_thoughts()
            
            # Get already processed Sam items
            processed_sam_items = self.get_processed_sam_items()
            
            # Process each instance
            for instance in self.instances:
                self.process_instance(instance, processed_thoughts.get(instance, set()))
            
            # Process Sam's data
            self.process_sam_data(processed_sam_items)
            
            self.stats.last_run = datetime.now()
            
            # Log summary
            duration = (self.stats.last_run - self.stats.start_time).total_seconds()
            logger.info(f"Scan completed in {duration:.1f}s: "
                       f"{self.stats.new_thoughts_processed} thoughts processed, "
                       f"{self.stats.sam_items_processed} Sam items processed, "
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
                'instances_processed': self.instances,
                'sam_collections': ['Sam_identity', 'Sam_context']
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
        logger.info(f"Starting continuous enhanced background embedding service (scan every {self.scan_interval}s)")
        
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
    
    parser = argparse.ArgumentParser(description='Enhanced Background Embedding Service with Sam Support')
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
        print("Qdrant collections setup complete (including Sam's collections)")
        return
    
    if args.single_run:
        service.run_single_scan()
        service.save_stats()
    else:
        service.run_continuous()

if __name__ == "__main__":
    main()
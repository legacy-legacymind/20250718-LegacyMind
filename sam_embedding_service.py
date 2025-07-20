#!/usr/bin/env python3
"""
Sam Identity & Context Embedding Service
Processes Sam's identity and context data from Redis → OpenAI → Qdrant
Specifically handles:
- Sam:Identity
- Sam:Context:BrainDump
- Sam:Context:Expectations
"""

import redis
import openai
import json
import time
import logging
import os
import signal
import sys
from datetime import datetime
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
        logging.FileHandler('sam_embedding.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ProcessingStats:
    """Track processing statistics"""
    total_items_found: int = 0
    new_items_processed: int = 0
    embeddings_generated: int = 0
    qdrant_writes: int = 0
    errors: int = 0
    start_time: datetime = None
    last_run: datetime = None
    
    def to_dict(self):
        return asdict(self)

class SamEmbeddingService:
    """
    Service that processes Sam's identity and context data into embeddings
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
        
        # Define Sam's specific Redis keys
        self.sam_keys = {
            'identity': 'Sam:Identity',
            'brain_dump': 'Sam:Context:BrainDump',
            'expectations': 'Sam:Context:Expectations'
        }
        
        # State management
        self.running = True
        self.state_file = 'sam_embedding_state.json'
        self.load_state()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        logger.info("Sam Embedding Service initialized")
    
    def setup_qdrant_collections(self):
        """Setup Sam-specific collections in Qdrant"""
        logger.info("Setting up Sam's Qdrant collections...")
        
        collections = ['Sam_identity', 'Sam_context']
        
        for collection_name in collections:
            try:
                # Check if collection exists
                self.qdrant_client.get_collection(collection_name)
                logger.info(f"Collection {collection_name} already exists")
            except:
                # Create collection with optimized settings
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
    
    def get_processed_items(self, collection_name: str) -> Set[str]:
        """Get set of already processed item IDs from Qdrant"""
        try:
            # Get all point IDs from Qdrant collection
            result = self.qdrant_client.scroll(
                collection_name=collection_name,
                limit=10000,
                with_payload=True,
                with_vectors=False
            )
            
            item_ids = set()
            for point in result[0]:
                if 'item_id' in point.payload:
                    item_ids.add(point.payload['item_id'])
            
            logger.info(f"Found {len(item_ids)} processed items in {collection_name}")
            return item_ids
            
        except Exception as e:
            logger.warning(f"Could not get processed items for {collection_name}: {e}")
            return set()
    
    def fetch_redis_data(self) -> Dict[str, Any]:
        """Fetch Sam's data from Redis"""
        data = {}
        
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
                    data[key_name] = {
                        'content': content,
                        'source_key': redis_key,
                        'key_type': key_type,
                        'retrieved_at': datetime.now().isoformat()
                    }
                    logger.info(f"Retrieved data from {redis_key}")
                
            except Exception as e:
                logger.error(f"Error fetching {redis_key}: {e}")
        
        self.stats.total_items_found = len(data)
        return data
    
    def prepare_embedding_chunks(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Prepare data chunks for embedding"""
        chunks = []
        
        # Process identity data
        if 'identity' in data:
            chunk = {
                'item_id': 'sam_identity',
                'content': data['identity']['content'],
                'source_key': data['identity']['source_key'],
                'data_type': 'identity',
                'collection': 'Sam_identity'
            }
            chunks.append(chunk)
        
        # Process context data
        for context_type in ['brain_dump', 'expectations']:
            if context_type in data:
                chunk = {
                    'item_id': f'sam_context_{context_type}',
                    'content': data[context_type]['content'],
                    'source_key': data[context_type]['source_key'],
                    'data_type': f'context_{context_type}',
                    'collection': 'Sam_context'
                }
                chunks.append(chunk)
        
        return chunks
    
    def generate_embeddings_batch(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate embeddings for a batch of data chunks"""
        if not chunks:
            return []
        
        try:
            # Extract content for batch processing
            contents = []
            for chunk in chunks:
                content = chunk['content']
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
            
            # Attach embeddings to chunks
            for i, chunk in enumerate(chunks):
                chunk['embedding'] = response.data[i].embedding
                chunk['embedding_model'] = "text-embedding-3-small"
                chunk['processed_at'] = datetime.now().isoformat()
            
            self.stats.embeddings_generated += len(chunks)
            logger.info(f"Generated {len(chunks)} embeddings")
            return chunks
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            self.stats.errors += 1
            return []
    
    def store_in_qdrant(self, chunks: List[Dict[str, Any]]):
        """Store chunks with embeddings in appropriate Qdrant collections"""
        if not chunks:
            return
        
        # Group chunks by collection
        collections = {}
        for chunk in chunks:
            if 'embedding' not in chunk:
                continue
            
            collection = chunk['collection']
            if collection not in collections:
                collections[collection] = []
            collections[collection].append(chunk)
        
        # Store in each collection
        for collection_name, collection_chunks in collections.items():
            points = []
            
            for chunk in collection_chunks:
                # Create unique point ID
                point_id = int(hashlib.md5(chunk['item_id'].encode()).hexdigest()[:8], 16)
                
                point = PointStruct(
                    id=point_id,
                    vector=chunk['embedding'],
                    payload={
                        "item_id": chunk['item_id'],
                        "content": chunk['content'],
                        "source_key": chunk['source_key'],
                        "data_type": chunk['data_type'],
                        "embedding_model": chunk['embedding_model'],
                        "processed_at": chunk['processed_at'],
                        "content_length": len(chunk['content'])
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
                logger.info(f"Stored {len(points)} items in {collection_name}")
                
            except Exception as e:
                logger.error(f"Error storing in Qdrant collection {collection_name}: {e}")
                self.stats.errors += 1
    
    def run_single_scan(self):
        """Run a single scan cycle"""
        logger.info("Starting Sam embedding scan...")
        self.stats.start_time = datetime.now()
        
        try:
            # Setup collections if needed
            self.setup_qdrant_collections()
            
            # Get already processed items
            processed_identity = self.get_processed_items('Sam_identity')
            processed_context = self.get_processed_items('Sam_context')
            processed_all = processed_identity.union(processed_context)
            
            # Fetch Sam's data from Redis
            redis_data = self.fetch_redis_data()
            
            if not redis_data:
                logger.info("No data found in Redis")
                return
            
            # Prepare chunks for embedding
            all_chunks = self.prepare_embedding_chunks(redis_data)
            
            # Filter to new chunks only
            new_chunks = [chunk for chunk in all_chunks if chunk['item_id'] not in processed_all]
            
            if not new_chunks:
                logger.info("No new data to process")
                return
            
            logger.info(f"Processing {len(new_chunks)} new items")
            
            # Process in batches
            for i in range(0, len(new_chunks), self.batch_size):
                batch = new_chunks[i:i + self.batch_size]
                
                logger.info(f"Processing batch {i//self.batch_size + 1}: {len(batch)} items")
                
                # Generate embeddings
                batch_with_embeddings = self.generate_embeddings_batch(batch)
                
                if batch_with_embeddings:
                    # Store in Qdrant
                    self.store_in_qdrant(batch_with_embeddings)
                    self.stats.new_items_processed += len(batch_with_embeddings)
                
                # Rate limiting
                time.sleep(3)
            
            self.stats.last_run = datetime.now()
            
            # Log summary
            duration = (self.stats.last_run - self.stats.start_time).total_seconds()
            logger.info(f"Scan completed in {duration:.1f}s: "
                       f"{self.stats.new_items_processed} items processed, "
                       f"{self.stats.embeddings_generated} embeddings generated, "
                       f"{self.stats.qdrant_writes} Qdrant writes, "
                       f"{self.stats.errors} errors")
            
        except Exception as e:
            logger.error(f"Error in scan cycle: {e}")
            self.stats.errors += 1
    
    def save_stats(self):
        """Save processing statistics to Redis"""
        try:
            stats_key = "sam_embedding:stats"
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
                'stats': self.stats.to_dict()
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
        logger.info(f"Starting continuous Sam embedding service (scan every {self.scan_interval}s)")
        
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
                logger.info("Sam embedding service stopped by user")
                self.handle_shutdown(signal.SIGINT, None)
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(60)  # Wait before retry

def main():
    """CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sam Identity & Context Embedding Service')
    parser.add_argument('--scan-interval', type=int, default=30, help='Scan interval in seconds')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for processing')
    parser.add_argument('--single-run', action='store_true', help='Run once instead of continuously')
    parser.add_argument('--setup-only', action='store_true', help='Just setup Qdrant collections and exit')
    
    args = parser.parse_args()
    
    # Initialize service
    service = SamEmbeddingService(
        scan_interval=args.scan_interval,
        batch_size=args.batch_size
    )
    
    if args.setup_only:
        service.setup_qdrant_collections()
        print("Sam's Qdrant collections setup complete")
        return
    
    if args.single_run:
        service.run_single_scan()
        service.save_stats()
    else:
        service.run_continuous()

if __name__ == "__main__":
    main()
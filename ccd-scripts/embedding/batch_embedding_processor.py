#!/usr/bin/env python3
"""
Enhanced Batch Embedding Processor for unified-intelligence
Extracted from batch_embeddings.py and enhanced for API integration.
Supports batching, rate limiting, progress tracking, and async operations.
"""

import sys
import json
import os
import time
import redis
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchJob:
    """Represents a batch embedding job"""
    job_id: str
    instance: str
    total_thoughts: int
    processed: int = 0
    success: int = 0
    errors: int = 0
    status: JobStatus = JobStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class ThoughtRecord:
    """Represents a thought that needs embedding"""
    key: str
    thought_id: str
    content: str
    timestamp: int


class EnhancedBatchEmbeddingProcessor:
    """Enhanced batch embedding processor with API support"""
    
    def __init__(self, redis_url: str, openai_api_key: str, instance: str = "Claude"):
        """Initialize the enhanced batch embedding processor"""
        self.redis_client = redis.from_url(redis_url)
        self.redis_url = redis_url
        self.openai_api_key = openai_api_key
        self.instance = instance
        self.jobs: Dict[str, BatchJob] = {}
        
        # Import here to avoid circular dependency issues
        try:
            sys.path.append('/Users/samuelatagana/Projects/LegacyMind/worktrees/CCD/unified-intelligence')
            from simple_embeddings import SimpleEmbeddingService
            self.embedding_service = SimpleEmbeddingService(redis_url, openai_api_key, instance)
        except ImportError as e:
            print(f"Warning: Could not import SimpleEmbeddingService: {e}")
            self.embedding_service = None
    
    def get_thoughts_without_embeddings(self) -> List[ThoughtRecord]:
        """Find all thoughts that don't have embeddings"""
        try:
            # Get all thought keys
            thought_pattern = f"{self.instance}:Thoughts:*"
            thought_keys = self.redis_client.keys(thought_pattern)
            
            # Get all embedding keys
            embedding_pattern = f"{self.instance}:embeddings:*"
            embedding_keys = self.redis_client.keys(embedding_pattern)
            
            # Extract thought IDs that have embeddings
            embedded_thought_ids = set()
            for key in embedding_keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                thought_id = key_str.split(':')[-1]  # Get the UUID part
                embedded_thought_ids.add(thought_id)
            
            # Find thoughts without embeddings
            missing_embeddings = []
            for thought_key in thought_keys:
                key_str = thought_key.decode('utf-8') if isinstance(thought_key, bytes) else thought_key
                thought_id = key_str.split(':')[-1]  # Get the UUID part
                
                if thought_id not in embedded_thought_ids:
                    try:
                        thought_data_str = self.redis_client.get(key_str)
                        if thought_data_str:
                            thought_data = json.loads(thought_data_str)
                            if thought_data and 'thought' in thought_data:
                                # Convert ISO timestamp to epoch seconds
                                timestamp_str = thought_data.get('timestamp', '')
                                try:
                                    if timestamp_str:
                                        timestamp = int(datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp())
                                    else:
                                        timestamp = int(time.time())
                                except ValueError:
                                    timestamp = int(time.time())
                                
                                missing_embeddings.append(ThoughtRecord(
                                    key=key_str,
                                    thought_id=thought_id,
                                    content=thought_data['thought'],
                                    timestamp=timestamp
                                ))
                    except Exception as e:
                        print(f"Error reading thought {key_str}: {e}", file=sys.stderr)
                        continue
            
            return missing_embeddings
            
        except Exception as e:
            print(f"Error finding thoughts without embeddings: {e}", file=sys.stderr)
            return []
    
    def create_batch_job(self, thoughts: Optional[List[ThoughtRecord]] = None) -> str:
        """Create a new batch job and return job ID"""
        if thoughts is None:
            thoughts = self.get_thoughts_without_embeddings()
        
        job_id = str(uuid.uuid4())
        job = BatchJob(
            job_id=job_id,
            instance=self.instance,
            total_thoughts=len(thoughts)
        )
        
        self.jobs[job_id] = job
        
        # Store job in Redis for persistence
        job_key = f"batch_jobs:{job_id}"
        job_data = {
            'job_id': job_id,
            'instance': self.instance,
            'total_thoughts': len(thoughts),
            'processed': 0,
            'success': 0,
            'errors': 0,
            'status': job.status.value,
            'created_at': datetime.now().isoformat()
        }
        self.redis_client.setex(job_key, 86400, json.dumps(job_data))  # 24 hour TTL
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        """Get the status of a batch job"""
        if job_id in self.jobs:
            return self.jobs[job_id]
        
        # Try to load from Redis
        job_key = f"batch_jobs:{job_id}"
        job_data_str = self.redis_client.get(job_key)
        if job_data_str:
            job_data = json.loads(job_data_str)
            job = BatchJob(
                job_id=job_data['job_id'],
                instance=job_data['instance'],
                total_thoughts=job_data['total_thoughts'],
                processed=job_data.get('processed', 0),
                success=job_data.get('success', 0),
                errors=job_data.get('errors', 0),
                status=JobStatus(job_data.get('status', 'pending'))
            )
            self.jobs[job_id] = job
            return job
        
        return None
    
    def update_job_status(self, job_id: str, **updates):
        """Update job status in memory and Redis"""
        if job_id not in self.jobs:
            return
        
        job = self.jobs[job_id]
        for key, value in updates.items():
            if hasattr(job, key):
                setattr(job, key, value)
        
        # Update in Redis
        job_key = f"batch_jobs:{job_id}"
        job_data = {
            'job_id': job.job_id,
            'instance': job.instance,
            'total_thoughts': job.total_thoughts,
            'processed': job.processed,
            'success': job.success,
            'errors': job.errors,
            'status': job.status.value,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'error_message': job.error_message
        }
        self.redis_client.setex(job_key, 86400, json.dumps(job_data))
    
    async def process_batch_async(self, job_id: str, batch_size: int = 50, delay: float = 0.02) -> Dict:
        """Process thoughts in batches asynchronously (Phase 1 batch optimization)"""
        job = self.get_job_status(job_id)
        if not job:
            return {'error': 'Job not found'}
        
        if not self.embedding_service:
            self.update_job_status(job_id, status=JobStatus.FAILED, error_message="Embedding service not available")
            return {'error': 'Embedding service not available'}
        
        # Update job status to running
        self.update_job_status(job_id, status=JobStatus.RUNNING, started_at=datetime.now())
        
        # Get thoughts to process
        thoughts = self.get_thoughts_without_embeddings()
        
        print(f"Processing {len(thoughts)} thoughts in batches of {batch_size}")
        
        try:
            for i in range(0, len(thoughts), batch_size):
                batch = thoughts[i:i + batch_size]
                print(f"Processing batch {i//batch_size + 1}: thoughts {i+1}-{min(i+batch_size, len(thoughts))}")
                
                # Process batch in parallel (Phase 1 optimization)
                tasks = []
                for thought in batch:
                    task = self._process_single_thought(thought)
                    tasks.append(task)
                
                # Wait for batch completion
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Update counters
                for result in results:
                    if isinstance(result, Exception):
                        job.errors += 1
                        print(f"✗ Error in batch: {result}")
                    elif result:
                        job.success += 1
                    else:
                        job.errors += 1
                    job.processed += 1
                
                # Update job status
                self.update_job_status(job_id, 
                                     processed=job.processed,
                                     success=job.success, 
                                     errors=job.errors)
                
                # Rate limiting between batches
                if i + batch_size < len(thoughts):
                    await asyncio.sleep(delay)
            
            # Mark job as completed
            self.update_job_status(job_id, 
                                 status=JobStatus.COMPLETED,
                                 completed_at=datetime.now())
            
            return {
                'job_id': job_id,
                'status': 'completed',
                'total': job.total_thoughts,
                'processed': job.processed,
                'success': job.success,
                'errors': job.errors
            }
            
        except Exception as e:
            self.update_job_status(job_id, 
                                 status=JobStatus.FAILED,
                                 error_message=str(e),
                                 completed_at=datetime.now())
            return {'error': str(e)}
    
    async def _process_single_thought(self, thought: ThoughtRecord) -> bool:
        """Process a single thought embedding asynchronously"""
        try:
            success = self.embedding_service.store_thought_embedding(
                thought.thought_id,
                thought.content,
                thought.timestamp
            )
            return success
        except Exception as e:
            print(f"Error processing thought {thought.thought_id}: {e}")
            return False
    
    def process_batch_sync(self, thoughts: List[ThoughtRecord], batch_size: int = 10, delay: float = 0.1) -> Dict:
        """Process thoughts in batches synchronously (legacy compatibility)"""
        results = {
            'total': len(thoughts),
            'processed': 0,
            'errors': 0,
            'success': 0
        }
        
        if not self.embedding_service:
            results['errors'] = len(thoughts)
            return results
        
        print(f"Processing {len(thoughts)} thoughts in batches of {batch_size}")
        
        for i in range(0, len(thoughts), batch_size):
            batch = thoughts[i:i + batch_size]
            print(f"Processing batch {i//batch_size + 1}: thoughts {i+1}-{min(i+batch_size, len(thoughts))}")
            
            for thought in batch:
                try:
                    success = self.embedding_service.store_thought_embedding(
                        thought.thought_id,
                        thought.content,
                        thought.timestamp
                    )
                    
                    if success:
                        results['success'] += 1
                        print(f"✓ Generated embedding for thought {thought.thought_id}")
                    else:
                        results['errors'] += 1
                        print(f"✗ Failed to generate embedding for thought {thought.thought_id}")
                    
                    results['processed'] += 1
                    
                    # Rate limiting
                    time.sleep(delay)
                    
                except Exception as e:
                    results['errors'] += 1
                    results['processed'] += 1
                    print(f"✗ Error processing thought {thought.thought_id}: {e}", file=sys.stderr)
            
            # Longer delay between batches
            if i + batch_size < len(thoughts):
                print(f"Batch complete. Waiting {delay * 10}s before next batch...")
                time.sleep(delay * 10)
        
        return results
    
    def analyze_current_state(self) -> Dict:
        """Analyze the current state of thoughts and embeddings"""
        try:
            # Count thoughts
            thought_pattern = f"{self.instance}:Thoughts:*"
            thought_count = len(self.redis_client.keys(thought_pattern))
            
            # Count embeddings
            embedding_pattern = f"{self.instance}:embeddings:*"
            embedding_count = len(self.redis_client.keys(embedding_pattern))
            
            # Find missing embeddings
            missing = self.get_thoughts_without_embeddings()
            
            return {
                'instance': self.instance,
                'total_thoughts': thought_count,
                'total_embeddings': embedding_count,
                'missing_embeddings': len(missing),
                'coverage_percentage': (embedding_count / thought_count * 100) if thought_count > 0 else 0,
                'analysis_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error analyzing current state: {e}", file=sys.stderr)
            return {'error': str(e)}
    
    def list_active_jobs(self) -> List[Dict]:
        """List all active batch jobs"""
        active_jobs = []
        for job_id, job in self.jobs.items():
            active_jobs.append({
                'job_id': job_id,
                'instance': job.instance,
                'status': job.status.value,
                'total_thoughts': job.total_thoughts,
                'processed': job.processed,
                'success': job.success,
                'errors': job.errors,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None
            })
        return active_jobs


# Backward compatibility function
def create_legacy_processor(redis_url: str, openai_api_key: str, instance: str = "Claude"):
    """Create processor with legacy interface"""
    return EnhancedBatchEmbeddingProcessor(redis_url, openai_api_key, instance)
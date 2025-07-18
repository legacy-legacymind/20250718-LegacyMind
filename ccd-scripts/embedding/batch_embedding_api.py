#!/usr/bin/env python3
"""
Batch Embedding REST API for unified-intelligence
Provides HTTP endpoints for batch embedding processing with job management.
Phase 1A implementation of the dual-storage embedding optimization plan.
"""

import os
import sys
import json
import asyncio
import redis
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
import uvicorn

# Add the current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append('/Users/samuelatagana/Projects/LegacyMind/worktrees/CCD/unified-intelligence')

from batch_embedding_processor import EnhancedBatchEmbeddingProcessor, JobStatus
from federation_auto_discovery import FederationAutoDiscovery


async def process_instance_embeddings(service, missing_thoughts, instance_name, batch_size, delay):
    """Background task to process embeddings for a specific instance"""
    try:
        print(f"Starting embedding processing for {instance_name}: {len(missing_thoughts)} thoughts")
        
        success_count = 0
        error_count = 0
        
        # Process in batches
        for i in range(0, len(missing_thoughts), batch_size):
            batch = missing_thoughts[i:i + batch_size]
            print(f"{instance_name}: Processing batch {i//batch_size + 1}: thoughts {i+1}-{min(i+batch_size, len(missing_thoughts))}")
            
            # Process batch with enhanced service (Phase 1B binary storage)
            for thought in batch:
                try:
                    success = service.store_thought_embedding(
                        thought['thought_id'],
                        thought['content'],
                        thought['timestamp']
                    )
                    
                    if success:
                        success_count += 1
                        print(f"✓ {instance_name}: Generated embedding for {thought['thought_id']}")
                    else:
                        error_count += 1
                        print(f"✗ {instance_name}: Failed to generate embedding for {thought['thought_id']}")
                
                except Exception as e:
                    error_count += 1
                    print(f"✗ {instance_name}: Error processing {thought['thought_id']}: {e}")
            
            # Delay between batches
            if i + batch_size < len(missing_thoughts):
                await asyncio.sleep(delay)
        
        print(f"Completed {instance_name}: {success_count} success, {error_count} errors")
        
    except Exception as e:
        print(f"Error processing embeddings for {instance_name}: {e}")


# Pydantic models for API requests/responses
class BatchJobRequest(BaseModel):
    """Request to start a batch embedding job"""
    instance: Optional[str] = Field(default="Claude", description="Federation instance name")
    batch_size: Optional[int] = Field(default=50, ge=1, le=100, description="Batch size for processing (1-100)")
    delay: Optional[float] = Field(default=0.02, ge=0.01, le=1.0, description="Delay between batches in seconds")


class BatchJobResponse(BaseModel):
    """Response when creating a batch job"""
    job_id: str
    instance: str
    total_thoughts: int
    status: str
    created_at: str


class JobStatusResponse(BaseModel):
    """Response for job status requests"""
    job_id: str
    instance: str
    status: str
    total_thoughts: int
    processed: int
    success: int
    errors: int
    progress_percentage: float
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Response for current state analysis"""
    instance: str
    total_thoughts: int
    total_embeddings: int
    missing_embeddings: int
    coverage_percentage: float
    analysis_timestamp: str


class MissingThoughtsResponse(BaseModel):
    """Response for listing missing thoughts"""
    instance: str
    missing_count: int
    thoughts: List[Dict]
    preview_limit: int


# Global processor instance
processor: Optional[EnhancedBatchEmbeddingProcessor] = None


def get_processor() -> EnhancedBatchEmbeddingProcessor:
    """Get or create the batch embedding processor"""
    global processor
    
    if processor is None:
        # Get configuration from environment
        redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        redis_url = f"redis://:{redis_password}@localhost:6379/0"
        instance = os.getenv('INSTANCE_ID', 'Claude')
        
        # Get OpenAI API key
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            import redis
            try:
                temp_redis = redis.from_url(redis_url)
                openai_api_key = temp_redis.get('config:openai_api_key')
                if openai_api_key:
                    openai_api_key = openai_api_key.decode('utf-8') if isinstance(openai_api_key, bytes) else openai_api_key
            except Exception:
                pass
        
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        processor = EnhancedBatchEmbeddingProcessor(redis_url, openai_api_key, instance)
    
    return processor


# FastAPI app initialization
app = FastAPI(
    title="Batch Embedding API",
    description="REST API for batch embedding processing in unified-intelligence federation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


@app.get("/")
async def root():
    """API root endpoint with basic information"""
    return {
        "service": "Batch Embedding API",
        "version": "1.0.0",
        "description": "Phase 1A implementation of dual-storage embedding optimization",
        "endpoints": {
            "POST /batch/process": "Start batch embedding job",
            "GET /batch/status/{job_id}": "Get job status",
            "GET /batch/jobs": "List all active jobs",
            "GET /batch/analyze": "Analyze current embedding state",
            "GET /batch/missing": "List thoughts without embeddings",
            "GET /health": "Health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        proc = get_processor()
        # Simple Redis connectivity check
        state = proc.analyze_current_state()
        if 'error' in state:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "error": state['error']}
            )
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "redis_connected": True,
            "embedding_service": proc.embedding_service is not None
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.post("/batch/process", response_model=BatchJobResponse)
async def start_batch_processing(
    request: BatchJobRequest,
    background_tasks: BackgroundTasks
):
    """Start a new batch embedding job for a specific instance"""
    try:
        proc = get_processor()
        
        # Create batch job
        thoughts = proc.get_thoughts_without_embeddings()
        if not thoughts:
            raise HTTPException(status_code=404, detail="No thoughts found that need embeddings")
        
        job_id = proc.create_batch_job(thoughts)
        
        # Start background processing
        background_tasks.add_task(
            proc.process_batch_async,
            job_id,
            request.batch_size,
            request.delay
        )
        
        return BatchJobResponse(
            job_id=job_id,
            instance=request.instance or "Claude",
            total_thoughts=len(thoughts),
            status="pending",
            created_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch/process-federation")
async def start_federation_processing(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(default=50, ge=1, le=100),
    delay: float = Query(default=0.02, ge=0.01, le=1.0)
):
    """Start batch embedding jobs for ALL federation instances with missing embeddings"""
    try:
        # Get Redis connection
        redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        redis_url = f"redis://:{redis_password}@localhost:6379/0"
        redis_client = redis.from_url(redis_url)
        
        # Get OpenAI API key
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            try:
                openai_api_key = redis_client.get('config:openai_api_key')
                if openai_api_key:
                    openai_api_key = openai_api_key.decode('utf-8')
            except Exception:
                pass
        
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        # Discover all federation instances
        discovery = FederationAutoDiscovery(redis_client)
        instances = discovery.discover_federation_instances()
        
        # Filter instances with missing embeddings
        instances_with_missing = [i for i in instances if i.missing_embeddings > 0]
        
        if not instances_with_missing:
            return {
                "message": "No federation instances have missing embeddings",
                "federation_summary": discovery.get_federation_summary()
            }
        
        # Start processing jobs for each instance
        job_results = []
        for instance in instances_with_missing:
            try:
                # Create processor for this instance
                from enhanced_embedding_service import EnhancedEmbeddingService
                service = EnhancedEmbeddingService(
                    redis_url=redis_url,
                    openai_api_key=openai_api_key,
                    instance=instance.name,
                    use_binary_storage=True,  # Use Phase 1B binary optimization
                    auto_migrate=False
                )
                
                # Get missing thoughts for this instance
                missing_thoughts = discovery.get_thoughts_without_embeddings(instance.name)
                
                if missing_thoughts:
                    # Start background processing for this instance
                    background_tasks.add_task(
                        process_instance_embeddings,
                        service,
                        missing_thoughts,
                        instance.name,
                        batch_size,
                        delay
                    )
                    
                    job_results.append({
                        "instance": instance.name,
                        "thoughts_to_process": len(missing_thoughts),
                        "status": "started",
                        "batch_size": batch_size
                    })
                
            except Exception as e:
                job_results.append({
                    "instance": instance.name,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "message": f"Started embedding jobs for {len(job_results)} federation instances",
            "jobs": job_results,
            "federation_summary": discovery.get_federation_summary(),
            "total_thoughts_queued": sum(j.get("thoughts_to_process", 0) for j in job_results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/batch/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get the status of a specific batch job"""
    try:
        proc = get_processor()
        job = proc.get_job_status(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        progress_percentage = (job.processed / job.total_thoughts * 100) if job.total_thoughts > 0 else 0
        
        return JobStatusResponse(
            job_id=job.job_id,
            instance=job.instance,
            status=job.status.value,
            total_thoughts=job.total_thoughts,
            processed=job.processed,
            success=job.success,
            errors=job.errors,
            progress_percentage=round(progress_percentage, 2),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            error_message=job.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/batch/jobs")
async def list_active_jobs():
    """List all active batch jobs"""
    try:
        proc = get_processor()
        jobs = proc.list_active_jobs()
        return {
            "active_jobs": jobs,
            "total_jobs": len(jobs),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/batch/analyze")
async def analyze_current_state():
    """Analyze the current state of thoughts and embeddings across all federation instances"""
    try:
        proc = get_processor()
        
        # Get federation-wide analysis using auto-discovery
        discovery = FederationAutoDiscovery(proc.redis_client)
        federation_summary = discovery.get_federation_summary()
        
        return federation_summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/batch/missing", response_model=MissingThoughtsResponse)
async def list_missing_thoughts(
    limit: int = Query(default=10, ge=1, le=100, description="Number of thoughts to return (1-100)"),
    instance: Optional[str] = Query(default=None, description="Filter by instance")
):
    """List thoughts that are missing embeddings"""
    try:
        proc = get_processor()
        
        # Override instance if specified
        if instance and instance != proc.instance:
            # Create temporary processor for different instance
            temp_proc = EnhancedBatchEmbeddingProcessor(proc.redis_url, proc.openai_api_key, instance)
            missing_thoughts = temp_proc.get_thoughts_without_embeddings()
        else:
            missing_thoughts = proc.get_thoughts_without_embeddings()
        
        # Convert ThoughtRecord objects to dictionaries and limit results
        thoughts_list = []
        for thought in missing_thoughts[:limit]:
            content_preview = thought.content[:100] + "..." if len(thought.content) > 100 else thought.content
            thoughts_list.append({
                "thought_id": thought.thought_id,
                "content_preview": content_preview,
                "timestamp": thought.timestamp,
                "key": thought.key
            })
        
        return MissingThoughtsResponse(
            instance=instance or proc.instance,
            missing_count=len(missing_thoughts),
            thoughts=thoughts_list,
            preview_limit=limit
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/batch/job/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running batch job"""
    try:
        proc = get_processor()
        job = proc.get_job_status(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail=f"Job is already {job.status.value}")
        
        # Update job status to cancelled
        proc.update_job_status(job_id, status=JobStatus.CANCELLED, completed_at=datetime.now())
        
        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job cancellation requested",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the API server"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch Embedding API Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    parser.add_argument('--workers', type=int, default=1, help='Number of worker processes')
    
    args = parser.parse_args()
    
    print(f"Starting Batch Embedding API server on {args.host}:{args.port}")
    print("API Documentation available at:")
    print(f"  Swagger UI: http://{args.host}:{args.port}/docs")
    print(f"  ReDoc: http://{args.host}:{args.port}/redoc")
    
    uvicorn.run(
        "batch_embedding_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level="info"
    )


if __name__ == "__main__":
    main()
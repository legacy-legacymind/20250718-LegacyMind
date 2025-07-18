#!/usr/bin/env python3
"""
Phase 3: FastAPI Server with gRPC Qdrant Integration
Combines all optimizations: batch API, binary storage, semantic caching, dual storage, gRPC
"""

import os
import sys
import asyncio
import redis
import json
import time
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from phase3_embedding_service import Phase3EmbeddingService


class EmbedRequest(BaseModel):
    thought_id: str
    content: str
    instance: str = "CCD"


class BatchEmbedRequest(BaseModel):
    thoughts: List[EmbedRequest]


class Phase3Status(BaseModel):
    phase: int = 3
    status: str
    features: List[str]
    performance: Dict[str, Any]
    uptime: float


# Global service instance
service: Optional[Phase3EmbeddingService] = None
start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service lifecycle"""
    global service
    
    # Startup
    print("🚀 Starting Phase 3 Embedding API...")
    
    # Get configuration
    redis_password = os.getenv("REDIS_PASSWORD", "")
    redis_url = f"redis://:{redis_password}@localhost:6379" if redis_password else "redis://localhost:6379"
    
    # Get API keys
    openai_api_key = os.getenv("OPENAI_API_KEY")
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not openai_api_key:
        try:
            r = redis.from_url(redis_url)
            openai_api_key = r.get("OPENAI_API_KEY")
            if openai_api_key:
                openai_api_key = openai_api_key.decode()
        except:
            pass
    
    if not groq_api_key:
        try:
            r = redis.from_url(redis_url)
            groq_api_key = r.get("config:groq_api_key")
            if groq_api_key:
                groq_api_key = groq_api_key.decode()
        except:
            pass
    
    if not openai_api_key:
        print("❌ No OpenAI API key found - limited functionality")
        openai_api_key = None  # Ensure it's None, not empty string
    
    if not groq_api_key:
        print("❌ No Groq API key found - no fallback available")
        groq_api_key = None
    
    # Initialize service
    service = Phase3EmbeddingService(redis_url, openai_api_key, groq_api_key)
    await service.initialize()
    
    print("✅ Phase 3 API ready!")
    
    yield
    
    # Shutdown
    print("👋 Shutting down Phase 3 API...")
    if service:
        await service.close()


app = FastAPI(
    title="Phase 3 Embedding API",
    description="Optimized embedding service with gRPC Qdrant, semantic caching, and dual storage",
    version="3.0.0",
    lifespan=lifespan
)


@app.get("/", response_model=Phase3Status)
async def root():
    """Get API status and metrics"""
    if not service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    metrics = service.get_metrics_summary()
    uptime = time.time() - start_time
    
    return Phase3Status(
        status="operational",
        features=[
            "Batch embedding API (50% cost reduction)",
            "Binary vector storage (75% memory savings)",
            "Semantic caching (30-40% API reduction)",
            "Dual storage (Redis + Qdrant)",
            "gRPC Qdrant optimization (10x performance)",
            "HNSW index tuning",
            "Federation auto-discovery",
            "Groq fallback for resilience",
            "Automatic recovery to OpenAI"
        ],
        performance=metrics,
        uptime=uptime
    )


@app.post("/v3/embed")
async def embed_single(request: EmbedRequest):
    """Embed a single thought with Phase 3 optimizations"""
    if not service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    result = await service.embed_with_full_optimization(
        request.thought_id,
        request.content,
        request.instance
    )
    
    if result['status'] == 'error':
        raise HTTPException(status_code=500, detail=result.get('message', 'Embedding failed'))
    
    return {
        "thought_id": request.thought_id,
        "status": result['status'],
        "cached": result['status'] == 'cached',
        "storage": result.get('storage', 'unknown'),
        "processing_time": result.get('time', 0),
        "provider": result.get('provider', 'unknown'),
        "fallback_used": result.get('fallback_used', False)
    }


@app.post("/v3/embed/batch")
async def embed_batch(request: BatchEmbedRequest, background_tasks: BackgroundTasks):
    """Batch embed multiple thoughts"""
    if not service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Process in background for large batches
    if len(request.thoughts) > 10:
        task_id = str(uuid.uuid4())
        background_tasks.add_task(
            process_batch_background,
            request.thoughts,
            task_id
        )
        
        return {
            "status": "processing",
            "task_id": task_id,
            "thoughts_count": len(request.thoughts),
            "message": "Large batch queued for background processing"
        }
    
    # Process small batches immediately
    results = []
    for thought in request.thoughts:
        result = await service.embed_with_full_optimization(
            thought.thought_id,
            thought.content,
            thought.instance
        )
        results.append({
            "thought_id": thought.thought_id,
            "status": result['status'],
            "cached": result['status'] == 'cached'
        })
    
    return {
        "status": "completed",
        "thoughts_processed": len(results),
        "results": results
    }


async def process_batch_background(thoughts: List[EmbedRequest], task_id: str):
    """Process batch in background"""
    print(f"🔄 Processing batch {task_id} with {len(thoughts)} thoughts...")
    
    processed = 0
    for thought in thoughts:
        try:
            await service.embed_with_full_optimization(
                thought.thought_id,
                thought.content,
                thought.instance
            )
            processed += 1
        except Exception as e:
            print(f"  Error processing {thought.thought_id}: {e}")
    
    print(f"✅ Batch {task_id} completed: {processed}/{len(thoughts)} processed")


@app.post("/v3/embed/federation")
async def embed_federation(background_tasks: BackgroundTasks):
    """Process all federation instances"""
    if not service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    task_id = str(uuid.uuid4())
    background_tasks.add_task(process_federation_background, task_id)
    
    return {
        "status": "processing",
        "task_id": task_id,
        "message": "Federation embedding started in background"
    }


async def process_federation_background(task_id: str):
    """Process federation in background"""
    print(f"🔄 Processing federation batch {task_id}...")
    
    try:
        total = await service.batch_embed_federation(batch_size=50)
        print(f"✅ Federation batch {task_id} completed: {total} embeddings generated")
    except Exception as e:
        print(f"❌ Federation batch {task_id} failed: {e}")


@app.get("/v3/metrics")
async def get_metrics():
    """Get detailed metrics"""
    if not service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    metrics = service.get_metrics_summary()
    
    # Add Qdrant status
    qdrant_status = "connected" if service.qdrant_connected else "disconnected"
    
    # Get collection info if connected
    collection_info = {}
    if service.qdrant_connected:
        try:
            collection_info = await service.qdrant_client.get_collection_info("thoughts")
        except:
            pass
    
    return {
        "phase": 3,
        "metrics": metrics,
        "qdrant": {
            "status": qdrant_status,
            "collection": collection_info
        },
        "uptime": time.time() - start_time
    }


@app.get("/v3/search/{thought_id}")
async def search_similar(thought_id: str, limit: int = 10):
    """Search for similar thoughts using Qdrant"""
    if not service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not service.qdrant_connected:
        raise HTTPException(status_code=503, detail="Qdrant not connected")
    
    # Get the embedding for this thought
    r = redis.from_url(service.redis_url)
    
    # Try all instances
    embedding = None
    instance = None
    for inst in ["CC", "CCI", "CCD", "CCS", "DT", "Claude"]:
        embedding_data = r.hget(f"embeddings:{inst}", thought_id)
        if embedding_data:
            instance = inst
            # Decode binary embedding
            import struct
            embedding = list(struct.unpack(f'{1536}f', embedding_data))
            break
    
    if not embedding:
        raise HTTPException(status_code=404, detail="Thought embedding not found")
    
    # Search similar
    results = await service.qdrant_client.search_similar(
        "thoughts",
        embedding,
        limit=limit
    )
    
    return {
        "thought_id": thought_id,
        "instance": instance,
        "similar_thoughts": results
    }


@app.post("/v3/recovery/run")
async def run_recovery():
    """Manually trigger recovery process"""
    if not service or not service.recovery_service:
        raise HTTPException(status_code=503, detail="Recovery service not available")
    
    # Run recovery scan and processing
    await service.recovery_service.run_recovery_scan()
    await service.recovery_service.process_recovery_queue()
    
    stats = service.recovery_service.get_recovery_stats()
    
    return {
        "status": "completed",
        "message": "Recovery process completed",
        "stats": stats
    }


@app.get("/v3/recovery/status")
async def get_recovery_status():
    """Get recovery service status"""
    if not service or not service.recovery_service:
        raise HTTPException(status_code=503, detail="Recovery service not available")
    
    stats = service.recovery_service.get_recovery_stats()
    
    return {
        "recovery_service": "active",
        "openai_available": service.recovery_service.is_openai_available(),
        "stats": stats
    }


def main():
    """Run the Phase 3 API server"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 3 Embedding API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8004, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    print(f"🚀 Starting Phase 3 API on {args.host}:{args.port}")
    print(f"📊 Features: gRPC, semantic caching, dual storage, batch API")
    print(f"🔗 API docs: http://{args.host}:{args.port}/docs")
    
    uvicorn.run(
        "phase3_embedding_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
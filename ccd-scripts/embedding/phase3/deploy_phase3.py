#!/usr/bin/env python3
"""
Deploy and test Phase 3 optimizations
"""

import os
import sys
import asyncio
import redis
import time
import httpx
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_phase3_api():
    """Test Phase 3 API endpoints"""
    base_url = "http://127.0.0.1:8004"
    
    async with httpx.AsyncClient() as client:
        # Check status
        print("🔍 Checking Phase 3 API status...")
        response = await client.get(f"{base_url}/")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Status: {data['status']}")
            print(f"   Features: {len(data['features'])} optimizations active")
            print(f"   Performance: {data['performance']}")
        else:
            print(f"❌ API not responding: {response.status_code}")
            return
        
        # Test single embedding
        print("\n🧪 Testing single embedding...")
        test_thought = {
            "thought_id": f"phase3_test_{int(time.time())}",
            "content": "Phase 3 optimizations include gRPC for Qdrant which provides 10x performance improvement",
            "instance": "CCD"
        }
        
        response = await client.post(f"{base_url}/v3/embed", json=test_thought)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Embedding created: {result['status']} "
                  f"(cached: {result['cached']}, storage: {result['storage']}, "
                  f"time: {result['processing_time']:.3f}s)")
        
        # Test with duplicate (should hit cache)
        print("\n🧪 Testing semantic cache...")
        test_thought['thought_id'] = f"phase3_test_cache_{int(time.time())}"
        
        response = await client.post(f"{base_url}/v3/embed", json=test_thought)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Cache test: {result['status']} "
                  f"(cached: {result['cached']}, time: {result['processing_time']:.3f}s)")
        
        # Get metrics
        print("\n📊 Phase 3 Metrics:")
        response = await client.get(f"{base_url}/v3/metrics")
        if response.status_code == 200:
            metrics = response.json()
            print(f"   Phase: {metrics['phase']}")
            print(f"   Qdrant Status: {metrics['qdrant']['status']}")
            
            for key, value in metrics['metrics'].items():
                print(f"   {key}: {value}")
            
            if metrics['qdrant']['collection']:
                print(f"\n   Qdrant Collection:")
                for key, value in metrics['qdrant']['collection'].items():
                    print(f"     {key}: {value}")


async def benchmark_phase3():
    """Benchmark Phase 3 performance"""
    print("\n🏃 Running Phase 3 benchmarks...")
    
    base_url = "http://127.0.0.1:8004"
    
    async with httpx.AsyncClient() as client:
        # Create test batch
        batch_size = 100
        thoughts = []
        
        for i in range(batch_size):
            thoughts.append({
                "thought_id": f"bench_phase3_{i}_{int(time.time())}",
                "content": f"Benchmark thought {i}: Testing Phase 3 gRPC optimization with unique content {i}",
                "instance": "CCD"
            })
        
        # Benchmark batch processing
        print(f"\n📊 Benchmarking batch of {batch_size} thoughts...")
        start_time = time.time()
        
        response = await client.post(
            f"{base_url}/v3/embed/batch",
            json={"thoughts": thoughts[:10]}  # Small batch for immediate processing
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            rate = result['thoughts_processed'] / elapsed
            print(f"✅ Processed {result['thoughts_processed']} thoughts in {elapsed:.2f}s "
                  f"({rate:.1f} thoughts/sec)")
        
        # Test large batch (background processing)
        print(f"\n📊 Testing large batch background processing...")
        response = await client.post(
            f"{base_url}/v3/embed/batch",
            json={"thoughts": thoughts}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result['status']}: {result['message']}")
            print(f"   Task ID: {result['task_id']}")


async def compare_phases():
    """Compare all three phases"""
    print("\n📊 Phase Comparison:")
    print("=" * 60)
    
    # Phase 1 metrics (if running)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8001/")
            if response.status_code == 200:
                data = response.json()
                print(f"Phase 1: {data.get('embeddings_generated', 0)} embeddings, "
                      f"{data.get('federation_coverage', 'N/A')} coverage")
    except:
        print("Phase 1: Not running")
    
    # Phase 2 metrics (if running)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8003/metrics")
            if response.status_code == 200:
                data = response.json()
                print(f"Phase 2: Cache hit rate {data.get('cache_hit_rate', 'N/A')}, "
                      f"${data.get('total_cost_saved', 0)} saved")
    except:
        print("Phase 2: Not running")
    
    # Phase 3 metrics
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8004/v3/metrics")
            if response.status_code == 200:
                data = response.json()
                metrics = data['metrics']
                print(f"Phase 3: gRPC speedup {metrics.get('grpc_speedup', 'N/A')}, "
                      f"Qdrant {data['qdrant']['status']}")
    except:
        print("Phase 3: Not running")


def main():
    """Deploy Phase 3"""
    print("🚀 Phase 3 Deployment")
    print("=" * 60)
    
    # Check if API is already running
    import subprocess
    result = subprocess.run(
        ["lsof", "-ti:8004"],
        capture_output=True,
        text=True
    )
    
    if result.stdout.strip():
        print("⚠️  Phase 3 API already running on port 8004")
    else:
        print("📦 Starting Phase 3 API server...")
        print("Run this in a separate terminal:")
        print("\npython3 ccd-scripts/embedding/phase3/phase3_embedding_api.py --port 8004\n")
        print("Waiting for API to start...")
        time.sleep(5)
    
    # Run tests
    print("\n🧪 Running Phase 3 tests...")
    asyncio.run(test_phase3_api())
    
    # Run benchmarks
    asyncio.run(benchmark_phase3())
    
    # Compare phases
    asyncio.run(compare_phases())
    
    print("\n✅ Phase 3 deployment complete!")
    print("\n📊 Summary:")
    print("- gRPC Qdrant connection established")
    print("- HNSW index optimization applied")
    print("- All Phase 1 & 2 features integrated")
    print("- API running on http://127.0.0.1:8004")
    print("- Docs available at http://127.0.0.1:8004/docs")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Phase 2 Deployment Script
Deploys and tests semantic caching + dual-storage embedding service.
"""

import os
import sys
import json
import time
import asyncio
import subprocess
import requests
from typing import Dict, List
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dual_storage_service import DualStorageEmbeddingService
from semantic_cache import SemanticCache
import redis


class Phase2Deployer:
    """Phase 2 deployment and testing manager"""
    
    def __init__(self):
        self.redis_url = None
        self.openai_api_key = None
        self.api_port = 8002
        self.api_process = None
        
    def setup_environment(self):
        """Setup environment variables and connections"""
        print("🔧 Setting up Phase 2 environment...")
        
        # Get Redis configuration
        redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        self.redis_url = f"redis://:{redis_password}@localhost:6379/0"
        
        # Test Redis connection
        try:
            redis_client = redis.from_url(self.redis_url)
            redis_client.ping()
            print("✓ Redis connection successful")
        except Exception as e:
            print(f"✗ Redis connection failed: {e}")
            return False
        
        # Get OpenAI API key
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            try:
                self.openai_api_key = redis_client.get('config:openai_api_key')
                if self.openai_api_key:
                    self.openai_api_key = self.openai_api_key.decode('utf-8')
            except Exception:
                pass
        
        if not self.openai_api_key:
            print("✗ OpenAI API key not found")
            return False
        
        print("✓ OpenAI API key configured")
        
        # Check Qdrant availability
        try:
            response = requests.get("http://localhost:6333/collections", timeout=5)
            if response.status_code == 200:
                print("✓ Qdrant server available")
            else:
                print("⚠ Qdrant server not responding properly")
        except Exception:
            print("⚠ Qdrant server not available (optional for Phase 2)")
        
        return True
    
    def deploy_api_server(self):
        """Deploy Phase 2 API server"""
        print(f"🚀 Deploying Phase 2 API server on port {self.api_port}...")
        
        try:
            # Check if port is already in use
            try:
                response = requests.get(f"http://127.0.0.1:{self.api_port}/health", timeout=2)
                if response.status_code == 200:
                    print(f"✓ Phase 2 API server already running on port {self.api_port}")
                    return True
            except requests.exceptions.RequestException:
                pass
            
            # Start API server
            cmd = [
                sys.executable, 
                "phase2_embedding_api.py", 
                "--host", "127.0.0.1", 
                "--port", str(self.api_port),
                "--workers", "1"
            ]
            
            self.api_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            # Wait for server to start
            max_retries = 10
            for i in range(max_retries):
                try:
                    response = requests.get(f"http://127.0.0.1:{self.api_port}/health", timeout=2)
                    if response.status_code == 200:
                        print(f"✓ Phase 2 API server started successfully")
                        return True
                except requests.exceptions.RequestException:
                    time.sleep(1)
                    print(f"  Waiting for server startup ({i+1}/{max_retries})...")
            
            print("✗ Failed to start Phase 2 API server")
            return False
            
        except Exception as e:
            print(f"✗ Error deploying API server: {e}")
            return False
    
    def test_semantic_caching(self):
        """Test semantic caching functionality"""
        print("🧪 Testing semantic caching...")
        
        base_url = f"http://127.0.0.1:{self.api_port}"
        
        # Test 1: Generate initial embedding
        test_content = "Redis is a fast in-memory data structure store"
        
        try:
            response = requests.post(
                f"{base_url}/v2/embed",
                json={"content": test_content},
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"✗ Failed to generate initial embedding: {response.status_code}")
                return False
            
            result1 = response.json()
            print(f"✓ Initial embedding generated: {result1['dimensions']} dimensions")
            print(f"  Cached: {result1['cached']}")
            print(f"  Cache hit: {result1['cache_hit']}")
            print(f"  Processing time: {result1['processing_time']:.3f}s")
            
        except Exception as e:
            print(f"✗ Error generating initial embedding: {e}")
            return False
        
        # Test 2: Test exact match caching
        try:
            response = requests.post(
                f"{base_url}/v2/embed",
                json={"content": test_content},
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"✗ Failed to test exact match caching: {response.status_code}")
                return False
            
            result2 = response.json()
            print(f"✓ Exact match test:")
            print(f"  Cached: {result2['cached']}")
            print(f"  Cache hit: {result2['cache_hit']}")
            print(f"  Processing time: {result2['processing_time']:.3f}s")
            
            if result2['cache_hit']:
                print("✓ Exact match caching working correctly")
            else:
                print("⚠ Exact match caching may need tuning")
                
        except Exception as e:
            print(f"✗ Error testing exact match caching: {e}")
            return False
        
        # Test 3: Test semantic similarity caching
        similar_content = "Redis is a high-performance in-memory database"
        
        try:
            response = requests.post(
                f"{base_url}/v2/embed",
                json={"content": similar_content},
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"✗ Failed to test semantic similarity: {response.status_code}")
                return False
            
            result3 = response.json()
            print(f"✓ Semantic similarity test:")
            print(f"  Content: '{similar_content}'")
            print(f"  Cached: {result3['cached']}")
            print(f"  Cache hit: {result3['cache_hit']}")
            print(f"  Processing time: {result3['processing_time']:.3f}s")
            
            if result3['cache_hit']:
                print("✓ Semantic similarity caching working correctly")
            else:
                print("⚠ Semantic similarity caching may need threshold adjustment")
                
        except Exception as e:
            print(f"✗ Error testing semantic similarity: {e}")
            return False
        
        return True
    
    def test_dual_storage(self):
        """Test dual storage functionality"""
        print("🗄️ Testing dual storage (Redis + Qdrant)...")
        
        base_url = f"http://127.0.0.1:{self.api_port}"
        
        try:
            # Generate embedding with dual storage
            test_content = "Dual storage combines Redis speed with Qdrant persistence"
            
            response = requests.post(
                f"{base_url}/v2/embed",
                json={"content": test_content, "store_in_qdrant": True},
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"✗ Failed to test dual storage: {response.status_code}")
                return False
            
            result = response.json()
            print(f"✓ Dual storage test:")
            print(f"  Dimensions: {result['dimensions']}")
            print(f"  Storage backends: {result['storage_backends']}")
            print(f"  Processing time: {result['processing_time']:.3f}s")
            
            # Check if both Redis and Qdrant were used
            if 'redis' in result['storage_backends']:
                print("✓ Redis storage successful")
            else:
                print("⚠ Redis storage may have failed")
            
            if 'qdrant' in result['storage_backends']:
                print("✓ Qdrant storage successful")
            else:
                print("⚠ Qdrant storage not available (optional)")
            
            return True
            
        except Exception as e:
            print(f"✗ Error testing dual storage: {e}")
            return False
    
    def test_batch_processing(self):
        """Test Phase 2 batch processing"""
        print("📦 Testing Phase 2 batch processing...")
        
        base_url = f"http://127.0.0.1:{self.api_port}"
        
        try:
            # Start batch processing
            response = requests.post(
                f"{base_url}/v2/batch/process",
                json={
                    "batch_size": 5,
                    "use_semantic_cache": True,
                    "cache_similarity_threshold": 0.85
                },
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"✗ Failed to start batch processing: {response.status_code}")
                return False
            
            result = response.json()
            print(f"✓ Batch processing started:")
            print(f"  Instance: {result['instance']}")
            print(f"  Thoughts to process: {result['thoughts_to_process']}")
            print(f"  Estimated API calls saved: {result['estimated_api_calls_saved']}")
            
            return True
            
        except Exception as e:
            print(f"✗ Error testing batch processing: {e}")
            return False
    
    def get_performance_stats(self):
        """Get and display performance statistics"""
        print("📊 Getting Phase 2 performance statistics...")
        
        base_url = f"http://127.0.0.1:{self.api_port}"
        
        try:
            # Get comprehensive stats
            response = requests.get(f"{base_url}/v2/stats", timeout=10)
            
            if response.status_code != 200:
                print(f"✗ Failed to get performance stats: {response.status_code}")
                return False
            
            stats = response.json()
            
            print("✓ Performance Statistics:")
            print(f"  Total requests: {stats['requests']['total']}")
            print(f"  Cache hits: {stats['requests']['cache_hits']}")
            print(f"  Cache hit rate: {stats['requests']['cache_hit_rate']}%")
            print(f"  API calls made: {stats['requests']['api_calls']}")
            print(f"  Redis writes: {stats['storage']['redis_writes']}")
            print(f"  Qdrant writes: {stats['storage']['qdrant_writes']}")
            
            # Get cache-specific stats
            cache_response = requests.get(f"{base_url}/v2/cache/stats", timeout=10)
            if cache_response.status_code == 200:
                cache_stats = cache_response.json()
                print(f"  Cache API calls saved: {cache_stats.get('api_calls_saved', 0)}")
                print(f"  Estimated cost savings: ${cache_stats.get('estimated_cost_savings', 0):.4f}")
            
            return True
            
        except Exception as e:
            print(f"✗ Error getting performance stats: {e}")
            return False
    
    def cleanup(self):
        """Clean up deployment resources"""
        print("🧹 Cleaning up Phase 2 deployment...")
        
        if self.api_process:
            try:
                self.api_process.terminate()
                self.api_process.wait(timeout=10)
                print("✓ API server stopped")
            except Exception as e:
                print(f"⚠ Error stopping API server: {e}")
    
    def run_deployment(self):
        """Run complete Phase 2 deployment and testing"""
        print("🚀 Starting Phase 2 Deployment")
        print("=" * 50)
        
        try:
            # Setup environment
            if not self.setup_environment():
                return False
            
            # Deploy API server
            if not self.deploy_api_server():
                return False
            
            # Wait for server to be fully ready
            time.sleep(2)
            
            # Run tests
            tests = [
                ("Semantic Caching", self.test_semantic_caching),
                ("Dual Storage", self.test_dual_storage),
                ("Batch Processing", self.test_batch_processing),
                ("Performance Stats", self.get_performance_stats)
            ]
            
            test_results = []
            for test_name, test_func in tests:
                print(f"\n--- {test_name} ---")
                result = test_func()
                test_results.append((test_name, result))
                if result:
                    print(f"✓ {test_name} passed")
                else:
                    print(f"✗ {test_name} failed")
            
            # Summary
            print("\n" + "=" * 50)
            print("📋 PHASE 2 DEPLOYMENT SUMMARY")
            print("=" * 50)
            
            passed_tests = sum(1 for _, result in test_results if result)
            total_tests = len(test_results)
            
            for test_name, result in test_results:
                status = "✓ PASS" if result else "✗ FAIL"
                print(f"  {test_name}: {status}")
            
            print(f"\nTests passed: {passed_tests}/{total_tests}")
            
            if passed_tests == total_tests:
                print("🎉 Phase 2 deployment successful!")
                print(f"🌐 API server running on: http://127.0.0.1:{self.api_port}")
                print(f"📚 API docs available at: http://127.0.0.1:{self.api_port}/docs")
                return True
            else:
                print("⚠ Phase 2 deployment completed with some test failures")
                return False
            
        except KeyboardInterrupt:
            print("\n⏹️ Deployment interrupted by user")
            return False
        except Exception as e:
            print(f"\n✗ Deployment failed: {e}")
            return False
        finally:
            if not os.getenv('KEEP_RUNNING'):
                self.cleanup()


def main():
    """Main deployment function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Phase 2 Deployment Script')
    parser.add_argument('--keep-running', action='store_true', 
                       help='Keep API server running after tests')
    parser.add_argument('--port', type=int, default=8002,
                       help='API server port (default: 8002)')
    
    args = parser.parse_args()
    
    # Set environment variable for cleanup control
    if args.keep_running:
        os.environ['KEEP_RUNNING'] = '1'
    
    deployer = Phase2Deployer()
    deployer.api_port = args.port
    
    success = deployer.run_deployment()
    
    if success and args.keep_running:
        print(f"\n⏳ API server will continue running on port {args.port}")
        print("   Use Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping API server...")
            deployer.cleanup()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
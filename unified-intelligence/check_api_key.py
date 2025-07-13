#!/usr/bin/env python3
"""
Check OpenAI API key retrieval for background service
"""

import asyncio
import os
import redis.asyncio as redis

async def check_api_key_sources():
    """Check all possible sources for OpenAI API key"""
    print("Checking OpenAI API key sources...")
    print("=" * 50)
    
    # Check environment variable
    env_key = os.getenv('OPENAI_API_KEY')
    if env_key:
        print(f"✅ Environment variable: Found ({len(env_key)} characters)")
    else:
        print("❌ Environment variable: Not found")
    
    # Check Redis
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    try:
        test_redis = redis.from_url(redis_url, decode_responses=True)
        await test_redis.ping()
        print("✅ Redis connection: OK")
        
        redis_key = await test_redis.get('config:openai_api_key')
        if redis_key:
            print(f"✅ Redis storage: Found ({len(redis_key)} characters)")
            
            # Verify it's a valid format (starts with sk-)
            if redis_key.startswith('sk-'):
                print("✅ API key format: Valid (starts with sk-)")
            else:
                print("⚠️  API key format: Unusual (doesn't start with sk-)")
                
        else:
            print("❌ Redis storage: Not found")
            
        await test_redis.aclose()
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False
    
    # Determine which source the service will use
    print("\n" + "=" * 50)
    print("Background service will use:")
    
    if env_key:
        print(f"✅ Environment variable ({len(env_key)} chars)")
        return True
    elif redis_key:
        print(f"✅ Redis storage ({len(redis_key)} chars)")
        return True
    else:
        print("❌ No API key found!")
        return False

async def test_api_key_with_openai():
    """Test the API key actually works with OpenAI"""
    print("\nTesting API key with OpenAI...")
    print("=" * 50)
    
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    # Get API key (same logic as background service)
    api_key = os.getenv('OPENAI_API_KEY')
    source = "environment"
    
    if not api_key:
        try:
            test_redis = redis.from_url(redis_url, decode_responses=True)
            api_key = await test_redis.get('config:openai_api_key')
            await test_redis.aclose()
            source = "Redis"
        except Exception as e:
            print(f"❌ Error retrieving from Redis: {e}")
            return False
    
    if not api_key:
        print("❌ No API key available for testing")
        return False
    
    print(f"📋 Using API key from {source} ({len(api_key)} chars)")
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Test with a simple embedding request
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input="API key test"
        )
        
        embedding = response.data[0].embedding
        print(f"✅ OpenAI API test successful: {len(embedding)} dimensions")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI API test failed: {e}")
        return False

async def main():
    """Run all API key checks"""
    print("Background Service - API Key Verification")
    print("=" * 60)
    
    key_found = await check_api_key_sources()
    
    if key_found:
        api_works = await test_api_key_with_openai()
        
        print("\n" + "=" * 60)
        if api_works:
            print("🎉 API Key Status: READY FOR PRODUCTION")
            print("   Background service will work correctly")
        else:
            print("⚠️  API Key Status: FOUND BUT NOT WORKING")
            print("   Check API key validity or OpenAI service status")
    else:
        print("\n" + "=" * 60)
        print("❌ API Key Status: NOT FOUND")
        print("   Background service will fail to start")
        print("\n💡 To fix:")
        print("   1. Set OPENAI_API_KEY environment variable, OR")
        print("   2. Store in Redis: redis-cli set config:openai_api_key 'sk-...'")

if __name__ == "__main__":
    asyncio.run(main())
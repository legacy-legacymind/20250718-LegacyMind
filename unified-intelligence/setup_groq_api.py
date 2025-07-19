#!/usr/bin/env python3
"""
Store Groq API key in Redis
"""

import asyncio
import os
import redis.asyncio as redis

async def store_groq_api_key():
    """Store Groq API key in Redis"""
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    client = redis.from_url(redis_url, decode_responses=True)
    
    groq_api_key = "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"
    
    try:
        await client.set('config:groq_api_key', groq_api_key)
        print(f"✅ Stored Groq API key in Redis ({len(groq_api_key)} characters)")
        
        # Verify storage
        stored_key = await client.get('config:groq_api_key')
        if stored_key == groq_api_key:
            print("✅ Verified: Groq API key stored correctly")
        
        await client.aclose()
        
    except Exception as e:
        print(f"❌ Failed to store API key: {e}")

if __name__ == "__main__":
    asyncio.run(store_groq_api_key())
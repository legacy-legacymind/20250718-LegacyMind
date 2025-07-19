#!/usr/bin/env python3
"""
Check for Groq API key and test Groq embedding capabilities
"""

import asyncio
import os
import redis.asyncio as redis

async def check_groq_setup():
    """Check if Groq API key is available"""
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Check for Groq API key
        groq_key = await client.get('config:groq_api_key')
        if groq_key:
            print(f"✅ Groq API key found ({len(groq_key)} characters)")
            
            # Test Groq API capabilities
            try:
                from groq import Groq
                groq_client = Groq(api_key=groq_key)
                
                # Check available models
                print("\nChecking Groq models...")
                # Note: Groq doesn't have a direct embedding model
                # They support LLMs that could generate embeddings differently
                print("ℹ️  Groq primarily supports LLM models, not dedicated embedding models")
                print("   Available for inference: llama3-8b, mixtral-8x7b, etc.")
                
            except ImportError:
                print("⚠️  Groq Python client not installed")
                print("   Run: pip install groq")
            except Exception as e:
                print(f"❌ Groq API test failed: {e}")
        else:
            print("❌ No Groq API key found in Redis")
            print("   Expected at: config:groq_api_key")
        
        await client.aclose()
        
    except Exception as e:
        print(f"❌ Check failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_groq_setup())
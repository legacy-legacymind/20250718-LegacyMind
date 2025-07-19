#!/usr/bin/env python3
"""
Test Groq API directly
"""

import os
import redis
from groq import Groq

# Get API key from Redis
redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
redis_url = f"redis://:{redis_password}@localhost:6379/0"
client = redis.from_url(redis_url)

groq_key = client.get('config:groq_api_key')
if groq_key:
    groq_key = groq_key.decode('utf-8') if isinstance(groq_key, bytes) else groq_key
    print(f"Groq API key: {groq_key[:10]}...{groq_key[-10:]}")
    
    # Test Groq API
    try:
        groq_client = Groq(api_key=groq_key)
        
        # Simple test
        response = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": "Say 'API test successful' and nothing else."}],
            temperature=0,
            max_tokens=10
        )
        
        print(f"✅ Groq API test response: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ Groq API test failed: {e}")
else:
    print("No Groq key found")

client.close()
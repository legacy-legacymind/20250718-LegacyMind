#!/usr/bin/env python3
"""
Update Groq API key in Redis with the new one
"""

import redis
import os

redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
redis_url = f"redis://:{redis_password}@localhost:6379/0"
client = redis.from_url(redis_url)

# Update with the new Groq API key
new_groq_key = "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"

# Store in Redis
client.set('config:groq_api_key', new_groq_key)
print(f"✅ Updated Groq API key in Redis ({len(new_groq_key)} characters)")

# Verify storage
stored = client.get('config:groq_api_key').decode('utf-8')
print(f"✅ Verified: {stored[:10]}...{stored[-10:]}")

# Test the new key
try:
    from groq import Groq
    groq_client = Groq(api_key=new_groq_key)
    
    # Simple test
    response = groq_client.chat.completions.create(
        model="mixtral-8x7b-32768",
        messages=[{"role": "user", "content": "Say 'API test successful' and nothing else."}],
        temperature=0,
        max_tokens=10
    )
    
    print(f"✅ Groq API test response: {response.choices[0].message.content}")
    print("🎉 New Groq API key is working!")
    
except Exception as e:
    print(f"❌ Groq API test failed: {e}")

client.close()
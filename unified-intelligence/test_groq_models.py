#!/usr/bin/env python3
"""
Test available Groq models
"""

import redis
import os
from groq import Groq

# Get API key from Redis
redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
redis_url = f"redis://:{redis_password}@localhost:6379/0"
client = redis.from_url(redis_url)

groq_key = client.get('config:groq_api_key').decode('utf-8')
groq_client = Groq(api_key=groq_key)

# Test different models
models_to_test = [
    "llama3-8b-8192",
    "llama3-70b-8192", 
    "llama2-70b-4096",
    "gemma-7b-it",
    "mixtral-8x7b",  # Without the -32768 suffix
]

print("Testing available Groq models...")
for model in models_to_test:
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'success'"}],
            temperature=0,
            max_tokens=10
        )
        print(f"✅ {model}: {response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ {model}: {str(e)[:100]}...")

client.close()
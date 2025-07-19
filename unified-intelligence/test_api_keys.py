#!/usr/bin/env python3
"""
Test API keys are being loaded correctly
"""

import os
import redis

# Get Redis connection
redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
redis_url = f"redis://:{redis_password}@localhost:6379/0"
client = redis.from_url(redis_url)

# Check OpenAI key
openai_key = client.get('config:openai_api_key')
if openai_key:
    openai_key = openai_key.decode('utf-8') if isinstance(openai_key, bytes) else openai_key
    print(f"OpenAI API key from Redis: {openai_key[:10]}...{openai_key[-10:]}")
    print(f"Length: {len(openai_key)}")
else:
    print("No OpenAI key found")

# Check Groq key
groq_key = client.get('config:groq_api_key')
if groq_key:
    groq_key = groq_key.decode('utf-8') if isinstance(groq_key, bytes) else groq_key
    print(f"\nGroq API key from Redis: {groq_key[:10]}...{groq_key[-10:]}")
    print(f"Length: {len(groq_key)}")
else:
    print("\nNo Groq key found")

client.close()
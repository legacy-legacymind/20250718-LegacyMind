#!/usr/bin/env python3
"""
Update OpenAI API key in Redis with the correct one
"""

import redis
import os

redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
redis_url = f"redis://:{redis_password}@localhost:6379/0"
client = redis.from_url(redis_url)

# Update with the correct OpenAI key from API_Keys.md
correct_key = "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"

client.set('config:openai_api_key', correct_key)
print(f"✅ Updated OpenAI API key in Redis ({len(correct_key)} characters)")

# Verify
stored = client.get('config:openai_api_key').decode('utf-8')
print(f"✅ Verified: {stored[:10]}...{stored[-10:]}")

client.close()
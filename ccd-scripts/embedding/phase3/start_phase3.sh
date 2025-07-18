#!/bin/bash
# Start Phase 3 API with proper configuration

# Set Redis password
export REDIS_PASSWORD="sammy5577"

# Get OpenAI API key from Redis using Python
export OPENAI_API_KEY=$(python3 -c "
import redis
r = redis.from_url('redis://:sammy5577@localhost:6379')
key = r.get('OPENAI_API_KEY')
print(key.decode() if key else '')
")

if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ No OpenAI API key found in Redis"
else
    echo "✅ OpenAI API key loaded from Redis"
fi

echo "🚀 Starting Phase 3 Embedding API..."
python3 ccd-scripts/embedding/phase3/phase3_embedding_api.py --port 8004
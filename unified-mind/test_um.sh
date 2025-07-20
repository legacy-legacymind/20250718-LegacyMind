#!/bin/bash

# Test UnifiedMind with proper environment
export OPENAI_API_KEY="${OPENAI_API_KEY}"
export GROQ_API_KEY="${GROQ_API_KEY}"
export REDIS_PASSWORD="${REDIS_PASSWORD}"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export QDRANT_HOST="localhost"
export QDRANT_PORT="6334"
export INSTANCE_ID="CC"
export RUST_LOG="unified_mind=debug,rmcp=info"

echo "Testing UnifiedMind MCP..."
echo "Redis: $REDIS_HOST:$REDIS_PORT"
echo "Qdrant: $QDRANT_HOST:$QDRANT_PORT"
echo "Instance: $INSTANCE_ID"

# Run the MCP server
./target/release/unified-mind
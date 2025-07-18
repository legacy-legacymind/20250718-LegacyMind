#!/bin/bash
# Start script for Batch Embedding API
# Phase 1A implementation of dual-storage embedding optimization

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Set environment variables if not already set
export REDIS_PASSWORD="${REDIS_PASSWORD:-legacymind_redis_pass}"
export INSTANCE_ID="${INSTANCE_ID:-Claude}"

# Check for OpenAI API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Warning: OPENAI_API_KEY not set. Will attempt to retrieve from Redis."
fi

echo "Starting Batch Embedding API server..."
echo "API Documentation will be available at:"
echo "  http://127.0.0.1:8000/docs"
echo "  http://127.0.0.1:8000/redoc"
echo ""
echo "Press Ctrl+C to stop the server"

# Start the API server
python3 batch_embedding_api.py --host 127.0.0.1 --port 8000 --reload
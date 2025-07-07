#!/bin/bash
# Deploy UnifiedIntelligence v3 MCP

set -e

echo "🚀 Deploying UnifiedIntelligence v3 MCP..."

# Navigate to Docker directory
cd /Users/samuelatagana/Projects/LegacyMind/Docker

# Build the container
echo "📦 Building container..."
docker-compose build unified-intelligence-mcp

# Start the container
echo "🏃 Starting container..."
docker-compose up -d unified-intelligence-mcp

# Wait for container to be ready
echo "⏳ Waiting for container to be ready..."
sleep 5

# Check container status
echo "✅ Checking container status..."
docker ps --filter name=unified-intelligence-mcp --format "table {{.Names}}\t{{.Status}}"

# Test MCP functionality
echo "🧪 Testing MCP functionality..."
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | docker exec -i unified-intelligence-mcp node src/index.js | jq -r '.result.tools[].name' 2>/dev/null || echo "⚠️  MCP test failed - check logs"

# Show logs
echo "📋 Container logs (last 20 lines):"
docker logs unified-intelligence-mcp --tail=20

echo "✨ Deployment complete!"
echo ""
echo "To monitor logs: docker logs -f unified-intelligence-mcp"
echo "To test tools: echo '{\"jsonrpc\":\"2.0\",\"method\":\"tools/list\",\"id\":1}' | docker exec -i unified-intelligence-mcp node src/index.js"
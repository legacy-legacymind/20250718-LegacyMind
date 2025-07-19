#!/bin/bash

# Setup UnifiedIntelligence for CCS on Studio
# Created: 2025-07-17

echo "Setting up UnifiedIntelligence for CCS on Studio..."

# Step 1: Copy the MCP binary from Mini to Studio
echo "1. Copying UnifiedIntelligence binary from Mini..."
scp mini.local:/Users/samuelatagana/Projects/LegacyMind/unified-intelligence/target/release/unified-intelligence ~/Projects/LegacyMind/unified-intelligence/target/release/

# Step 2: Create SSH tunnel script for Redis access
echo "2. Creating SSH tunnel script..."
cat > ~/Projects/LegacyMind/scripts/ccs_redis_tunnel.sh << 'EOF'
#!/bin/bash
# SSH tunnel to Mini's Redis for CCS
echo "Creating SSH tunnel to Mini's Redis on port 6379..."
ssh -L 6379:localhost:6379 -N samuelatagana@mini.local
EOF

chmod +x ~/Projects/LegacyMind/scripts/ccs_redis_tunnel.sh

# Step 3: Create CCS-specific MCP config
echo "3. Creating CCS MCP configuration..."
cat > ~/Projects/LegacyMind/ccs_mcp_config.json << 'EOF'
{
  "unified-intelligence": {
    "command": "/Users/samuelatagana/Projects/LegacyMind/unified-intelligence/target/release/unified-intelligence",
    "env": {
      "REDIS_HOST": "127.0.0.1",
      "REDIS_PORT": "6379", 
      "REDIS_PASSWORD": "legacymind_redis_pass",
      "OPENAI_API_KEY": "${OPENAI_API_KEY}",
      "INSTANCE_ID": "CCS"
    }
  }
}
EOF

echo ""
echo "✅ Setup complete!"
echo ""
echo "To use UnifiedIntelligence with CCS:"
echo "1. On Studio, start the Redis tunnel in a terminal:"
echo "   ~/Projects/LegacyMind/scripts/ccs_redis_tunnel.sh"
echo ""
echo "2. Add this to Studio's Claude desktop config:"
echo "   Copy the contents of ~/Projects/LegacyMind/ccs_mcp_config.json"
echo "   to your Claude desktop configuration"
echo ""
echo "3. Restart Claude Desktop on Studio to load the MCP"
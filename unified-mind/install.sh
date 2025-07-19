#!/bin/bash

# UnifiedMind MCP Installation Script
# This script builds and installs UnifiedMind as an MCP server

set -e

echo "🧠 UnifiedMind MCP Installation Script"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project directory
PROJECT_DIR="/Users/samuelatagana/Projects/LegacyMind/unified-mind"
INSTALL_DIR="/Users/samuelatagana/Projects/LegacyMind"

echo -e "${YELLOW}📁 Project directory: ${PROJECT_DIR}${NC}"

# Check if we're in the right directory
if [[ ! -d "$PROJECT_DIR" ]]; then
    echo -e "${RED}❌ Error: Project directory not found: ${PROJECT_DIR}${NC}"
    exit 1
fi

cd "$PROJECT_DIR"

# Check if Cargo.toml exists
if [[ ! -f "Cargo.toml" ]]; then
    echo -e "${RED}❌ Error: Cargo.toml not found in ${PROJECT_DIR}${NC}"
    exit 1
fi

echo -e "${YELLOW}🔧 Building UnifiedMind MCP...${NC}"

# Build the project
cargo build --release

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✅ Build successful!${NC}"
else
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi

# Create wrapper script
echo -e "${YELLOW}📝 Creating wrapper script...${NC}"

cat > "${INSTALL_DIR}/unified_mind_wrapper.py" << 'EOF'
#!/usr/bin/env python3
"""
UnifiedMind MCP Wrapper Script
Similar to redis_mcp_wrapper.py pattern
"""

import os
import sys
import subprocess
import signal
import time

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

def main():
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Project directory
    project_dir = "/Users/samuelatagana/Projects/LegacyMind/unified-mind"
    binary_path = os.path.join(project_dir, "target", "release", "unified-mind")
    
    # Check if binary exists
    if not os.path.exists(binary_path):
        print(f"Error: UnifiedMind binary not found at {binary_path}")
        print("Please run 'cargo build --release' first")
        sys.exit(1)
    
    # Change to project directory
    os.chdir(project_dir)
    
    # Environment variables for Redis connection
    env = os.environ.copy()
    env.update({
        'REDIS_HOST': env.get('REDIS_HOST', '127.0.0.1'),
        'REDIS_PORT': env.get('REDIS_PORT', '6379'),
        'REDIS_PWD': env.get('REDIS_PWD', ''),
        'UNIFIED_MIND_INSTANCE': env.get('UNIFIED_MIND_INSTANCE', 'CC'),
        'UNIFIED_MIND_LOG_LEVEL': env.get('UNIFIED_MIND_LOG_LEVEL', 'info'),
    })
    
    try:
        # Run the UnifiedMind MCP server
        print("🧠 Starting UnifiedMind MCP server...")
        result = subprocess.run([binary_path], env=env, cwd=project_dir)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n🛑 UnifiedMind MCP server interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error running UnifiedMind MCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

# Make wrapper executable
chmod +x "${INSTALL_DIR}/unified_mind_wrapper.py"

echo -e "${GREEN}✅ Wrapper script created at ${INSTALL_DIR}/unified_mind_wrapper.py${NC}"

# Test the MCP server
echo -e "${YELLOW}🧪 Testing UnifiedMind MCP server...${NC}"

# Start the server in background for testing
export REDIS_HOST="127.0.0.1"
export REDIS_PORT="6379"
export REDIS_PWD="legacymind_redis_pass"
export UNIFIED_MIND_INSTANCE="CC"

"${INSTALL_DIR}/unified_mind_wrapper.py" &
SERVER_PID=$!

# Give it 10 seconds max to start
TIMEOUT=10
ELAPSED=0

# Wait a moment for server to start
sleep 2

# Check if server is running within timeout
while [ $ELAPSED -lt $TIMEOUT ]; do
    if ps -p $SERVER_PID > /dev/null 2>&1; then
        echo -e "${GREEN}✅ UnifiedMind MCP server started successfully!${NC}"
        # Stop the test server
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
        break
    fi
    sleep 1
    ELAPSED=$((ELAPSED + 1))
done

if [ $ELAPSED -eq $TIMEOUT ]; then
    echo -e "${RED}❌ UnifiedMind MCP server failed to start within ${TIMEOUT} seconds${NC}"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi

echo -e "${GREEN}✅ Installation complete!${NC}"
echo ""
echo "🔧 Configuration Instructions:"
echo "=============================="
echo ""
echo "Add the following to your Claude desktop config:"
echo "File: /Users/samuelatagana/Library/Application Support/Claude/claude_desktop_config.json"
echo ""
echo '"unified-mind": {'
echo '  "command": "/Users/samuelatagana/Projects/LegacyMind/unified_mind_wrapper.py",'
echo '  "env": {'
echo '    "REDIS_HOST": "127.0.0.1",'
echo '    "REDIS_PORT": "6379",'
echo '    "REDIS_PWD": "legacymind_redis_pass",'
echo '    "UNIFIED_MIND_INSTANCE": "CC"'
echo '  }'
echo '}'
echo ""
echo "🚀 Available UnifiedMind MCP Tools:"
echo "- mind_monitor_status: Get monitoring status and metrics"
echo "- mind_cognitive_metrics: Get cognitive pattern metrics"
echo "- mind_intervention_queue: Get pending interventions"
echo "- mind_conversation_insights: Get conversation insights"
echo "- mind_entity_tracking: Get detected entities"
echo "- ui_think: Store and process thoughts"
echo "- ui_recall: Search and retrieve thoughts"
echo "- ui_identity: Manage identity information"
echo ""
echo "💡 Usage: Restart Claude Desktop after adding the configuration"
echo ""
echo -e "${GREEN}🎉 UnifiedMind MCP is ready to enhance your cognitive abilities!${NC}"
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

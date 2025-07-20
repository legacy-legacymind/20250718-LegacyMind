#!/usr/bin/env python3
"""Test script for UnifiedMind MCP server"""

import asyncio
import json
from mcp import StdioServerSession, ClientSession

async def test_unified_mind():
    print("Testing UnifiedMind MCP server...")
    
    # Start the server process
    server = await StdioServerSession.start(
        "./target/release/unified-mind",
        env={
            "RUST_LOG": "unified_mind=debug,rmcp=debug",
            "INSTANCE_ID": "CC",
            "REDIS_HOST": "localhost",
            "REDIS_PORT": "6379",
            "QDRANT_HOST": "localhost",
            "QDRANT_PORT": "6334",
        }
    )
    
    # Create a client to interact with it
    async with ClientSession(server) as client:
        # Initialize the connection
        info = await client.initialize()
        print(f"Server info: {info}")
        
        # Test um_recall
        print("\nTesting um_recall with text search...")
        result = await client.call_tool(
            "um_recall",
            {
                "query": "redis",
                "limit": 5,
                "threshold": 0.7,
                "search_all_instances": False
            }
        )
        
        print(f"\nResults: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_unified_mind())
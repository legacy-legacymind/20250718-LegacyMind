#!/usr/bin/env python3
import sys
import os
sys.path.append('/Users/samuelatagana/Projects/LegacyMind/unified-intelligence-dev')

import asyncio
import json
from test_scripts.test_mcp import MCPTestClient

async def test_ui_identity():
    """Test the ui_identity tool with view operation"""
    print("Testing ui_identity tool...")
    
    # Initialize client
    transport = "stdio"
    server_path = "/Users/samuelatagana/Projects/LegacyMind/unified-intelligence-dev/unified-intelligence/target/debug/unified-intelligence"
    
    print(f"Connecting to server at {server_path}...")
    
    async with MCPTestClient(server_path, transport) as client:
        # Test view operation
        print("\nTesting ui_identity view operation...")
        try:
            result = await client.call_tool(
                "ui_identity",
                {
                    "operation": "view"
                }
            )
            print(f"Success: {json.dumps(result, indent=2)[:500]}...")
        except Exception as e:
            print(f"Error: {type(e).__name__}: {str(e)}")
            # Try to get more details about the error
            if hasattr(e, 'response'):
                print(f"Response: {e.response}")
            if hasattr(e, 'args'):
                print(f"Args: {e.args}")

if __name__ == "__main__":
    asyncio.run(test_ui_identity())
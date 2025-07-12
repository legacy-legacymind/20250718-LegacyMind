#!/usr/bin/env python3
"""Test the Lua script functionality"""

import asyncio
import json
import sys
from rmcp import Client
import uuid

async def test_lua_scripts():
    """Test atomic operations with Lua scripts"""
    try:
        client = Client("unified-think")
        
        # First, let's think a thought
        chain_id = f"test-chain-{uuid.uuid4()}"
        thought_content = f"Testing Lua script atomicity at {uuid.uuid4()}"
        
        print(f"Storing thought with chain_id: {chain_id}")
        
        # Store a thought
        response = await client.call_tool(
            "ui_think",
            {
                "thought": thought_content,
                "thought_number": 1,
                "total_thoughts": 3,
                "next_thought_needed": True,
                "chain_id": chain_id
            }
        )
        
        print(f"Think response: {json.dumps(response.result, indent=2)}")
        
        # Try to store the same thought again (should be detected as duplicate)
        print("\nTrying to store the same thought again...")
        response2 = await client.call_tool(
            "ui_think",
            {
                "thought": thought_content,
                "thought_number": 2,
                "total_thoughts": 3,
                "next_thought_needed": True,
                "chain_id": chain_id
            }
        )
        
        print(f"Second think response: {json.dumps(response2.result, indent=2)}")
        
        # Store a different thought in the same chain
        print("\nStoring a different thought in the same chain...")
        response3 = await client.call_tool(
            "ui_think",
            {
                "thought": f"Different thought in chain at {uuid.uuid4()}",
                "thought_number": 2,
                "total_thoughts": 3,
                "next_thought_needed": False,
                "chain_id": chain_id
            }
        )
        
        print(f"Third think response: {json.dumps(response3.result, indent=2)}")
        
        # Recall the chain
        print(f"\nRecalling chain {chain_id}...")
        recall_response = await client.call_tool(
            "ui_recall",
            {
                "chain_id": chain_id,
                "action": "search"
            }
        )
        
        print(f"Recall response: {json.dumps(recall_response.result, indent=2)}")
        
        # The recall should show both thoughts in the correct order
        thoughts = recall_response.result.get("thoughts", [])
        print(f"\nFound {len(thoughts)} thoughts in chain")
        for i, thought in enumerate(thoughts):
            print(f"  {i+1}. {thought.get('thought', '')[:50]}...")
        
        # Test search by content
        print("\nSearching for 'atomicity'...")
        search_response = await client.call_tool(
            "ui_recall",
            {
                "query": "atomicity",
                "action": "search"
            }
        )
        
        print(f"Search response: {json.dumps(search_response.result, indent=2)}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_lua_scripts())
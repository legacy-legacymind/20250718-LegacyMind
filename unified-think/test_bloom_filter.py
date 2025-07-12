#!/usr/bin/env python3
"""
Test script to verify Redis bloom filter implementation
"""

import json
import asyncio
import websockets
import time

async def test_bloom_filter():
    uri = "ws://localhost:8080"
    
    # Test instance ID
    instance_id = "bloom_test_instance"
    
    print("Testing Redis bloom filter implementation...")
    
    async with websockets.connect(uri) as websocket:
        # Send initial hello message
        hello = {
            "method": "hello",
            "params": {
                "instance_id": instance_id,
                "app_version": "1.0.0"
            }
        }
        
        await websocket.send(json.dumps(hello))
        response = await websocket.recv()
        print(f"Hello response: {response}")
        
        # Test saving thoughts with duplicate detection
        print("\n1. Testing duplicate detection...")
        
        # First thought
        thought1 = {
            "method": "think",
            "params": {
                "thought": "This is a unique thought about Redis bloom filters",
                "context": ["testing", "bloom filters"]
            }
        }
        
        await websocket.send(json.dumps(thought1))
        response1 = await websocket.recv()
        print(f"First thought saved: {response1}")
        
        # Try saving the same thought again (should be detected as duplicate)
        print("\n2. Trying to save duplicate thought...")
        await websocket.send(json.dumps(thought1))
        response2 = await websocket.recv()
        print(f"Duplicate attempt: {response2}")
        
        # Save a different thought
        thought2 = {
            "method": "think",
            "params": {
                "thought": "This is a different thought about bloom filter false positive rates",
                "context": ["testing", "bloom filters", "false positives"]
            }
        }
        
        print("\n3. Saving a different thought...")
        await websocket.send(json.dumps(thought2))
        response3 = await websocket.recv()
        print(f"Different thought saved: {response3}")
        
        # Test with slight variation (should not be detected as duplicate)
        thought3 = {
            "method": "think",
            "params": {
                "thought": "This is a unique thought about Redis bloom filter",  # Slightly different
                "context": ["testing", "bloom filters"]
            }
        }
        
        print("\n4. Saving slightly different thought...")
        await websocket.send(json.dumps(thought3))
        response4 = await websocket.recv()
        print(f"Slightly different thought: {response4}")
        
        print("\nBloom filter test complete!")

if __name__ == "__main__":
    asyncio.run(test_bloom_filter())
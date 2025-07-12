#!/usr/bin/env python3
"""Test script to verify ui_recall functionality after fixing Redis type errors."""

import json
import sys
import time

# Standard JSON-RPC request structure
def create_request(method, params, id=1):
    return {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": id
    }

# Test data
TEST_INSTANCE = "Claude"
TEST_THOUGHT = f"Testing ui_recall functionality after Redis type error fix - {time.time()}"

print("=== Testing ui_recall Functionality ===\n")

# Step 1: Create a thought to search for
print("Step 1: Creating a test thought...")
think_request = create_request(
    "ui_think",
    {
        "thought": TEST_THOUGHT,
        "instance_id": TEST_INSTANCE,
        "metadata": {"test": "ui_recall_test"}
    }
)

print(json.dumps(think_request))
print()

# Step 2: Search for the thought using ui_recall
print("\nStep 2: Searching for the thought using ui_recall...")
recall_request = create_request(
    "ui_recall",
    {
        "query": "Redis type error fix",
        "instance_id": TEST_INSTANCE,
        "limit": 5
    },
    id=2
)

print(json.dumps(recall_request))
print()

# Step 3: Get all thoughts for the instance
print("\nStep 3: Getting all thoughts for instance...")
recall_all_request = create_request(
    "ui_recall",
    {
        "instance_id": TEST_INSTANCE,
        "limit": 10
    },
    id=3
)

print(json.dumps(recall_all_request))
print()

# Step 4: Test chain retrieval
print("\nStep 4: Testing chain retrieval...")
recall_chain_request = create_request(
    "ui_recall",
    {
        "chain_id": "test_chain",
        "instance_id": TEST_INSTANCE
    },
    id=4
)

print(json.dumps(recall_chain_request))
print()

print("\n=== Test commands generated ===")
print("\nTo run these tests, start the server and use:")
print("cat test_ui_recall.py | python3 | nc localhost 9999")
print("\nOr run interactively:")
print("python3 test_ui_recall.py | ./target/release/unified-think")
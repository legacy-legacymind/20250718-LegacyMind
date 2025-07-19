#!/usr/bin/env python3
"""Test semantic search via MCP protocol."""

import json
import subprocess
import sys
import os

# Get API key - it will be retrieved from Redis by the Rust service
api_key = os.getenv('OPENAI_API_KEY', 'sk-test-key')

# MCP initialization request
init_request = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "protocolVersion": "0.1.0",
        "capabilities": {},
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    },
    "id": 1
}

# MCP tool call request for semantic search
semantic_search_request = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "ui_recall",
        "arguments": {
            "query": "chain of thought",
            "semantic_search": True,
            "threshold": 0.4,  # Lower threshold
            "limit": 5
        }
    },
    "id": 2
}

# Text search request for comparison
text_search_request = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "ui_recall",
        "arguments": {
            "query": "chain",
            "semantic_search": False,
            "limit": 5
        }
    },
    "id": 3
}

print("Testing semantic search via MCP...")
print(f"Using API key: {api_key[:20]}...{api_key[-10:] if len(api_key) > 30 else ''}")

# Run with unified-intelligence
proc = subprocess.Popen(
    ["./target/release/unified-intelligence"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env={
        "REDIS_PASSWORD": "legacymind_redis_pass",
        "INSTANCE_ID": "Claude",
        "OPENAI_API_KEY": api_key,
        "PATH": "/usr/bin:/bin",
        "RUST_LOG": "info"
    },
    text=True
)

# Send initialization
proc.stdin.write(json.dumps(init_request) + "\n")
proc.stdin.flush()

# Read initialization response
init_response = proc.stdout.readline()
print("\n--- INIT RESPONSE ---")
print(init_response)

# Send initialized notification
initialized_notif = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized"
}
proc.stdin.write(json.dumps(initialized_notif) + "\n")
proc.stdin.flush()

# Test semantic search
print("\n--- TESTING SEMANTIC SEARCH ---")
proc.stdin.write(json.dumps(semantic_search_request) + "\n")
proc.stdin.flush()
semantic_response = proc.stdout.readline()
print("Semantic Search Response:", semantic_response)

# Parse and display semantic search results
if semantic_response:
    try:
        response = json.loads(semantic_response)
        if 'result' in response and 'content' in response['result']:
            content = json.loads(response['result']['content'][0]['text'])
            print(f"\nSemantic Search Results: Found {content.get('total_found', 0)} thoughts")
            print(f"Search Method: {content.get('search_method', 'unknown')}")
            if content.get('thoughts'):
                for thought in content['thoughts'][:3]:
                    print(f"\n- ID: {thought['id']}")
                    print(f"  Content: {thought['content'][:100]}...")
                    print(f"  Similarity: {thought.get('similarity', 'N/A')}")
    except Exception as e:
        print(f"Error parsing semantic response: {e}")

# Test text search for comparison
print("\n--- TESTING TEXT SEARCH ---")
proc.stdin.write(json.dumps(text_search_request) + "\n")
proc.stdin.flush()
text_response = proc.stdout.readline()
print("Text Search Response:", text_response)

# Parse and display text search results
if text_response:
    try:
        response = json.loads(text_response)
        if 'result' in response and 'content' in response['result']:
            content = json.loads(response['result']['content'][0]['text'])
            print(f"\nText Search Results: Found {content.get('total_found', 0)} thoughts")
            print(f"Search Method: {content.get('search_method', 'unknown')}")
    except Exception as e:
        print(f"Error parsing text response: {e}")

# Close stdin and wait for process to finish
proc.stdin.close()
proc.wait()

# Print stderr if any
stderr = proc.stderr.read()
if stderr:
    print("\n--- STDERR ---")
    print(stderr)
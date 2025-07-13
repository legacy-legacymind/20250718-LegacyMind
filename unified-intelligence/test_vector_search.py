#!/usr/bin/env python3
"""
Test script for Vector Set semantic search functionality
"""

import json
import sys
import uuid

# Test thoughts with similar meanings
test_thoughts = [
    # Related thoughts about machine learning
    "Machine learning algorithms can identify patterns in large datasets",
    "AI and machine learning help computers learn from data patterns",
    "Deep learning is a subset of machine learning that uses neural networks",
    
    # Related thoughts about Redis
    "Redis is an in-memory data structure store used as a database",
    "Redis provides fast data access due to its in-memory architecture",
    "Caching with Redis improves application performance significantly",
    
    # Unrelated thoughts
    "The weather today is sunny and warm",
    "I had pizza for lunch yesterday",
    "Cats are independent animals that make great pets",
]

def create_thought_request(thought, thought_number, total_thoughts=len(test_thoughts)):
    """Create a ui_think request"""
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "ui_think",
        "params": {
            "thought": thought,
            "thought_number": thought_number,
            "total_thoughts": total_thoughts
        }
    }

def create_search_request(query, semantic_search=False, limit=5):
    """Create a ui_recall request"""
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "ui_recall",
        "params": {
            "query": query,
            "limit": limit,
            "semantic_search": semantic_search
        }
    }

def print_request(request):
    """Print a request to stdout"""
    print(json.dumps(request))
    print()  # Empty line to separate requests

def main():
    print("# Testing Vector Set Semantic Search", file=sys.stderr)
    print("# First, adding test thoughts...", file=sys.stderr)
    
    # Add all test thoughts
    for i, thought in enumerate(test_thoughts, 1):
        print(f"# Adding thought {i}: {thought[:50]}...", file=sys.stderr)
        print_request(create_thought_request(thought, i))
    
    # Test searches
    test_queries = [
        ("machine learning patterns", "Should find ML-related thoughts"),
        ("Redis memory database", "Should find Redis-related thoughts"),
        ("weather pizza cats", "Should find unrelated thoughts"),
    ]
    
    print("\n# Testing text search vs semantic search", file=sys.stderr)
    
    for query, description in test_queries:
        print(f"\n# Query: '{query}' - {description}", file=sys.stderr)
        
        # Text search
        print("# Text search:", file=sys.stderr)
        print_request(create_search_request(query, semantic_search=False))
        
        # Semantic search
        print("# Semantic search:", file=sys.stderr)
        print_request(create_search_request(query, semantic_search=True))

if __name__ == "__main__":
    main()
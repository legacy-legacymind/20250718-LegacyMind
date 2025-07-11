#!/usr/bin/env python3
"""
Enhanced test script for ui_recall functionality.
Tests all recall actions: search, analyze, merge, branch, continue
"""

import json
import sys
import time
from datetime import datetime

def send_request(request):
    """Send request and return response."""
    print(json.dumps(request), flush=True)
    response = input()
    return json.loads(response)

def test_ui_think(content, tags=None, chain_id=None):
    """Store a thought using ui_think."""
    request = {
        "method": "ui_think",
        "params": {
            "content": content
        }
    }
    
    if tags:
        request["params"]["tags"] = tags
    if chain_id:
        request["params"]["chain_id"] = chain_id
        
    return send_request(request)

def test_ui_recall(action, params=None):
    """Test ui_recall with specified action."""
    request = {
        "method": "ui_recall",
        "params": {
            "action": action
        }
    }
    
    if params:
        request["params"].update(params)
        
    return send_request(request)

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  {title}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

def print_result(action, response):
    """Print formatted result."""
    print(f"\n[{action.upper()}] Result:", file=sys.stderr)
    
    if response.get("result", {}).get("success"):
        result = response["result"]
        
        # Handle different response structures
        if "thoughts" in result:
            print(f"Found {len(result['thoughts'])} thoughts:", file=sys.stderr)
            for thought in result['thoughts']:
                print(f"\n  ID: {thought['id']}", file=sys.stderr)
                print(f"  Content: {thought['content'][:100]}...", file=sys.stderr)
                print(f"  Tags: {thought.get('tags', [])}", file=sys.stderr)
                print(f"  Chain: {thought.get('chain_id', 'none')}", file=sys.stderr)
                
        elif "analysis" in result:
            print(f"Analysis:", file=sys.stderr)
            analysis = result["analysis"]
            print(f"  Key themes: {analysis.get('key_themes', [])}", file=sys.stderr)
            print(f"  Summary: {analysis.get('summary', 'N/A')[:200]}...", file=sys.stderr)
            
        elif "merged_thought" in result:
            merged = result["merged_thought"]
            print(f"Merged thought created:", file=sys.stderr)
            print(f"  ID: {merged['id']}", file=sys.stderr)
            print(f"  Content: {merged['content'][:200]}...", file=sys.stderr)
            
        elif "new_chain" in result:
            new_chain = result["new_chain"]
            print(f"New branch created:", file=sys.stderr)
            print(f"  Chain ID: {new_chain['id']}", file=sys.stderr)
            print(f"  Initial thought: {new_chain['initial_thought'][:100]}...", file=sys.stderr)
            
        elif "thought" in result:
            thought = result["thought"]
            print(f"Continued chain:", file=sys.stderr)
            print(f"  ID: {thought['id']}", file=sys.stderr)
            print(f"  Content: {thought['content'][:200]}...", file=sys.stderr)
            
        print(f"  Message: {result.get('message', 'Success')}", file=sys.stderr)
    else:
        print(f"  Error: {response.get('error', 'Unknown error')}", file=sys.stderr)

def main():
    print_section("UNIFIED THINK - ENHANCED RECALL TEST")
    
    # Store test thoughts with different chains
    print_section("1. STORING TEST THOUGHTS")
    
    # Chain 1: Architecture thoughts
    chain1_thoughts = [
        "Designing a microservices architecture with Redis for state management",
        "Each service should have its own bounded context and data ownership",
        "Consider using event sourcing for inter-service communication"
    ]
    
    chain1_id = None
    for i, content in enumerate(chain1_thoughts):
        print(f"\nStoring architecture thought {i+1}...", file=sys.stderr)
        response = test_ui_think(
            content, 
            tags=["architecture", "microservices", "redis"],
            chain_id=chain1_id
        )
        if i == 0 and response.get("result", {}).get("success"):
            chain1_id = response["result"]["thought"]["chain_id"]
        time.sleep(0.1)
    
    # Chain 2: Performance optimization thoughts
    chain2_thoughts = [
        "Optimizing database queries by implementing connection pooling",
        "Add caching layer with TTL-based expiration strategy",
        "Profile application to identify bottlenecks in request processing"
    ]
    
    chain2_id = None
    for i, content in enumerate(chain2_thoughts):
        print(f"\nStoring performance thought {i+1}...", file=sys.stderr)
        response = test_ui_think(
            content,
            tags=["performance", "optimization", "database"],
            chain_id=chain2_id
        )
        if i == 0 and response.get("result", {}).get("success"):
            chain2_id = response["result"]["thought"]["chain_id"]
        time.sleep(0.1)
    
    # Standalone thoughts
    standalone_thoughts = [
        "Research Rust async patterns for concurrent processing",
        "Implement comprehensive error handling with custom error types",
        "Document API endpoints using OpenAPI specification"
    ]
    
    for i, content in enumerate(standalone_thoughts):
        print(f"\nStoring standalone thought {i+1}...", file=sys.stderr)
        test_ui_think(content, tags=["development", "best-practices"])
        time.sleep(0.1)
    
    # Test search action
    print_section("2. TESTING SEARCH ACTION")
    
    # Search by query
    print("\nSearching for 'architecture'...", file=sys.stderr)
    response = test_ui_recall("search", {"query": "architecture"})
    print_result("search", response)
    
    # Search by tags
    print("\nSearching by tags ['performance']...", file=sys.stderr)
    response = test_ui_recall("search", {"tags": ["performance"]})
    print_result("search", response)
    
    # Search by chain
    if chain1_id:
        print(f"\nSearching by chain_id '{chain1_id}'...", file=sys.stderr)
        response = test_ui_recall("search", {"chain_id": chain1_id})
        print_result("search", response)
    
    # Test analyze action
    print_section("3. TESTING ANALYZE ACTION")
    
    # Analyze all thoughts
    print("\nAnalyzing all thoughts...", file=sys.stderr)
    response = test_ui_recall("analyze")
    print_result("analyze", response)
    
    # Analyze by tags
    print("\nAnalyzing thoughts with tag 'optimization'...", file=sys.stderr)
    response = test_ui_recall("analyze", {"tags": ["optimization"]})
    print_result("analyze", response)
    
    # Test merge action
    print_section("4. TESTING MERGE ACTION")
    
    # First, get some thought IDs to merge
    search_response = test_ui_recall("search", {"tags": ["architecture"]})
    if search_response.get("result", {}).get("thoughts"):
        thought_ids = [t["id"] for t in search_response["result"]["thoughts"][:2]]
        
        if len(thought_ids) >= 2:
            print(f"\nMerging thoughts {thought_ids}...", file=sys.stderr)
            response = test_ui_recall("merge", {
                "thought_ids": thought_ids,
                "merge_strategy": "synthesis"
            })
            print_result("merge", response)
    
    # Test branch action
    print_section("5. TESTING BRANCH ACTION")
    
    if chain1_id:
        print(f"\nBranching from chain '{chain1_id}'...", file=sys.stderr)
        response = test_ui_recall("branch", {
            "from_chain": chain1_id,
            "initial_thought": "Exploring alternative architecture: serverless approach"
        })
        print_result("branch", response)
    
    # Test continue action
    print_section("6. TESTING CONTINUE ACTION")
    
    if chain2_id:
        print(f"\nContinuing chain '{chain2_id}'...", file=sys.stderr)
        response = test_ui_recall("continue", {
            "chain_id": chain2_id,
            "content": "Implement distributed tracing for performance monitoring"
        })
        print_result("continue", response)
    
    # Test error cases
    print_section("7. TESTING ERROR CASES")
    
    # Invalid action
    print("\nTesting invalid action...", file=sys.stderr)
    response = test_ui_recall("invalid_action")
    print_result("invalid_action", response)
    
    # Missing required parameters
    print("\nTesting merge without thought_ids...", file=sys.stderr)
    response = test_ui_recall("merge")
    print_result("merge_error", response)
    
    # Non-existent chain
    print("\nTesting continue with non-existent chain...", file=sys.stderr)
    response = test_ui_recall("continue", {
        "chain_id": "non-existent-chain",
        "content": "This should fail"
    })
    print_result("continue_error", response)
    
    print_section("TEST COMPLETE")
    print("\nAll ui_recall actions have been tested!", file=sys.stderr)

if __name__ == "__main__":
    main()
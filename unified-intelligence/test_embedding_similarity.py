#!/usr/bin/env python3
"""
Test OpenAI embedding similarity for debugging low similarity scores
"""

import os
import numpy as np
from openai import OpenAI

def test_embeddings():
    # Get API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY not set")
        return
    
    client = OpenAI(api_key=api_key)
    
    # Test pairs that should have high similarity
    test_pairs = [
        ("Redis performance", "Redis optimization"),
        ("database performance", "database optimization"),
        ("cache performance", "cache optimization"),
        ("Redis", "Redis"),  # Same text should give 1.0
    ]
    
    print("Testing OpenAI text-embedding-3-small embeddings...")
    print("=" * 60)
    
    for text1, text2 in test_pairs:
        # Generate embeddings
        response1 = client.embeddings.create(
            model="text-embedding-3-small",
            input=text1
        )
        embedding1 = np.array(response1.data[0].embedding)
        
        response2 = client.embeddings.create(
            model="text-embedding-3-small",
            input=text2
        )
        embedding2 = np.array(response2.data[0].embedding)
        
        # Check if embeddings are normalized
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        # Calculate cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        cosine_sim = dot_product / (norm1 * norm2)
        
        # Also try direct dot product (if already normalized)
        direct_dot = np.dot(embedding1, embedding2)
        
        print(f"\nText 1: '{text1}'")
        print(f"Text 2: '{text2}'")
        print(f"Embedding 1 norm: {norm1:.6f}")
        print(f"Embedding 2 norm: {norm2:.6f}")
        print(f"Cosine similarity: {cosine_sim:.6f}")
        print(f"Direct dot product: {direct_dot:.6f}")
        print(f"Dimension: {len(embedding1)}")
        
        # Check a few embedding values
        print(f"First 5 values of embedding 1: {embedding1[:5]}")
        print(f"First 5 values of embedding 2: {embedding2[:5]}")

if __name__ == "__main__":
    test_embeddings()
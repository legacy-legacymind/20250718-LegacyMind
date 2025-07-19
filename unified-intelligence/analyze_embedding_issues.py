#!/usr/bin/env python3
"""
Comprehensive analysis of embedding issues
"""

import os
import json
import redis
import numpy as np
from openai import OpenAI
import sys

def analyze_embedding_service():
    # Setup
    redis_password = 'legacymind_redis_pass'
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    openai_api_key = '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'
    
    redis_client = redis.from_url(redis_url)
    openai_client = OpenAI(api_key=openai_api_key)
    
    print("=== EMBEDDING SERVICE ANALYSIS ===")
    print()
    
    # 1. Check stored embeddings
    print("1. Checking stored embeddings in Redis...")
    patterns = ['*:embeddings:*', '*:embedding_index']
    for pattern in patterns:
        keys = redis_client.keys(pattern)
        print(f"   Pattern '{pattern}': {len(keys)} keys found")
        for key in keys[:5]:  # Show first 5
            print(f"     - {key.decode()}")
    
    # 2. Analyze a stored embedding
    print("\n2. Analyzing stored embedding structure...")
    sample_keys = redis_client.keys('*:embeddings:*')
    if sample_keys:
        sample_data = redis_client.get(sample_keys[0])
        if sample_data:
            data = json.loads(sample_data)
            embedding = np.array(data['embedding'])
            print(f"   Key: {sample_keys[0].decode()}")
            print(f"   Content: {data['content'][:50]}...")
            print(f"   Embedding dimension: {len(embedding)}")
            print(f"   Embedding norm: {np.linalg.norm(embedding):.6f}")
            print(f"   First 5 values: {embedding[:5]}")
    
    # 3. Test similarity calculation
    print("\n3. Testing similarity calculation...")
    test_texts = [
        ("Redis performance", "Redis optimization"),
        ("Thinking about Redis", "Considering Redis usage"),
        ("Database caching", "Cache database"),
    ]
    
    for text1, text2 in test_texts:
        # Generate fresh embeddings
        resp1 = openai_client.embeddings.create(model="text-embedding-3-small", input=text1)
        resp2 = openai_client.embeddings.create(model="text-embedding-3-small", input=text2)
        
        emb1 = np.array(resp1.data[0].embedding)
        emb2 = np.array(resp2.data[0].embedding)
        
        # Different similarity calculations
        dot_product = np.dot(emb1, emb2)
        cosine_sim = dot_product / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        
        print(f"\n   '{text1}' vs '{text2}':")
        print(f"     Dot product: {dot_product:.6f}")
        print(f"     Cosine similarity: {cosine_sim:.6f}")
        print(f"     Norms: {np.linalg.norm(emb1):.6f}, {np.linalg.norm(emb2):.6f}")
    
    # 4. Check for specific issues
    print("\n4. Checking for specific issues...")
    
    # Check if embeddings are being double-normalized
    print("\n   Testing double normalization:")
    test_vec = np.array([1, 2, 3, 4, 5])
    norm1 = test_vec / np.linalg.norm(test_vec)
    norm2 = norm1 / np.linalg.norm(norm1)
    print(f"     Original: {test_vec}")
    print(f"     Normalized once: {norm1}")
    print(f"     Normalized twice: {norm2}")
    print(f"     Are they equal? {np.allclose(norm1, norm2)}")
    
    # 5. Recommendations
    print("\n5. RECOMMENDATIONS:")
    print("   - OpenAI embeddings are pre-normalized (norm ≈ 1.0)")
    print("   - Use direct dot product for similarity (faster, same result)")
    print("   - Lower thresholds: 0.7 is quite high, consider 0.5 or 0.6")
    print("   - Expected similarities for related content: 0.65-0.85")
    print("   - Exact matches should give ~1.0")

if __name__ == "__main__":
    analyze_embedding_service()
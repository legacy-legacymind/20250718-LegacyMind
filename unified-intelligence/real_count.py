#!/usr/bin/env python3
"""
Get real counts from Redis
"""
import os
import redis

def get_real_counts():
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    # Count CCD thoughts specifically
    ccd_thoughts = client.keys("CCD:Thoughts:*")
    ccd_embeddings = client.keys("CCD:embeddings:*")
    
    print(f"CCD Thoughts: {len(ccd_thoughts)}")
    print(f"CCD Embeddings: {len(ccd_embeddings)}")
    
    # Count all thoughts
    all_thoughts = client.keys("*:Thoughts:*")
    all_embeddings = client.keys("*:embeddings:*")
    
    print(f"All Thoughts: {len(all_thoughts)}")
    print(f"All Embeddings: {len(all_embeddings)}")
    
    client.close()

if __name__ == "__main__":
    get_real_counts()
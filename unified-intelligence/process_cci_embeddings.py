#!/usr/bin/env python3
"""
Process missing CCI embeddings specifically
"""
import asyncio
import os
import json
import redis.asyncio as redis
from simple_embeddings import SimpleEmbeddingService

async def process_cci_embeddings():
    """Process missing CCI embeddings"""
    print("🔍 Processing CCI embeddings...")
    
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    # Get API key
    api_key = await client.get('config:openai_api_key')
    if not api_key:
        print("❌ No API key found")
        return
    
    # Create embedding service for CCI instance
    sync_redis_url = f"redis://:{redis_password}@localhost:6379/0"
    embedding_service = SimpleEmbeddingService(sync_redis_url, api_key, "CCI")
    
    try:
        # Get all CCI thought keys
        cci_thoughts = await client.keys("CCI:Thoughts:*")
        print(f"📚 Found {len(cci_thoughts)} CCI thoughts")
        
        missing = []
        for thought_key in cci_thoughts:
            thought_id = thought_key.split(":")[-1]
            embedding_key = f"CCI:embeddings:{thought_id}"
            
            exists = await client.exists(embedding_key)
            if not exists:
                missing.append(thought_id)
        
        print(f"🔥 Found {len(missing)} CCI thoughts without embeddings")
        
        processed = 0
        for thought_id in missing:
            success = await process_cci_thought(client, embedding_service, thought_id)
            if success:
                processed += 1
                if processed % 5 == 0:
                    print(f"  Processed {processed}/{len(missing)}...")
        
        print(f"✅ Processed {processed}/{len(missing)} CCI embeddings")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

async def process_cci_thought(client, embedding_service, thought_id):
    """Process a single CCI thought"""
    try:
        thought_key = f"CCI:Thoughts:{thought_id}"
        
        # Get thought data (handle both string and JSON types)
        key_type = await client.type(thought_key)
        
        if key_type == "string":
            thought_data_str = await client.get(thought_key)
            thought_data = json.loads(thought_data_str)
        elif key_type == "ReJSON-RL":
            thought_data = await client.execute_command("JSON.GET", thought_key)
            thought_data = json.loads(thought_data)
        else:
            return False
        
        content = thought_data.get('thought', '')
        if not content:
            return False
        
        # Convert timestamp
        timestamp = thought_data.get('timestamp', 0)
        if isinstance(timestamp, str):
            try:
                from datetime import datetime
                if 'T' in timestamp:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamp = int(dt.timestamp())
                else:
                    timestamp = int(float(timestamp))
            except ValueError:
                timestamp = 0
        elif timestamp is None:
            timestamp = 0
        
        # Store embedding for CCI instance
        success = embedding_service.store_thought_embedding(thought_id, content, timestamp)
        return success
        
    except Exception as e:
        print(f"❌ Error processing CCI thought {thought_id}: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(process_cci_embeddings())
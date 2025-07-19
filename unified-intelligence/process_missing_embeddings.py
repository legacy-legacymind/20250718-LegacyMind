#!/usr/bin/env python3
"""
Process all thoughts that are missing embeddings
"""
import asyncio
import os
import json
import redis.asyncio as redis
from simple_embeddings import SimpleEmbeddingService

async def process_missing_embeddings():
    """Find and process thoughts missing embeddings"""
    print("🔍 Finding thoughts without embeddings...")
    
    # Setup
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    # Get OpenAI API key
    api_key = await client.get('config:openai_api_key')
    if not api_key:
        print("❌ No OpenAI API key found")
        await client.close()
        return
    
    print(f"✅ Found API key ({len(api_key)} chars)")
    
    # Create embedding service
    sync_redis_url = f"redis://:{redis_password}@localhost:6379/0"
    embedding_service = SimpleEmbeddingService(sync_redis_url, api_key, "Claude")
    
    try:
        # Get all thought keys
        thought_keys = await client.keys("Claude:Thoughts:*")
        print(f"📚 Found {len(thought_keys)} total thoughts")
        
        missing_embeddings = []
        
        # Check which ones are missing embeddings
        for thought_key in thought_keys:
            thought_id = thought_key.split(":")[-1]
            embedding_key = f"Claude:embeddings:{thought_id}"
            
            exists = await client.exists(embedding_key)
            if not exists:
                missing_embeddings.append(thought_id)
        
        print(f"🔥 Found {len(missing_embeddings)} thoughts without embeddings")
        
        if not missing_embeddings:
            print("✅ All thoughts have embeddings!")
            return
        
        # Process missing embeddings
        processed = 0
        for thought_id in missing_embeddings:
            success = await process_thought_embedding(client, embedding_service, thought_id)
            if success:
                processed += 1
                if processed % 5 == 0:
                    print(f"  Processed {processed}/{len(missing_embeddings)}...")
        
        print(f"✅ Processed {processed}/{len(missing_embeddings)} missing embeddings")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

async def process_thought_embedding(client, embedding_service, thought_id):
    """Process embedding for a single thought"""
    try:
        # Get thought content - handle both string and JSON types
        thought_key = f"Claude:Thoughts:{thought_id}"
        
        # Check what type the key is
        key_type = await client.type(thought_key)
        
        if key_type == "string":
            thought_data_str = await client.get(thought_key)
            if not thought_data_str:
                return False
            thought_data = json.loads(thought_data_str)
        elif key_type == "ReJSON-RL":
            # Use JSON.GET for RedisJSON
            thought_data = await client.execute_command("JSON.GET", thought_key)
            if not thought_data:
                return False
            thought_data = json.loads(thought_data)
        else:
            print(f"⚠️  Unknown key type {key_type} for {thought_id}")
            return False
        
        content = thought_data.get('thought', '')
        if not content:
            return False
        
        # Generate and store embedding  
        timestamp = thought_data.get('timestamp', 0)
        
        # Convert timestamp to float if needed
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
        
        success = embedding_service.store_thought_embedding(thought_id, content, timestamp)
        return success
            
    except Exception as e:
        print(f"❌ Error processing {thought_id}: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(process_missing_embeddings())
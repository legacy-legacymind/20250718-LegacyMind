#!/usr/bin/env python3
"""
Test processing a specific recent thought
"""
import asyncio
import os
import json
import redis.asyncio as redis
from simple_embeddings import SimpleEmbeddingService

async def test_specific_thought():
    """Test processing a specific thought"""
    print("🔍 Testing specific thought processing...")
    
    redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
    redis_url = f"redis://:{redis_password}@localhost:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Get a recent thought ID
        events = await client.xrevrange("Claude:events", count=5)
        
        for message_id, fields in events:
            event_type = fields.get('event_type')
            thought_id = fields.get('thought_id')
            
            if not event_type and 'data' in fields:
                try:
                    data = json.loads(fields['data'])
                    event_type = data.get('type')
                    thought_id = data.get('thought_id')
                except:
                    continue
            
            if event_type == 'thought_created' and thought_id:
                print(f"Testing thought: {thought_id}")
                
                # Check if embedding exists
                embedding_key = f"Claude:embeddings:{thought_id}"
                exists = await client.exists(embedding_key)
                print(f"Embedding exists: {exists}")
                
                if not exists:
                    # Get thought content
                    thought_key = f"Claude:Thoughts:{thought_id}"
                    key_type = await client.type(thought_key)
                    print(f"Thought key type: {key_type}")
                    
                    if key_type == "ReJSON-RL":
                        thought_data = await client.execute_command("JSON.GET", thought_key)
                        thought_data = json.loads(thought_data)
                    else:
                        thought_data_str = await client.get(thought_key)
                        thought_data = json.loads(thought_data_str)
                    
                    content = thought_data.get('thought', '')
                    print(f"Content length: {len(content)}")
                    print(f"Content preview: {content[:100]}...")
                    
                    # Try to generate embedding
                    api_key = await client.get('config:openai_api_key')
                    sync_redis_url = f"redis://:{redis_password}@localhost:6379/0"
                    service = SimpleEmbeddingService(sync_redis_url, api_key, "Claude")
                    
                    print("Generating embedding...")
                    embedding = service.generate_embedding(content)
                    
                    if embedding:
                        print(f"✅ Successfully generated {len(embedding)}-dim embedding")
                        
                        # Check if it was stored
                        await asyncio.sleep(1)  # Brief wait
                        exists_after = await client.exists(embedding_key)
                        print(f"Embedding stored: {exists_after}")
                        
                        if exists_after:
                            stored_embedding = await client.get(embedding_key)
                            if stored_embedding:
                                stored_data = json.loads(stored_embedding)
                                print(f"Stored embedding dims: {len(stored_data.get('embedding', []))}")
                        
                    else:
                        print("❌ Failed to generate embedding")
                
                break
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_specific_thought())
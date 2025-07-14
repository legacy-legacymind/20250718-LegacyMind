#!/usr/bin/env python3
"""
Minimal embedding processor - process the backlog
"""

import asyncio
import os
import json
import time
import redis.asyncio as redis
from simple_embeddings import SimpleEmbeddingService

async def process_backlog():
    """Process the backlog of thoughts needing embeddings"""
    print("Starting minimal embedding processor...")
    
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
    
    # Process events from stream
    try:
        # Ensure consumer group exists
        try:
            await client.xgroup_create("Claude:events", "batch_processor", id="0", mkstream=True)
            print("✅ Created consumer group")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                print("✅ Consumer group exists")
            else:
                raise
        
        processed = 0
        total_processed = 0
        
        while True:
            # Read events
            events = await client.xreadgroup(
                "batch_processor",
                "batch_consumer",
                {"Claude:events": ">"},
                count=10,
                block=1000
            )
            
            if not events:
                print(f"No more events. Processed {total_processed} total.")
                break
            
            for stream_name, messages in events:
                for message_id, fields in messages:
                    success = await process_single_thought(client, embedding_service, message_id, fields)
                    if success:
                        processed += 1
                        total_processed += 1
                        await client.xack("Claude:events", "batch_processor", message_id)
                        
                        if processed % 5 == 0:
                            print(f"Processed {processed} events...")
            
            if len(events) == 0 or len(events[0][1]) == 0:
                break
        
        print(f"✅ Backlog processing complete. Total: {total_processed}")
        
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

async def process_single_thought(client, embedding_service, message_id, fields):
    """Process a single thought for embedding"""
    try:
        # Check if it's a thought event - handle both formats
        event_type = fields.get('event_type')
        thought_id = fields.get('thought_id')
        
        # Handle nested JSON format
        if not event_type and 'data' in fields:
            try:
                data = json.loads(fields['data'])
                event_type = data.get('type')
                thought_id = data.get('thought_id')
            except (json.JSONDecodeError, TypeError):
                return True  # Skip malformed JSON
        
        if event_type != 'thought_created':
            return True  # Skip non-thought events
        
        if not thought_id:
            return True  # Skip malformed events
        
        # Check if embedding already exists
        embedding_key = f"Claude:embeddings:{thought_id}"
        exists = await client.exists(embedding_key)
        if exists:
            return True  # Skip if already has embedding
        
        # Get thought content - handle both string and JSON types
        thought_key = f"Claude:Thoughts:{thought_id}"
        
        # Check what type the key is
        key_type = await client.type(thought_key)
        
        if key_type == "string":
            thought_data_str = await client.get(thought_key)
            if not thought_data_str:
                print(f"⚠️  Thought not found: {thought_id}")
                return False
            thought_data = json.loads(thought_data_str)
        elif key_type == "ReJSON-RL":
            # Use JSON.GET for RedisJSON
            thought_data = await client.execute_command("JSON.GET", thought_key)
            if not thought_data:
                print(f"⚠️  Thought not found: {thought_id}")
                return False
            thought_data = json.loads(thought_data)
        else:
            print(f"⚠️  Unknown key type {key_type} for {thought_id}")
            return False
        content = thought_data.get('thought', '')
        if not content:
            print(f"⚠️  Empty content: {thought_id}")
            return False
        
        # Parse timestamp
        timestamp_str = fields.get('timestamp', '')
        try:
            if timestamp_str:
                from datetime import datetime
                timestamp = int(datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp())
            else:
                timestamp = int(time.time())
        except ValueError:
            timestamp = int(time.time())
        
        # Generate embedding (sync call in executor)
        success = await asyncio.get_event_loop().run_in_executor(
            None,
            embedding_service.store_thought_embedding,
            thought_id,
            content,
            timestamp
        )
        
        if success:
            print(f"✅ {thought_id}")
            return True
        else:
            print(f"❌ Failed: {thought_id}")
            return False
            
    except Exception as e:
        print(f"❌ Error processing {message_id}: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(process_backlog())
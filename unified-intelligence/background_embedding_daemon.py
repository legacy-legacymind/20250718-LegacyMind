#!/usr/bin/env python3
"""
Background embedding daemon - continuously processes new thoughts
"""
import asyncio
import os
import json
import time
import signal
import sys
import redis.asyncio as redis
from simple_embeddings import SimpleEmbeddingService

class EmbeddingDaemon:
    def __init__(self):
        self.running = True
        self.client = None
        self.embedding_service = None
        
    async def initialize(self):
        """Initialize Redis client and embedding service"""
        print("🚀 Starting background embedding daemon...")
        
        # Setup Redis
        redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        redis_url = f"redis://:{redis_password}@localhost:6379/0"
        self.client = redis.from_url(redis_url, decode_responses=True)
        
        # Get API key
        api_key = await self.client.get('config:openai_api_key')
        if not api_key:
            print("❌ No OpenAI API key found")
            return False
        
        print(f"✅ API key loaded ({len(api_key)} chars)")
        
        # Create embedding service
        sync_redis_url = f"redis://:{redis_password}@localhost:6379/0"
        self.embedding_service = SimpleEmbeddingService(sync_redis_url, api_key, "Claude")
        
        # Setup consumer group
        try:
            await self.client.xgroup_create("Claude:events", "embedding_daemon", id="0", mkstream=True)
            print("✅ Created consumer group")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                print("✅ Consumer group exists")
            else:
                raise
        
        return True
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    async def process_events_loop(self):
        """Main event processing loop"""
        print("🔄 Starting event processing loop...")
        processed_count = 0
        
        while self.running:
            try:
                # Read new events
                events = await self.client.xreadgroup(
                    "embedding_daemon",
                    "daemon_consumer",
                    {"Claude:events": ">"},
                    count=5,
                    block=5000  # 5 second timeout
                )
                
                if events:
                    for stream_name, messages in events:
                        for message_id, fields in messages:
                            success = await self.process_single_thought(message_id, fields)
                            if success:
                                processed_count += 1
                                print(f"✅ Processed thought {processed_count}")
                                # Acknowledge the message
                                await self.client.xack("Claude:events", "embedding_daemon", message_id)
                else:
                    # No new events, brief pause
                    await asyncio.sleep(1)
                    
            except Exception as e:
                print(f"❌ Error in processing loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
        
        print(f"🏁 Daemon stopped. Total processed: {processed_count}")
    
    async def process_single_thought(self, message_id, fields):
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
            exists = await self.client.exists(embedding_key)
            if exists:
                return True  # Skip if already has embedding
            
            # Get thought content - handle both string and JSON types
            thought_key = f"Claude:Thoughts:{thought_id}"
            
            # Check what type the key is
            key_type = await self.client.type(thought_key)
            
            if key_type == "string":
                thought_data_str = await self.client.get(thought_key)
                if not thought_data_str:
                    return False
                thought_data = json.loads(thought_data_str)
            elif key_type == "ReJSON-RL":
                # Use JSON.GET for RedisJSON
                thought_data = await self.client.execute_command("JSON.GET", thought_key)
                if not thought_data:
                    return False
                thought_data = json.loads(thought_data)
            else:
                return False
            
            content = thought_data.get('thought', '')
            if not content:
                return False
            
            # Generate and store embedding
            timestamp = thought_data.get('timestamp', 0)
            success = self.embedding_service.store_thought_embedding(thought_id, content, timestamp)
            return success
            
        except Exception as e:
            print(f"❌ Error processing {message_id}: {e}")
            return False
    
    async def run(self):
        """Main daemon entry point"""
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Initialize
        if not await self.initialize():
            return 1
        
        try:
            # Run main loop
            await self.process_events_loop()
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            return 1
        finally:
            if self.client:
                await self.client.close()
        
        return 0

async def main():
    daemon = EmbeddingDaemon()
    exit_code = await daemon.run()
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3.11
"""
Test Feedback System Setup - Phase 1
Test script to verify consumer groups and basic functionality
"""

import asyncio
import json
import os
import sys
import time
from typing import Dict
import redis
from datetime import datetime

async def test_redis_connection():
    """Test basic Redis connection."""
    print("🔍 Testing Redis connection...")
    
    try:
        password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        redis_url = f"redis://:{password}@localhost:6379/0"
        
        client = redis.from_url(redis_url, decode_responses=True)
        await asyncio.to_thread(client.ping)
        
        print("✅ Redis connection successful")
        return client
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return None

async def test_consumer_groups(client):
    """Test consumer group creation and functionality."""
    print("\n🔍 Testing consumer group setup...")
    
    instances = ['CC', 'CCD', 'CCI']
    consumer_group = "feedback_processor"
    
    results = {}
    
    for instance in instances:
        stream_key = f"{instance}:feedback_events"
        
        try:
            # Try to create consumer group
            await asyncio.to_thread(
                client.xgroup_create,
                stream_key,
                consumer_group,
                id='0',
                mkstream=True
            )
            
            results[instance] = {
                'status': 'created',
                'message': 'Consumer group created successfully'
            }
            
        except redis.RedisError as e:
            if "BUSYGROUP" in str(e):
                results[instance] = {
                    'status': 'exists',
                    'message': 'Consumer group already exists'
                }
            else:
                results[instance] = {
                    'status': 'error',
                    'message': str(e)
                }
    
    # Print results
    for instance, result in results.items():
        status_icon = "✅" if result['status'] in ['created', 'exists'] else "❌"
        print(f"{status_icon} {instance}: {result['message']}")
    
    return results

async def test_event_publishing(client):
    """Test publishing sample events to streams."""
    print("\n🔍 Testing event publishing...")
    
    instances = ['CC', 'CCD', 'CCI']
    
    # Sample events for testing
    sample_events = [
        {
            'event_type': 'thought_created',
            'thought_id': 'test_thought_123',
            'importance': '8',
            'tags': '["test", "phase1"]',
            'timestamp': datetime.now().isoformat()
        },
        {
            'event_type': 'search_performed',
            'search_id': 'test_search_456',
            'query': 'test query',
            'results_count': '5',
            'timestamp': datetime.now().isoformat()
        },
        {
            'event_type': 'feedback_provided',
            'search_id': 'test_search_456',
            'thought_id': 'test_thought_123',
            'feedback': 'relevant',
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    published_events = {}
    
    for instance in instances:
        stream_key = f"{instance}:feedback_events"
        published_events[instance] = []
        
        print(f"   Publishing to {instance}...")
        
        for event in sample_events:
            try:
                # Add event to stream
                event_id = await asyncio.to_thread(
                    client.xadd,
                    stream_key,
                    event,
                    id='*'
                )
                
                published_events[instance].append({
                    'event_id': event_id,
                    'event_type': event['event_type'],
                    'status': 'published'
                })
                
            except Exception as e:
                published_events[instance].append({
                    'event_type': event['event_type'],
                    'status': 'error',
                    'error': str(e)
                })
    
    # Report results
    for instance, events in published_events.items():
        successful = len([e for e in events if e['status'] == 'published'])
        print(f"   {instance}: {successful}/{len(sample_events)} events published")
    
    return published_events

async def test_event_consumption(client):
    """Test consuming events from streams."""
    print("\n🔍 Testing event consumption...")
    
    instances = ['CC', 'CCD', 'CCI']
    consumer_group = "feedback_processor"
    consumer_name = f"test_consumer_{int(time.time())}"
    
    consumed_events = {}
    
    for instance in instances:
        stream_key = f"{instance}:feedback_events"
        
        try:
            # Try to read from stream
            result = await asyncio.to_thread(
                client.xreadgroup,
                consumer_group,
                consumer_name,
                {stream_key: '>'},
                count=10,
                block=1000  # 1 second timeout
            )
            
            events = []
            if result:
                for stream_name, stream_messages in result:
                    for message_id, fields in stream_messages:
                        events.append({
                            'id': message_id,
                            'event_type': fields.get('event_type'),
                            'fields': fields
                        })
                        
                        # Acknowledge the message
                        await asyncio.to_thread(
                            client.xack,
                            stream_key,
                            consumer_group,
                            message_id
                        )
            
            consumed_events[instance] = {
                'status': 'success',
                'events_consumed': len(events),
                'events': events
            }
            
            print(f"   {instance}: {len(events)} events consumed")
            
        except Exception as e:
            consumed_events[instance] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"   {instance}: Error - {e}")
    
    return consumed_events

async def test_stream_info(client):
    """Test getting stream information."""
    print("\n🔍 Testing stream information retrieval...")
    
    instances = ['CC', 'CCD', 'CCI']
    consumer_group = "feedback_processor"
    
    for instance in instances:
        stream_key = f"{instance}:feedback_events"
        
        try:
            # Get stream length
            length = await asyncio.to_thread(client.xlen, stream_key)
            
            # Get groups
            groups = await asyncio.to_thread(client.xinfo_groups, stream_key)
            
            # Get consumers
            consumers = []
            try:
                consumers = await asyncio.to_thread(
                    client.xinfo_consumers,
                    stream_key,
                    consumer_group
                )
            except redis.RedisError:
                consumers = []
            
            print(f"   {instance}:")
            print(f"     Stream length: {length}")
            print(f"     Consumer groups: {len(groups)}")
            print(f"     Active consumers: {len(consumers)}")
            
        except Exception as e:
            print(f"   {instance}: Error - {e}")

async def main():
    """Main test function."""
    print("🧪 FEEDBACK SYSTEM SETUP TEST")
    print("=" * 50)
    
    # Test Redis connection
    client = await test_redis_connection()
    if not client:
        print("❌ Cannot proceed without Redis connection")
        return 1
    
    try:
        # Test consumer groups
        group_results = await test_consumer_groups(client)
        
        # Test event publishing
        publish_results = await test_event_publishing(client)
        
        # Test event consumption
        consume_results = await test_event_consumption(client)
        
        # Test stream info
        await test_stream_info(client)
        
        print("\n🎉 FEEDBACK SYSTEM SETUP TEST COMPLETE")
        print("=" * 50)
        
        # Summary
        all_groups_ok = all(
            r['status'] in ['created', 'exists'] 
            for r in group_results.values()
        )
        
        all_publish_ok = all(
            len([e for e in events if e['status'] == 'published']) > 0
            for events in publish_results.values()
        )
        
        all_consume_ok = all(
            r['status'] == 'success' 
            for r in consume_results.values()
        )
        
        if all_groups_ok and all_publish_ok and all_consume_ok:
            print("✅ All tests passed! Feedback system is ready.")
            return 0
        else:
            print("⚠️ Some tests failed. Check the output above.")
            return 1
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return 1
        
    finally:
        client.close()

if __name__ == "__main__":
    exit(asyncio.run(main()))
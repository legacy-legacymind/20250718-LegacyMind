#!/usr/bin/env python3
"""
Check the interventions created by the monitoring system.
"""

import redis
import json
from datetime import datetime

def check_interventions():
    """Check all interventions in Redis."""
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    print("=== Checking Interventions ===\n")
    
    # Find all intervention streams
    intervention_streams = list(r.scan_iter(match="intervention:*", _type="stream"))
    
    for stream in intervention_streams:
        print(f"Stream: {stream}")
        print("-" * 50)
        
        # Get all messages from the stream
        messages = r.xrange(stream, min="-", max="+")
        
        for msg_id, data in messages:
            intervention_data = json.loads(data['data'])
            
            print(f"ID: {msg_id}")
            print(f"Intervention ID: {intervention_data.get('id', 'N/A')}")
            print(f"Type: {intervention_data.get('type', 'Unknown')}")
            print(f"Priority: {intervention_data.get('priority', 'Normal')}")
            print(f"Timestamp: {intervention_data.get('timestamp', 'Unknown')}")
            print(f"Message: {intervention_data.get('message', '')[:100]}...")
            print(f"Suggestion: {intervention_data.get('suggestion', 'None')}")
            print()
    
    # Check cognitive states
    print("\n=== Cognitive States ===")
    print("-" * 50)
    
    cognitive_keys = list(r.scan_iter(match="cognitive:*:state"))
    for key in cognitive_keys:
        print(f"\nKey: {key}")
        state_data = r.hget(key, "state")
        if state_data:
            state = json.loads(state_data)
            print(f"Last Processed: {state.get('last_processed', 'N/A')}")
            print(f"Timestamp: {state.get('timestamp', 'N/A')}")
            print(f"Messages Processed: {state.get('messages_processed', 0)}")
            print(f"Entities Detected: {state.get('entities_detected', 0)}")
            print(f"Topics Extracted: {state.get('topics_extracted', 0)}")
    
    # Check entities and topics
    print("\n=== Detected Entities ===")
    print("-" * 50)
    
    entity_keys = list(r.scan_iter(match="entities:*"))
    for key in entity_keys:
        entities = r.smembers(key)
        print(f"{key}: {', '.join(sorted(entities))}")
    
    print("\n=== Extracted Topics ===")
    print("-" * 50)
    
    topic_keys = list(r.scan_iter(match="topics:*"))
    for key in topic_keys:
        topics = r.smembers(key)
        print(f"{key}: {', '.join(sorted(topics))}")

if __name__ == "__main__":
    check_interventions()
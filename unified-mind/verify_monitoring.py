#!/usr/bin/env python3
"""
Verify that the UnifiedMind monitoring system is processing conversations.
This script checks for monitoring artifacts and system responses.
"""

import redis
import json
import time
from datetime import datetime

class MonitoringVerifier:
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0):
        """Initialize the verifier with Redis connection."""
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True
        )
    
    def check_monitoring_artifacts(self):
        """Check for artifacts created by the monitoring system."""
        print("\n=== Checking Monitoring Artifacts ===")
        
        # Check for intervention streams
        intervention_streams = list(self.redis_client.scan_iter(match="intervention:*", _type="stream"))
        print(f"\nIntervention Streams: {len(intervention_streams)}")
        for stream in intervention_streams:
            length = self.redis_client.xlen(stream)
            print(f"  {stream} - {length} entries")
            
        # Check for entity detection results
        entity_keys = list(self.redis_client.scan_iter(match="entities:*"))
        print(f"\nEntity Keys: {len(entity_keys)}")
        for key in entity_keys[:5]:  # Show first 5
            print(f"  {key}")
            
        # Check for topic analysis results  
        topic_keys = list(self.redis_client.scan_iter(match="topics:*"))
        print(f"\nTopic Keys: {len(topic_keys)}")
        for key in topic_keys[:5]:  # Show first 5
            print(f"  {key}")
            
        # Check for pattern detection
        pattern_keys = list(self.redis_client.scan_iter(match="pattern:*"))
        print(f"\nPattern Keys: {len(pattern_keys)}")
        for key in pattern_keys[:5]:
            print(f"  {key}")
            
        # Check cognitive state keys
        cognitive_keys = list(self.redis_client.scan_iter(match="cognitive:*"))
        print(f"\nCognitive State Keys: {len(cognitive_keys)}")
        for key in cognitive_keys[:5]:
            print(f"  {key}")
    
    def check_consumer_groups(self):
        """Check if consumer groups are processing the streams."""
        print("\n=== Checking Consumer Groups ===")
        
        conversation_streams = list(self.redis_client.scan_iter(match="conversation:*:*", _type="stream"))
        
        for stream in conversation_streams:
            print(f"\nStream: {stream}")
            try:
                # Check for consumer groups
                groups = self.redis_client.xinfo_groups(stream)
                if groups:
                    print(f"  Consumer Groups: {len(groups)}")
                    for group in groups:
                        print(f"    - {group['name']}: {group['pending']} pending, last-delivered: {group['last-delivered-id']}")
                else:
                    print("  No consumer groups found")
            except redis.ResponseError:
                print("  No consumer groups configured")
                
    def monitor_real_time(self, duration=10):
        """Monitor Redis in real-time for monitoring activity."""
        print(f"\n=== Monitoring Real-time Activity for {duration} seconds ===")
        
        start_time = time.time()
        initial_keys = set(self.redis_client.keys("*"))
        
        print("Watching for new keys and stream activity...")
        
        while time.time() - start_time < duration:
            current_keys = set(self.redis_client.keys("*"))
            new_keys = current_keys - initial_keys
            
            if new_keys:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] New keys detected:")
                for key in new_keys:
                    key_type = self.redis_client.type(key)
                    print(f"  {key} (type: {key_type})")
                    
            time.sleep(1)
            
        print("\nReal-time monitoring complete.")
    
    def check_unified_mind_events(self):
        """Check for UnifiedMind specific events."""
        print("\n=== Checking UnifiedMind Events ===")
        
        # Check event streams for monitoring-related events
        event_streams = ["CCI:events", "CCD:events", "CC:events"]
        
        for stream in event_streams:
            if self.redis_client.exists(stream):
                # Get last 5 events
                events = self.redis_client.xrevrange(stream, count=5)
                if events:
                    print(f"\nRecent events in {stream}:")
                    for event_id, data in events:
                        try:
                            event_data = json.loads(data.get('event', '{}'))
                            if 'monitor' in str(event_data).lower() or 'conversation' in str(event_data).lower():
                                print(f"  [{event_id}] {event_data.get('type', 'unknown')}")
                        except:
                            pass
    
    def simulate_monitoring_trigger(self):
        """Add a message to trigger monitoring if it's running."""
        print("\n=== Simulating Monitoring Trigger ===")
        
        # Add a high-priority message that should trigger monitoring
        message = {
            "id": "trigger-" + str(int(time.time())),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "instance": "CCI",
            "session": "monitor-test",
            "role": "User",
            "content": "URGENT: System performance degradation detected! Memory usage at 95%!",
            "entities": ["URGENT", "system_performance", "memory_usage"],
            "topics": ["urgent", "performance", "alert"],
            "confidence": 0.99
        }
        
        stream_key = "conversation:CCI:monitor-test"
        stream_data = {"data": json.dumps(message)}
        
        msg_id = self.redis_client.xadd(stream_key, stream_data)
        print(f"Added trigger message: {msg_id}")
        print("If monitoring is active, this should generate an intervention...")
        
        # Wait and check for response
        time.sleep(2)
        
        # Check for interventions
        intervention_pattern = "intervention:*"
        interventions = list(self.redis_client.scan_iter(match=intervention_pattern, _type="stream"))
        if interventions:
            print(f"\n✓ Found {len(interventions)} intervention streams!")
        else:
            print("\n✗ No intervention streams found - monitoring may not be active")

def main():
    """Run the monitoring verification."""
    print("=== UnifiedMind Monitoring Verification ===")
    
    verifier = MonitoringVerifier()
    
    # Check Redis connection
    try:
        verifier.redis_client.ping()
        print("✓ Redis connection successful")
    except:
        print("✗ Failed to connect to Redis")
        return
    
    # Run all checks
    verifier.check_monitoring_artifacts()
    verifier.check_consumer_groups()
    verifier.check_unified_mind_events()
    verifier.simulate_monitoring_trigger()
    
    # Optional: Monitor real-time
    print("\nWould you like to monitor real-time activity? (y/n): ", end="")
    # For automation, we'll skip this
    # verifier.monitor_real_time(duration=10)
    
    print("\n=== Verification Complete ===")
    print("\nNote: If no monitoring artifacts were found, the CognitiveMonitor")
    print("service may not be running. Check the unified-mind process.")

if __name__ == "__main__":
    main()
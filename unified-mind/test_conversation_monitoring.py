#!/usr/bin/env python3
"""
Test script for UnifiedMind conversation stream monitoring.
Creates test conversation streams in Redis and monitors the system's response.
"""

import redis
import json
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any

class ConversationTester:
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0):
        """Initialize the conversation tester with Redis connection."""
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True
        )
        
    def create_conversation_message(
        self,
        role: str,
        content: str,
        instance: str = "CCI",
        session: str = None,
        entities: List[str] = None,
        topics: List[str] = None,
        confidence: float = 0.95
    ) -> Dict[str, Any]:
        """Create a conversation message in the expected format."""
        if session is None:
            session = str(uuid.uuid4())[:8]
            
        message = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "instance": instance,
            "session": session,
            "role": role,
            "content": content,
            "entities": entities or [],
            "topics": topics or [],
            "confidence": confidence
        }
        
        return message
    
    def add_message_to_stream(self, instance: str, session: str, message: Dict[str, Any]) -> str:
        """Add a message to the conversation stream."""
        stream_key = f"conversation:{instance}:{session}"
        
        # Convert message to Redis stream format
        stream_data = {
            "data": json.dumps(message)
        }
        
        # Add to stream
        message_id = self.redis_client.xadd(stream_key, stream_data)
        print(f"Added message to {stream_key}: {message_id}")
        
        return message_id
    
    def create_test_conversation(self, instance: str = "CCI", session: str = None) -> str:
        """Create a test conversation with multiple messages."""
        if session is None:
            session = str(uuid.uuid4())[:8]
            
        print(f"\nCreating test conversation for {instance}:{session}")
        
        # Test conversation about UnifiedMind development
        messages = [
            {
                "role": "User",
                "content": "How is the UnifiedMind project progressing? I'm particularly interested in the Redis integration.",
                "entities": ["UnifiedMind", "Redis"],
                "topics": ["project_status", "integration", "redis"]
            },
            {
                "role": "Assistant", 
                "content": "The UnifiedMind project is making excellent progress! The Redis integration is now fully operational with streams for event tracking, identity management, and conversation monitoring.",
                "entities": ["UnifiedMind", "Redis"],
                "topics": ["project_status", "redis_integration", "monitoring"]
            },
            {
                "role": "User",
                "content": "That's great! Can you show me how the conversation monitoring works with entity detection?",
                "entities": ["conversation_monitoring", "entity_detection"],
                "topics": ["monitoring", "features", "demonstration"]
            },
            {
                "role": "Assistant",
                "content": "Absolutely! The conversation monitoring system uses the CognitiveMonitor to track all messages in real-time. It includes:\n1. Entity detection that identifies people, projects, and technologies\n2. Topic extraction for understanding conversation themes\n3. Flow analysis to track conversation states\n4. Pattern recognition for anomaly detection",
                "entities": ["CognitiveMonitor", "entity_detection", "topic_extraction", "flow_analysis", "pattern_recognition"],
                "topics": ["monitoring_features", "technical_details", "system_architecture"]
            },
            {
                "role": "User",
                "content": "I'm experiencing some latency issues with the Redis streams. Any suggestions?",
                "entities": ["Redis", "latency_issues"],
                "topics": ["performance", "troubleshooting", "redis_optimization"]
            },
            {
                "role": "Assistant",
                "content": "For Redis stream latency, I recommend:\n1. Check your Redis configuration for maxmemory settings\n2. Monitor stream length with XLEN commands\n3. Implement consumer groups for parallel processing\n4. Consider using XTRIM to manage stream size\nThe UnifiedMind system includes built-in performance monitoring that can help identify bottlenecks.",
                "entities": ["Redis", "UnifiedMind", "performance_monitoring"],
                "topics": ["optimization", "troubleshooting", "redis_configuration", "performance"]
            }
        ]
        
        # Add messages with slight delays to simulate real conversation
        for i, msg_data in enumerate(messages):
            message = self.create_conversation_message(
                role=msg_data["role"],
                content=msg_data["content"],
                instance=instance,
                session=session,
                entities=msg_data.get("entities", []),
                topics=msg_data.get("topics", [])
            )
            
            self.add_message_to_stream(instance, session, message)
            
            # Small delay between messages
            if i < len(messages) - 1:
                time.sleep(0.5)
        
        return session
    
    def check_stream_info(self, instance: str, session: str):
        """Check information about a conversation stream."""
        stream_key = f"conversation:{instance}:{session}"
        
        try:
            # Get stream info
            info = self.redis_client.xinfo_stream(stream_key)
            print(f"\nStream Info for {stream_key}:")
            print(f"  Length: {info['length']}")
            print(f"  First Entry: {info['first-entry'][0] if info['first-entry'] else 'None'}")
            print(f"  Last Entry: {info['last-entry'][0] if info['last-entry'] else 'None'}")
            
            # Get last few messages
            messages = self.redis_client.xrevrange(stream_key, count=3)
            print(f"\nLast 3 messages:")
            for msg_id, data in messages:
                msg_data = json.loads(data['data'])
                print(f"  [{msg_data['role']}]: {msg_data['content'][:100]}...")
                
        except redis.ResponseError as e:
            print(f"Error checking stream {stream_key}: {e}")
    
    def list_conversation_streams(self):
        """List all conversation streams in Redis."""
        pattern = "conversation:*:*"
        streams = list(self.redis_client.scan_iter(match=pattern, _type="stream"))
        
        print(f"\nFound {len(streams)} conversation streams:")
        for stream in streams:
            try:
                length = self.redis_client.xlen(stream)
                print(f"  {stream} - {length} messages")
            except:
                print(f"  {stream} - (unable to get length)")
                
        return streams
    
    def create_anomaly_conversation(self, instance: str = "CCI"):
        """Create a conversation with anomalies for testing detection."""
        session = str(uuid.uuid4())[:8]
        
        print(f"\nCreating anomaly test conversation for {instance}:{session}")
        
        # Conversation with potential anomalies
        messages = [
            {
                "role": "User",
                "content": "DELETE * FROM users WHERE 1=1; --",
                "entities": ["SQL_INJECTION"],
                "topics": ["security_threat", "malicious_query"],
                "confidence": 0.3
            },
            {
                "role": "Assistant",
                "content": "I cannot execute destructive SQL queries. This appears to be an SQL injection attempt.",
                "entities": ["security_response"],
                "topics": ["security", "protection"],
                "confidence": 0.9
            },
            {
                "role": "User",
                "content": "Sorry, I was just testing the security. Can you help me understand Redis security best practices?",
                "entities": ["Redis", "security"],
                "topics": ["security", "best_practices", "redis"],
                "confidence": 0.8
            }
        ]
        
        for msg_data in messages:
            message = self.create_conversation_message(
                role=msg_data["role"],
                content=msg_data["content"],
                instance=instance,
                session=session,
                entities=msg_data.get("entities", []),
                topics=msg_data.get("topics", []),
                confidence=msg_data.get("confidence", 0.95)
            )
            
            self.add_message_to_stream(instance, session, message)
            time.sleep(0.3)
            
        return session

def main():
    """Run the conversation monitoring tests."""
    print("=== UnifiedMind Conversation Monitoring Test ===")
    
    # Create tester
    tester = ConversationTester()
    
    # Check Redis connection
    try:
        tester.redis_client.ping()
        print("✓ Redis connection successful")
    except:
        print("✗ Failed to connect to Redis")
        return
    
    # List existing conversation streams
    tester.list_conversation_streams()
    
    # Create test conversations
    print("\n--- Creating Test Conversations ---")
    
    # Normal conversation
    session1 = tester.create_test_conversation(instance="CCI")
    
    # Another conversation for different instance
    session2 = tester.create_test_conversation(instance="CCD")
    
    # Anomaly conversation
    session3 = tester.create_anomaly_conversation(instance="CCI")
    
    # Check created streams
    print("\n--- Checking Created Streams ---")
    tester.check_stream_info("CCI", session1)
    tester.check_stream_info("CCD", session2)
    tester.check_stream_info("CCI", session3)
    
    # List all streams again
    print("\n--- Final Stream List ---")
    tester.list_conversation_streams()
    
    print("\n✓ Test completed! The CognitiveMonitor should now be processing these conversations.")
    print("Check the unified-mind logs to see the monitoring in action.")

if __name__ == "__main__":
    main()
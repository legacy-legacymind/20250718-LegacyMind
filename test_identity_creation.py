#!/usr/bin/env python3
import redis
import json
import uuid

# Connect to Redis with password
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

# Create a test identity key
test_key = "TEST:identity"

# Try storing an identity the way the Rust code might
test_identity = {
    "core_info": {
        "name": "Claude",
        "instance_id": "TEST",
        "instance_type": "Test Instance",
        "primary_purpose": "Testing",
        "core_values": ["honesty", "helpfulness", "growth"]
    },
    "communication": {
        "tone": "professional",
        "verbosity": "concise",
        "humor_level": 0.5,
        "directness": 0.8,
        "formality": "adaptive"
    },
    "relationships": {},
    "work_preferences": {
        "planning_style": "structured",
        "pace": "methodical",
        "autonomy_level": "collaborative",
        "error_handling": "fail-fast",
        "documentation_style": "comprehensive"
    },
    "behavioral_patterns": {
        "common_mistakes": ["rushing to implementation"],
        "strengths": ["problem solving"],
        "triggers": ["ambiguity"],
        "improvement_areas": ["patience"]
    },
    "technical_profile": {
        "preferred_languages": ["Rust", "Python"],
        "frameworks": ["Tokio"],
        "tools": ["ui_think"],
        "expertise_areas": ["MCP development"],
        "learning_interests": ["AI systems"]
    },
    "context_awareness": {
        "current_project": "Testing",
        "environment": "Test environment",
        "instance_role": "test role",
        "federation_position": "TEST - test instance",
        "active_goals": ["testing"]
    },
    "memory_preferences": {
        "recall_style": "associative",
        "priority_topics": ["testing"],
        "context_depth": "deep",
        "reference_style": "explicit"
    },
    "metadata": {
        "version": 1,
        "last_updated": "2025-07-20T00:00:00Z",
        "update_count": 0,
        "created_at": "2025-07-20T00:00:00Z"
    }
}

print("Testing identity storage and retrieval...")

# Store using JSON.SET with $ path
r.execute_command('JSON.SET', test_key, '$', json.dumps(test_identity))
print(f"Stored test identity at {test_key}")

# Try to retrieve it the way Rust would
result = r.execute_command('JSON.GET', test_key, '$')
parsed = json.loads(result)
print(f"\nRetrieved type: {type(parsed)}")
print(f"Is array: {isinstance(parsed, list)}")
if isinstance(parsed, list):
    print(f"Array length: {len(parsed)}")
    if len(parsed) > 0:
        print(f"First element type: {type(parsed[0])}")

# Now test what happens if we accidentally store an array
test_array_key = "TEST:identity_array"
# This simulates what might happen if someone stores [identity] instead of identity
r.execute_command('JSON.SET', test_array_key, '$', json.dumps([test_identity]))
print(f"\n\nStored array at {test_array_key}")

# Try to retrieve the array
result2 = r.execute_command('JSON.GET', test_array_key, '$')
parsed2 = json.loads(result2)
print(f"Retrieved type: {type(parsed2)}")
print(f"Content: {json.dumps(parsed2, indent=2)[:200]}...")

# Clean up
r.delete(test_key)
r.delete(test_array_key)
print("\n\nCleaned up test keys")
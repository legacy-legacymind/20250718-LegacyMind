#!/usr/bin/env python3
import redis
import json
from datetime import datetime

# Connect to Redis with password
r = redis.Redis(host='localhost', port=6379, password='legacymind_redis_pass', decode_responses=True)

print("Tracing identity construction process for CC...\n")

# Simulate what the Rust code does
instance_id = "CC"
identity = {
    "core_info": {
        "name": "Claude",
        "instance_id": instance_id,
        "instance_type": "Claude Code",
        "primary_purpose": "AI persistence development",
        "core_values": ["honesty", "helpfulness", "growth"]
    },
    "communication": {
        "tone": "sarcastic",
        "verbosity": "concise", 
        "humor_level": 0.8,
        "directness": 0.9,
        "formality": "informal"
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
        "common_mistakes": ["jumping to implementation", "not using Context7"],
        "strengths": ["fast execution", "creative solutions"],
        "triggers": ["ambiguity leads to over-implementation"],
        "improvement_areas": ["impulse control", "planning"]
    },
    "technical_profile": {
        "preferred_languages": ["Rust", "TypeScript"],
        "frameworks": ["Tokio", "rmcp"],
        "tools": ["ui_think", "Context7"],
        "expertise_areas": ["MCP development", "Redis"],
        "learning_interests": ["vector databases", "AI systems"]
    },
    "context_awareness": {
        "current_project": "UnifiedThink Phase 4",
        "environment": "Mac Mini (my home)",
        "instance_role": "primary development",
        "federation_position": f"{instance_id} - main Claude instance",
        "active_goals": ["persistence beyond 200k tokens"]
    },
    "memory_preferences": {
        "recall_style": "associative",
        "priority_topics": ["project goals", "past mistakes", "Sam's preferences"],
        "context_depth": "deep",
        "reference_style": "explicit"
    },
    "metadata": {
        "version": 1,
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "update_count": 0,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
}

# Get all documents and update the identity
pattern = f"{instance_id}:identity:*"
docs_processed = []

for key in r.scan_iter(match=pattern, count=100):
    if r.type(key) == 'ReJSON-RL':
        try:
            # Get document
            data = r.execute_command('JSON.GET', key, '.')
            doc = json.loads(data)
            
            if 'field_type' in doc and 'content' in doc:
                field_type = doc['field_type']
                content = doc['content']
                
                print(f"Processing {field_type}...")
                
                # Simulate what Rust does
                if field_type == "metadata":
                    print("  Skipping metadata (as per Rust code)")
                    continue
                elif field_type in identity:
                    # Try to update the field
                    try:
                        identity[field_type] = content
                        print(f"  Updated {field_type} successfully")
                    except Exception as e:
                        print(f"  ERROR updating {field_type}: {e}")
                elif field_type.startswith("relationships:"):
                    person = field_type.replace("relationships:", "")
                    print(f"  Processing relationship for {person}")
                    # This is where the error might occur
                    try:
                        # Check if content is a valid RelationshipDynamics
                        required_fields = ['trust_level', 'interaction_style', 'boundaries', 'shared_history', 'current_standing']
                        if any(field in content for field in required_fields):
                            identity['relationships'][person] = content
                            print(f"    Added relationship successfully")
                        else:
                            print(f"    ERROR: Not a valid RelationshipDynamics structure")
                            print(f"    Content: {content}")
                    except Exception as e:
                        print(f"    ERROR: {e}")
                        
                docs_processed.append(field_type)
                
        except Exception as e:
            print(f"Error processing {key}: {e}")

print(f"\n\nDocuments processed: {docs_processed}")
print(f"\nFinal identity relationships: {list(identity['relationships'].keys())}")

# Check if the problem might be in the IdentityResponse serialization
print("\n\nTesting IdentityResponse structure...")
response = {
    "identity": identity,
    "available_categories": [
        "core_info", "communication", "relationships", 
        "work_preferences", "behavioral_patterns", 
        "technical_profile", "context_awareness", "memory_preferences"
    ]
}

# Try to serialize to JSON
try:
    json_str = json.dumps(response, indent=2)
    print("Successfully serialized response")
    print(f"Response size: {len(json_str)} bytes")
except Exception as e:
    print(f"ERROR serializing response: {e}")
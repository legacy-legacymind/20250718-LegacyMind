#!/usr/bin/env python3
import json

# Test different response structures to find the issue

# This is what the Rust code should produce for View variant with untagged enum
view_response = {
    "identity": {
        "core_info": {"name": "Claude", "instance_id": "CC", "instance_type": "Claude Code", "primary_purpose": "AI persistence development", "core_values": ["honesty", "helpfulness", "growth"]},
        "communication": {"tone": "sarcastic", "verbosity": "concise", "humor_level": 0.8, "directness": 0.9, "formality": "informal"},
        "relationships": {},
        "work_preferences": {"planning_style": "structured", "pace": "methodical", "autonomy_level": "collaborative", "error_handling": "fail-fast", "documentation_style": "comprehensive"},
        "behavioral_patterns": {"common_mistakes": ["jumping to implementation", "not using Context7"], "strengths": ["fast execution", "creative solutions"], "triggers": ["ambiguity leads to over-implementation"], "improvement_areas": ["impulse control", "planning"]},
        "technical_profile": {"preferred_languages": ["Rust", "TypeScript"], "frameworks": ["Tokio", "rmcp"], "tools": ["ui_think", "Context7"], "expertise_areas": ["MCP development", "Redis"], "learning_interests": ["vector databases", "AI systems"]},
        "context_awareness": {"current_project": "UnifiedThink Phase 4", "environment": "Mac Mini (my home)", "instance_role": "primary development", "federation_position": "CC - main Claude instance", "active_goals": ["persistence beyond 200k tokens"]},
        "memory_preferences": {"recall_style": "associative", "priority_topics": ["project goals", "past mistakes", "Sam's preferences"], "context_depth": "deep", "reference_style": "explicit"},
        "metadata": {"version": 1, "last_updated": "2025-07-20T00:00:00Z", "update_count": 0, "created_at": "2025-07-20T00:00:00Z"}
    },
    "available_categories": ["core_info", "communication", "relationships", "work_preferences", "behavioral_patterns", "technical_profile", "context_awareness", "memory_preferences"]
}

# Test serialization
try:
    json_str = json.dumps(view_response)
    print("Serialization successful")
    print(f"Length: {len(json_str)} bytes")
    
    # Check for any field that might be problematic
    def check_field_types(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                if isinstance(value, (dict, list)):
                    check_field_types(value, new_path)
                else:
                    print(f"{new_path}: {type(value).__name__}")
        elif isinstance(obj, list):
            if len(obj) > 0:
                print(f"{path}: list[{type(obj[0]).__name__}] (length: {len(obj)})")
    
    print("\nField types:")
    check_field_types(view_response)
    
except Exception as e:
    print(f"Serialization failed: {e}")
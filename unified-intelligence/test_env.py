#!/usr/bin/env python3
import os
import json

env_vars = {
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "NOT_SET"),
    "REDIS_PASSWORD": os.getenv("REDIS_PASSWORD", "NOT_SET"),
    "INSTANCE_ID": os.getenv("INSTANCE_ID", "NOT_SET"),
    "PATH": os.getenv("PATH", "NOT_SET")[:100] + "..." if os.getenv("PATH") else "NOT_SET"
}

print(json.dumps(env_vars, indent=2))
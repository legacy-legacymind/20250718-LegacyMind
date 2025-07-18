# CCD Scripts Organization

**Author**: CCD (Database & Architecture Specialist)  
**Created**: 2025-07-17  
**Purpose**: Organized collection of all CCD-related scripts and utilities

## Directory Structure

```
ccd-scripts/
├── embedding/           # Embedding service implementations
├── debugging/          # Diagnostic and debugging utilities  
├── feedback/           # Feedback loop processing scripts
├── migration/          # Redis to Qdrant migration tools
├── monitoring/         # System monitoring and metrics
└── README.md          # This file
```

## Scripts by Category

### 📊 Embedding Services
- `embedding/simple_federation_embedding.py` - Multi-instance embedding service
- `embedding/start_federation_embedding.py` - Production startup script

### 🔍 Debugging & Diagnostics
- `debugging/check_instances.py` - Instance status and stream analysis
- `debugging/debug_async.py` - Async Redis operation testing
- `debugging/debug_embeddings.py` - Embedding generation debugging
- `debugging/check_thought_storage.py` - Thought persistence verification
- `debugging/verify_thoughts.py` - Comprehensive thought verification
- `debugging/full_redis_scan.py` - Complete Redis structure analysis

### 🔄 Feedback Processing
- `feedback/` - (Reserved for feedback loop scripts from unified-intelligence/)

### 🚀 Migration Tools
- `migration/` - (Reserved for Redis→Qdrant migration scripts)

### 📈 Monitoring
- `monitoring/` - (Reserved for system monitoring scripts)

## Usage Notes

1. **Python Dependencies**: All scripts require `redis`, `asyncio`, and related packages
2. **Redis Connection**: Scripts use `redis://:legacymind_redis_pass@localhost:6379/0`
3. **Instance Support**: Scripts handle CC, CCI, CCD, Claude, DT instances
4. **Future Migration**: These Python scripts should be converted to Rust

## Running Scripts

```bash
# From CCD worktree root
cd ccd-scripts/

# Debug instance status
python3 debugging/check_instances.py

# Start federation embedding service
python3 embedding/simple_federation_embedding.py

# Full Redis analysis
python3 debugging/full_redis_scan.py
```

## Migration Plan

These Python scripts represent the current working implementations. The plan is to:

1. ✅ Organize scripts (DONE)
2. 🔄 Convert to Rust for consistency
3. 📦 Integrate with unified-intelligence MCP server
4. 🚀 Deploy as native Rust services

## Documentation References

- `/Users/samuelatagana/LegacyMind_Vault/Claude/CCD/CCD-Expert-Documentation.md`
- `/Users/samuelatagana/LegacyMind_Vault/Claude/CCD/20250712-CCB-CCD/Redis-Qdrant-Pipeline-Research.md`
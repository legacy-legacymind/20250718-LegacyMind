# Redis Migration Guide: CCI/CCD → CCB

## Overview
This guide covers migrating Redis data from CCI and CCD instances to CCB using the automated migration script.

**Date Created**: July 19, 2025  
**Script Location**: `/Users/samuelatagana/Projects/LegacyMind/scripts/migrate_redis_cci_ccd_to_ccb.py`

## Pre-Migration Analysis Summary

### Data Discovered
- **CCI Keys**: ~400+ keys across multiple data types
- **CCD Keys**: ~100+ keys primarily thoughts and tags  
- **Total Migration Volume**: ~500+ keys
- **Database Size**: 5,359 total keys

### Key Types and Structures
1. **Thoughts** (ReJSON-RL): `{instance}:Thoughts:{uuid}`
2. **Tags** (Redis Sets): `{instance}:tags:{tag_name}`
3. **Chains** (Redis Lists): `{instance}:chains:{chain_name}`
4. **Search Sessions** (Redis Hashes): `{instance}:search_sessions:search_{timestamp}_{id}`
5. **Thought Metadata** (ReJSON-RL): `{instance}:thought_meta:{uuid}`

### Migration Strategy
- **Simple Rename**: Most keys (thoughts, chains, search_sessions, thought_meta)
- **Conflict Resolution**: Tags are merged using union operations
- **Instance Updates**: Update `instance` fields in JSON/Hash data from CCI/CCD → CCB
- **TTL Preservation**: All original TTL settings maintained (-1 for most keys)

## Usage Instructions

### 1. Dry Run (Recommended First Step)
```bash
cd /Users/samuelatagana/Projects/LegacyMind/scripts
python3 migrate_redis_cci_ccd_to_ccb.py
```

This will:
- Analyze all CCI/CCD keys  
- Show migration plan
- Identify conflicts
- Provide summary without making changes

### 2. Execute Migration with Backup
```bash
python3 migrate_redis_cci_ccd_to_ccb.py --execute --backup redis_backup_$(date +%Y%m%d_%H%M%S).json
```

### 3. Execute Migration (Auto-backup)
```bash
python3 migrate_redis_cci_ccd_to_ccb.py --execute
```
*(Auto-generates backup file with timestamp)*

## Script Features

### Safety Features
- ✅ **Dry Run Mode**: Test migration without changes
- ✅ **Automatic Backup**: Creates JSON backup of all source keys
- ✅ **Conflict Detection**: Identifies overlapping tag names
- ✅ **Smart Merging**: Union operation for conflicting tags
- ✅ **Error Handling**: Graceful failure handling per key
- ✅ **Progress Tracking**: Real-time migration status
- ✅ **Rollback Ready**: Backup format supports restoration

### Conflict Resolution
- **Tags**: CCI and CCD tags with same name are merged (union of UUIDs)
- **Thoughts**: UUID conflicts extremely unlikely
- **Other Types**: Direct migration (low conflict probability)

## Expected Results

### Before Migration
```
CCI:Thoughts:* → ~275 keys
CCI:tags:* → ~40 keys  
CCI:chains:* → ~1 key
CCI:search_sessions:* → ~2 keys
CCI:thought_meta:* → ~1 key

CCD:Thoughts:* → ~62 keys
CCD:tags:* → ~13 keys
CCD:chains:* → 0 keys
CCD:search_sessions:* → 0 keys  
CCD:thought_meta:* → 0 keys
```

### After Migration
```
CCB:Thoughts:* → ~337 keys (275 + 62)
CCB:tags:* → ~45-53 keys (40 + 13 - conflicts)
CCB:chains:* → ~1 key
CCB:search_sessions:* → ~2 keys
CCB:thought_meta:* → ~1 key
```

## Verification Steps

### 1. Check Key Counts
```bash
# Before migration
redis-cli --scan --pattern "CCI:*" | wc -l
redis-cli --scan --pattern "CCD:*" | wc -l

# After migration  
redis-cli --scan --pattern "CCB:*" | wc -l
```

### 2. Spot Check Data Integrity
```bash
# Check a thought
redis-cli JSON.GET "CCB:Thoughts:{some-uuid}"

# Check a tag
redis-cli SMEMBERS "CCB:tags:{some-tag-name}"

# Check search session
redis-cli HGETALL "CCB:search_sessions:{some-session}"
```

### 3. Verify Instance Updates
```bash
# Search sessions should show "instance": "CCB"
redis-cli HGET "CCB:search_sessions:{session-id}" instance
```

## Rollback Procedure

If migration issues occur, restore from backup:

```python
#!/usr/bin/env python3
import redis
import json

def restore_from_backup(backup_file):
    r = redis.Redis(decode_responses=True)
    
    with open(backup_file, 'r') as f:
        backup = json.load(f)
    
    for key, data in backup['keys'].items():
        # Delete any migrated keys first
        ccb_key = key.replace('CCI:', 'CCB:').replace('CCD:', 'CCB:')
        r.delete(ccb_key)
        
        # Restore original key using backup data
        restore_key(r, data)

# Use: restore_from_backup('redis_backup_20250719_213000.json')
```

## Integration with UnifiedIntelligence

After migration, update UnifiedIntelligence configuration:
1. Verify instance settings point to CCB
2. Run UI tests to ensure data accessibility  
3. Check thought retrieval and search functions
4. Validate tag operations and chain access

## Cleanup (After Verification)

⚠️ **Only after confirming successful migration and testing:**

```python
# Delete source keys (DANGEROUS - ensure backup exists!)
import redis
r = redis.Redis(decode_responses=True)

# Delete CCI keys
for key in r.scan_iter(match="CCI:*"):
    r.delete(key)
    
# Delete CCD keys  
for key in r.scan_iter(match="CCD:*"):
    r.delete(key)
```

## Troubleshooting

### Common Issues
1. **ReJSON Module**: Ensure Redis has ReJSON module loaded
2. **Memory**: Large migrations may need memory consideration
3. **Timeouts**: Network timeouts on large data sets
4. **Permissions**: Ensure Redis write permissions

### Recovery Options
1. Use backup file for rollback
2. Re-run migration (script is idempotent)
3. Manual key inspection and correction
4. Partial migration retry using filtered patterns

## Contact and Support

For issues or questions:
- Check Redis logs: `/var/log/redis/`  
- Review script output for specific error messages
- Verify Redis connection and module availability
- Consult backup files for data verification

---
**Created**: July 19, 2025  
**Author**: CCB (Claude Code Bot)  
**Purpose**: CCI/CCD to CCB Redis migration documentation
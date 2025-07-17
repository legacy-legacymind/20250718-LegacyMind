#!/bin/bash

# Redis Backup Script for UnifiedIntelligence
# Created: 2025-07-16
# Purpose: Protect MY Redis data from being wiped by other instances

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/Users/samuelatagana/LegacyMind_Vault/Redis_Backups"
REDIS_CONTAINER="legacymind-redis"
REDIS_PASSWORD="legacymind_redis_pass"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "Starting Redis backup at $(date)"

# Method 1: Export using redis-cli SAVE
echo "Creating RDB backup..."
docker exec $REDIS_CONTAINER redis-cli -a $REDIS_PASSWORD --no-auth-warning BGSAVE
sleep 2

# Copy the RDB file
docker cp $REDIS_CONTAINER:/data/dump.rdb "$BACKUP_DIR/redis_backup_${TIMESTAMP}.rdb"

# Method 2: Export all keys as Redis commands
echo "Creating command-based backup..."
docker exec $REDIS_CONTAINER redis-cli -a $REDIS_PASSWORD --no-auth-warning --rdb - > "$BACKUP_DIR/redis_full_${TIMESTAMP}.rdb"

# Method 3: JSON export of key data (for inspection)
echo "Creating JSON inspection backup..."
{
    echo "{"
    echo "  \"timestamp\": \"$(date -Iseconds)\","
    echo "  \"keyspace_info\": $(docker exec $REDIS_CONTAINER redis-cli -a $REDIS_PASSWORD --no-auth-warning INFO keyspace | grep -E "^db[0-9]:" | head -1),"
    echo "  \"total_keys\": $(docker exec $REDIS_CONTAINER redis-cli -a $REDIS_PASSWORD --no-auth-warning DBSIZE),"
    echo "  \"keys_sample\": ["
    docker exec $REDIS_CONTAINER redis-cli -a $REDIS_PASSWORD --no-auth-warning KEYS "*" | head -20 | sed 's/.*/"&"/' | paste -sd "," -
    echo "  ]"
    echo "}"
} > "$BACKUP_DIR/redis_info_${TIMESTAMP}.json"

# Cleanup old backups (keep last 10 of each type)
find "$BACKUP_DIR" -name "redis_backup_*.rdb" -type f | sort | head -n -10 | xargs rm -f 2>/dev/null
find "$BACKUP_DIR" -name "redis_full_*.rdb" -type f | sort | head -n -10 | xargs rm -f 2>/dev/null
find "$BACKUP_DIR" -name "redis_info_*.json" -type f | sort | head -n -10 | xargs rm -f 2>/dev/null

# Also copy to Obsidian Backups folder
cp "$BACKUP_DIR/redis_backup_${TIMESTAMP}.rdb" "/Users/samuelatagana/LegacyMind_Vault/Backups/"

echo "Redis backup completed: $BACKUP_DIR/redis_backup_${TIMESTAMP}.rdb"
echo "Total backups in directory: $(ls $BACKUP_DIR/*.rdb 2>/dev/null | wc -l)"
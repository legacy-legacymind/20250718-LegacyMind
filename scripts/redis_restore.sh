#!/bin/bash

# Redis Restore Script for UnifiedIntelligence
# Usage: ./redis_restore.sh [backup_file.rdb]

REDIS_CONTAINER="legacymind-redis"
BACKUP_DIR="/Users/samuelatagana/LegacyMind_Vault/Redis_Backups"

if [ $# -eq 0 ]; then
    echo "Available backups:"
    ls -lah "$BACKUP_DIR"/*.rdb 2>/dev/null | tail -10
    echo ""
    echo "Usage: $0 <backup_file.rdb>"
    echo "Example: $0 redis_backup_20250716_205008.rdb"
    exit 1
fi

BACKUP_FILE="$1"

# Check if file exists (try both absolute path and backup directory)
if [[ ! -f "$BACKUP_FILE" && -f "$BACKUP_DIR/$BACKUP_FILE" ]]; then
    BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
elif [[ ! -f "$BACKUP_FILE" ]]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring Redis from: $BACKUP_FILE"
echo "WARNING: This will overwrite current Redis data!"
read -p "Continue? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

# Create a backup of current state first
echo "Creating safety backup of current state..."
SAFETY_BACKUP="$BACKUP_DIR/pre_restore_$(date +%Y%m%d_%H%M%S).rdb"
docker exec $REDIS_CONTAINER redis-cli -a legacymind_redis_pass --no-auth-warning BGSAVE
sleep 2
docker cp $REDIS_CONTAINER:/data/dump.rdb "$SAFETY_BACKUP"

# Stop Redis, replace dump.rdb, restart
echo "Stopping Redis container..."
docker stop $REDIS_CONTAINER

echo "Copying backup file..."
docker cp "$BACKUP_FILE" $REDIS_CONTAINER:/data/dump.rdb

echo "Starting Redis container..."
docker start $REDIS_CONTAINER

echo "Waiting for Redis to start..."
sleep 5

# Verify restoration
echo "Verifying restoration..."
KEYCOUNT=$(docker exec $REDIS_CONTAINER redis-cli -a legacymind_redis_pass --no-auth-warning DBSIZE 2>/dev/null)
echo "Restored database contains $KEYCOUNT keys"

echo "Restore completed successfully!"
echo "Safety backup saved as: $SAFETY_BACKUP"
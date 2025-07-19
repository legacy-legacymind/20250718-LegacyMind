#!/bin/bash

# Redis CLI migration script for Claude -> CC keys
# Usage: ./redis_migrate_claude_keys.sh

REDIS_HOST="localhost"
REDIS_PORT="6379"
REDIS_PASSWORD="legacymind_redis_pass"

echo "Starting Redis key migration from Claude: to CC:..."

# Function to rename keys using Redis CLI
rename_keys() {
    local pattern="$1"
    echo "Processing pattern: $pattern"
    
    # Get all keys matching the pattern
    redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD --scan --pattern "$pattern" | while read key; do
        if [ -n "$key" ]; then
            # Generate new key name
            new_key="${key/Claude:/CC:}"
            
            # Rename the key
            echo "Renaming: $key -> $new_key"
            redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD RENAME "$key" "$new_key"
            
            if [ $? -eq 0 ]; then
                echo "  ✓ Success"
            else
                echo "  ✗ Failed"
            fi
        fi
    done
}

# Migrate different key types
echo ""
echo "1. Migrating Claude:Thoughts:* keys..."
rename_keys "Claude:Thoughts:*"

echo ""
echo "2. Migrating Claude:bloom:* keys..."
rename_keys "Claude:bloom:*"

echo ""
echo "3. Migrating Claude:metrics:* keys..."
rename_keys "Claude:metrics:*"

echo ""
echo "4. Migrating any other Claude:* keys..."
rename_keys "Claude:*"

echo ""
echo "Migration complete! Checking for remaining Claude keys..."
remaining=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD --scan --pattern "Claude:*" | wc -l)
echo "Remaining Claude keys: $remaining"

if [ "$remaining" -eq 0 ]; then
    echo "✓ All Claude keys successfully migrated to CC!"
else
    echo "⚠ Some Claude keys still remain. Check manually."
fi
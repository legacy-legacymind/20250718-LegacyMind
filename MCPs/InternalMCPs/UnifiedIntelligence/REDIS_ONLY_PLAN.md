# UnifiedIntelligence Redis-Only Write Plan

## Current Situation

The UnifiedIntelligence currently performs synchronous writes to three databases when capturing thoughts:
1. **PostgreSQL** - Primary storage for thoughts and sessions
2. **Qdrant** - Vector database for embeddings and similarity search
3. **Redis** - Federation checkin and thought streams (but only after PG/Qdrant writes complete)

This triple-write approach makes thought capture slow because it waits for all writes to complete before returning.

## Goal

Make thought capture instant by writing to Redis ONLY. PostgreSQL and Qdrant writes should be handled by a separate archival process later (not part of this implementation).

## Implementation Plan

### 1. Code to Remove/Modify

#### A. Remove Database Writes from `captureThought` (unified-intelligence.js)

**Current flow (lines 473-540):**
```javascript
// Step 4: Persist (Dual-write to PG and Qdrant)
const savedThought = await this.persistence.saveThought(enrichedThought);
```

**Change to:**
```javascript
// Step 4: Write to Redis ONLY
const savedThought = await this.saveThoughtToRedis(enrichedThought);
```

#### B. Remove/Stub Methods in persistence.js

**Methods to remove or make no-op:**
- `saveThought()` (lines 104-198) - Currently does PG + Qdrant writes
- `saveToPostgres()` (lines 205-230) - PostgreSQL write
- `saveToQdrant()` (lines 239-279) - Qdrant write with embeddings
- `deleteFromPostgres()` (lines 285-296) - Rollback method

**Methods that read from PG/Qdrant (need Redis alternatives):**
- `getThoughtsForSession()` (lines 378-392) - Used by pattern analyzer
- `searchSimilarThoughts()` (lines 425-491) - Vector search
- `getRecentThoughtsWithVectors()` (lines 499-525) - Recent thoughts

#### C. Disable Rollback Infrastructure

Since we're only writing to Redis, we don't need the complex rollback coordinator:
- Comment out `initializeRollbackInfrastructure()` call in persistence.js constructor
- Remove rollback logic from `saveThought()`

### 2. New Redis-Only Data Structure

#### A. Thought Storage in Redis

Use Redis native JSON for thoughts:
```javascript
// Key structure: ui:thought:{thoughtId}
{
  "id": "uuid",
  "content": "thought content",
  "mode": "convo",
  "framework": "socratic",
  "confidence": 0.85,
  "significance": 0.7,
  "tags": ["tag1", "tag2"],
  "session_id": "session-uuid",
  "instance": "CCI",
  "thought_number": 42,
  "mode_scores": { "convo": 0.8, "design": 0.2 },
  "created_at": "2025-01-04T10:30:00Z",
  "metadata": {}
}
```

#### B. Session Thoughts Index

Track thoughts per session using Redis sorted sets:
```javascript
// Key: ui:session:{sessionId}:thoughts
// Score: timestamp
// Member: thoughtId
ZADD ui:session:abc123:thoughts 1704365400000 "thought-uuid-1"
```

#### C. Instance Thought Stream

Continue using existing stream for federation:
```javascript
// Key: {instanceId}:thoughts
// Already implemented in federationCheckin()
```

### 3. New Methods to Add

#### A. In unified-intelligence.js

```javascript
async saveThoughtToRedis(thoughtData) {
  if (!this.redisManager) {
    throw new Error('Redis not available - cannot save thought');
  }
  
  const thoughtId = thoughtData.id || uuidv4();
  const thoughtKey = `ui:thought:${thoughtId}`;
  
  // Save thought as JSON
  const thoughtJson = {
    id: thoughtId,
    ...thoughtData,
    created_at: new Date().toISOString()
  };
  
  await this.redisManager.jsonSet(thoughtKey, '$', thoughtJson);
  
  // Add to session index
  const sessionKey = `ui:session:${thoughtData.session_id}:thoughts`;
  await this.redisManager.executeOperation(
    () => this.redisManager.client.zadd(sessionKey, Date.now(), thoughtId),
    'indexThought'
  );
  
  // Set TTL if needed (7 days default)
  await this.redisManager.executeOperation(
    () => this.redisManager.client.expire(thoughtKey, 7 * 24 * 60 * 60),
    'setThoughtTTL'
  );
  
  return thoughtJson;
}
```

#### B. In redis-manager.js

Add methods for thought retrieval:
```javascript
async getThought(thoughtId) {
  const thoughtKey = `ui:thought:${thoughtId}`;
  return await this.jsonGet(thoughtKey);
}

async getSessionThoughts(sessionId, limit = 10) {
  const sessionKey = `ui:session:${sessionId}:thoughts`;
  
  // Get thought IDs from sorted set (most recent first)
  const thoughtIds = await this.executeOperation(
    () => this.client.zrevrange(sessionKey, 0, limit - 1),
    'getSessionThoughtIds'
  );
  
  // Batch get thoughts
  const thoughts = [];
  for (const thoughtId of thoughtIds) {
    const thought = await this.getThought(thoughtId);
    if (thought) thoughts.push(thought);
  }
  
  return thoughts;
}
```

### 4. Session Management Changes

#### A. Modify session-manager.js

- Keep Redis-based session management as primary
- Make PostgreSQL session creation optional (try/catch)
- Use Redis JSON for all session operations

#### B. Session Structure in Redis

```javascript
// Key: ui:session:{sessionId}
{
  "id": "session-uuid",
  "instanceId": "CCI",
  "status": "active",
  "goal": "Design auth system",
  "total_thoughts": 42,
  "created_at": "2025-01-04T10:00:00Z",
  "last_active": "2025-01-04T10:30:00Z",
  "metadata": {},
  "context": {
    "identity": { "name": "CCI", "type": "Intelligence Specialist" },
    "samContext": {},
    "activeTickets": []
  }
}
```

### 5. Impact on Other Features

#### A. Pattern Analysis (pattern-analyzer.js)
- Currently reads from PostgreSQL via `getThoughtsForSession()`
- **Change:** Use `redisManager.getSessionThoughts()` instead
- Pattern detection logic remains the same

#### B. Context Injection (context-injector.js)
- May need similar thoughts for context
- **Change:** Implement simple text-based similarity in Redis (no vectors for now)
- Or disable similarity search temporarily

#### C. Search Features
- `searchSimilarThoughts()` requires embeddings and Qdrant
- **Change:** Return empty results or implement simple keyword search
- Full vector search would require archival process

#### D. Auto-capture Features
- Stream monitor and conversation analyzer already use Redis
- No changes needed - they continue to work

### 6. Configuration Changes

Add Redis-only mode flag:
```javascript
// In config or environment
REDIS_ONLY_MODE=true
THOUGHT_TTL_DAYS=7
```

### 7. Error Handling

Since Redis is now critical:
- Check Redis health before any thought capture
- Fail fast if Redis is unavailable
- Return clear error messages about Redis requirement

### 8. Future Archival Process Considerations

The Redis-only thoughts should be structured to support future archival:
- Include all necessary fields for PostgreSQL schema
- Keep metadata for embedding generation
- Use consistent IDs across all systems
- Consider Redis persistence settings (AOF/RDB)

## Implementation Steps

1. **Create backup** of current code
2. **Add Redis-only methods** to unified-intelligence.js and redis-manager.js
3. **Modify captureThought** to use Redis-only save
4. **Update pattern-analyzer** to read from Redis
5. **Stub out persistence.js methods** that do PG/Qdrant writes
6. **Test thought capture** speed improvement
7. **Update error messages** to indicate Redis-only mode
8. **Document the changes** in code comments

## Benefits

- **Instant thought capture** - No waiting for slow database writes
- **Simplified architecture** - Single write path
- **Better reliability** - No complex rollback scenarios
- **Federation-ready** - Thoughts immediately available to other instances

## Risks/Limitations

- **No vector search** until archival process implemented
- **Data persistence** depends on Redis configuration
- **Memory usage** - Redis will hold all recent thoughts
- **TTL management** - Thoughts expire after set time unless archived
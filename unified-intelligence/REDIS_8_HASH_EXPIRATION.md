# Redis 8.0 Hash Field Expiration Support

This document describes the implementation of Redis 8.0's new hash field expiration commands in unified-think.

## Overview

Redis 8.0 introduces fine-grained expiration control at the hash field level, allowing individual fields within a hash to have their own TTL (Time To Live). This is a significant enhancement over previous versions where expiration could only be set at the key level.

## Core Commands Implemented

### 1. HGETEX - Get with Expiration Control
```rust
pub async fn hgetex(&self, key: &str, field: &str, expire_option: Option<i64>) -> Result<Option<String>>
```
- Retrieves a hash field value while optionally modifying its expiration
- Options:
  - `None`: Get value without affecting expiration
  - `Some(seconds)`: Get value and set expiration to N seconds
  - `Some(0)`: Get value and persist (remove expiration)

### 2. HSETEX - Set with Expiration
```rust
pub async fn hsetex(&self, key: &str, field: &str, value: &str, seconds: i64) -> Result<bool>
```
- Atomically sets a hash field value with expiration
- Returns `true` if a new field was created, `false` if existing field was updated

### 3. HGETDEL - Get and Delete Atomically
```rust
pub async fn hgetdel(&self, key: &str, field: &str) -> Result<Option<String>>
```
- Atomically retrieves and deletes a hash field
- Useful for implementing "pop" operations on hash fields

## Convenience Wrappers

### Basic Operations
- `set_hash_field_with_ttl()` - Simple wrapper for setting fields with TTL
- `get_hash_field_extend_ttl()` - Get field and refresh TTL on access
- `get_hash_field_preserve_ttl()` - Get field without affecting TTL
- `get_hash_field_persist()` - Get field and remove expiration

### Use Case Specific Methods

#### Temporary Metadata
```rust
// Store metadata that expires after 1 hour
redis.set_temp_metadata("instance_id", "last_error", "connection timeout", 3600).await?;

// Get metadata and refresh TTL for another hour
let error = redis.get_temp_metadata("instance_id", "last_error", Some(3600)).await?;
```

#### Session Management
```rust
// Create session field with 30 minute TTL
redis.set_session_field("session_123", "user_id", "user_456", 1800).await?;

// Get session data and extend session for another 30 minutes
let user_id = redis.get_session_field("session_123", "user_id", Some(1800)).await?;

// Pop session field (get and delete atomically)
let old_value = redis.pop_session_field("session_123", "temp_token").await?;
```

#### Cache Management
```rust
// Cache computed result for 5 minutes
redis.set_cache_field("embeddings", "thought_123", "vector", "[0.1, 0.2, ...]", 300).await?;

// Get cached value without affecting TTL
let vector = redis.get_cache_field("embeddings", "thought_123", "vector").await?;
```

## Fallback Behavior

All implementations include automatic fallback for Redis versions < 8.0:
- `HGETEX` falls back to `HGET` (no expiration control)
- `HSETEX` falls back to `HSET` (no field-level TTL)
- `HGETDEL` falls back to `HGET` + `HDEL` (non-atomic)

The fallback behavior is logged at debug level and operations continue without field-level expiration support.

## Use Cases in unified-think

### 1. Temporary Thought Metadata
Store temporary metadata about thoughts that should auto-expire:
- Processing status
- Temporary flags
- Short-lived annotations

### 2. Session-like Data
Manage user sessions or temporary contexts:
- Active chain contexts
- Temporary user preferences
- Short-term state information

### 3. Cache-style Hash Fields
Implement fine-grained caching within hash structures:
- Computed embeddings with individual TTLs
- Temporary search results
- Rate limit counters per field

## Example Integration

```rust
// In service.rs or handlers.rs

// Store temporary processing status
self.redis.set_temp_metadata(
    &instance,
    "processing_status",
    "analyzing",
    300  // 5 minute TTL
).await?;

// Store session context
self.redis.set_session_field(
    &session_id,
    "active_chain",
    &chain_id,
    1800  // 30 minute session
).await?;

// Cache embedding with TTL
self.redis.set_cache_field(
    "thought_embeddings",
    &thought_id,
    "vector_384d",
    &embedding_json,
    3600  // 1 hour cache
).await?;
```

## Performance Considerations

1. **Atomic Operations**: HSETEX and HGETDEL are atomic, eliminating race conditions
2. **Memory Efficiency**: Fields expire individually, reducing memory usage
3. **Fallback Overhead**: Minimal overhead when falling back to older Redis versions
4. **TTL Precision**: Redis checks expiration with millisecond precision

## Testing

To test these features:
1. Ensure Redis 8.0+ is installed
2. Run with older Redis versions to verify fallback behavior
3. Monitor debug logs for fallback messages

## Future Enhancements

1. Add HEXPIRE/HPEXPIRE support when available
2. Implement batch operations for multiple fields
3. Add metrics for field expiration events
4. Create background job to cleanup expired fields (if needed)
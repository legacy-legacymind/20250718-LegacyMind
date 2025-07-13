# Redis 8.0 Features in unified-think

## Hash Field Expiration

Redis 8.0 introduces groundbreaking support for field-level expiration in hashes. This feature enables more granular control over data lifecycle management.

### When to Use Hash Field Expiration

#### ✅ Good Use Cases

1. **Session Management**
   - Individual session attributes with different lifetimes
   - Temporary authentication tokens within a user session
   - Rate limit counters per action

2. **Caching with Mixed TTLs**
   - Computed values with different freshness requirements
   - Partial cache invalidation
   - Progressive cache warming

3. **Temporary Metadata**
   - Processing status flags
   - Temporary locks or reservations
   - Short-lived annotations

#### ❌ When NOT to Use

1. **Permanent Data** - Use regular hash operations
2. **Uniform TTLs** - Use key-level expiration
3. **High-frequency Updates** - Consider streams or sorted sets

### Performance Characteristics

- **Memory**: ~8 bytes overhead per field with expiration
- **CPU**: O(1) for all operations
- **Atomicity**: All operations are atomic

### Integration Examples

#### Session Management Pattern
```rust
// User logs in - create session with mixed TTLs
let session_id = generate_session_id();

// Core session data - 2 hours
redis.set_session_field(&session_id, "user_id", &user_id, 7200).await?;
redis.set_session_field(&session_id, "ip_address", &ip, 7200).await?;

// Temporary CSRF token - 15 minutes
redis.set_session_field(&session_id, "csrf_token", &csrf, 900).await?;

// On each request - extend session
let user_id = redis.get_session_field(&session_id, "user_id", Some(7200)).await?;
```

#### Cache Invalidation Pattern
```rust
// Cache different aspects of a thought with different TTLs
let thought_id = "thought_123";

// Embedding - cache for 1 hour
redis.set_cache_field("thoughts", thought_id, "embedding", &embedding_json, 3600).await?;

// Summary - cache for 15 minutes (changes more frequently)
redis.set_cache_field("thoughts", thought_id, "summary", &summary, 900).await?;

// Access count - cache for 5 minutes
redis.set_cache_field("thoughts", thought_id, "access_count", &count.to_string(), 300).await?;
```

#### Distributed Locking Pattern
```rust
// Acquire lock with automatic expiration
let lock_acquired = redis.hsetex(
    "locks:processing",
    &task_id,
    &worker_id,
    30  // 30 second lock timeout
).await?;

// Process task...

// Release lock atomically
let lock_holder = redis.hgetdel("locks:processing", &task_id).await?;
if lock_holder == Some(worker_id) {
    println!("Lock successfully released");
}
```

### Monitoring and Debugging

#### Check Field TTL (Redis 8.0+)
```bash
# Check remaining TTL for a field
HTTL mykey field1

# Check expiration timestamp
HEXPIRETIME mykey field1
```

#### Monitor Expiration Events
Configure Redis keyspace notifications:
```
CONFIG SET notify-keyspace-events Ehx
```

Then subscribe to expiration events:
```
SUBSCRIBE __keyevent@0__:hexpired
```

### Migration Guide

#### From Key-Level to Field-Level Expiration

Before (multiple keys):
```rust
// Old approach - separate keys with TTL
redis.set_with_ttl("session:123:user_id", "789", 3600).await?;
redis.set_with_ttl("session:123:csrf", "abc", 900).await?;
```

After (single hash with field TTLs):
```rust
// New approach - one hash, different field TTLs
redis.set_session_field("123", "user_id", "789", 3600).await?;
redis.set_session_field("123", "csrf", "abc", 900).await?;
```

### Best Practices

1. **Design for Fallback**: Always handle Redis < 8.0 gracefully
2. **Monitor Memory**: Field expiration adds overhead
3. **Batch Operations**: Use pipelining for multiple field operations
4. **Consistent Naming**: Use clear key patterns for different TTL strategies

### Future Enhancements

- **HEXPIRE/HPEXPIRE**: Set expiration on existing fields
- **HTTL/HPTTL**: Query remaining TTL for fields
- **Bulk Operations**: Set multiple fields with same TTL
- **Expiration Callbacks**: React to field expiration events
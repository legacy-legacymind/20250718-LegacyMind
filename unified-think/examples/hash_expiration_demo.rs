use unified_think::redis::RedisManager;
use unified_think::error::Result;
use std::time::Duration;
use tokio::time::sleep;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize Redis connection
    let redis = RedisManager::new().await?;
    println!("Connected to Redis");

    // Demo 1: Temporary metadata with expiration
    println!("\n=== Demo 1: Temporary Metadata ===");
    
    // Set temporary metadata that expires in 5 seconds
    redis.set_temp_metadata("test_instance", "status", "processing", 5).await?;
    println!("Set temporary metadata with 5 second TTL");
    
    // Get metadata immediately
    let value = redis.get_temp_metadata("test_instance", "status", None).await?;
    println!("Retrieved metadata: {:?}", value);
    
    // Wait 3 seconds and extend TTL
    sleep(Duration::from_secs(3)).await;
    let value = redis.get_temp_metadata("test_instance", "status", Some(10)).await?;
    println!("After 3s, retrieved and extended TTL to 10s: {:?}", value);
    
    // Wait 6 more seconds (should still exist due to extension)
    sleep(Duration::from_secs(6)).await;
    let value = redis.get_temp_metadata("test_instance", "status", None).await?;
    println!("After 6 more seconds: {:?}", value);

    // Demo 2: Session management
    println!("\n=== Demo 2: Session Management ===");
    
    let session_id = "session_12345";
    
    // Create session fields with 10 second TTL
    redis.set_session_field(session_id, "user_id", "user_789", 10).await?;
    redis.set_session_field(session_id, "role", "admin", 10).await?;
    redis.set_session_field(session_id, "temp_token", "abc123", 10).await?;
    println!("Created session with 3 fields (10s TTL)");
    
    // Get and extend user_id TTL
    let user_id = redis.get_session_field(session_id, "user_id", Some(20)).await?;
    println!("User ID (extended to 20s): {:?}", user_id);
    
    // Pop temp_token (get and delete atomically)
    let token = redis.pop_session_field(session_id, "temp_token").await?;
    println!("Popped temp_token: {:?}", token);
    
    // Verify temp_token is gone
    let token_check = redis.get_session_field(session_id, "temp_token", None).await?;
    println!("Temp token after pop: {:?}", token_check);

    // Demo 3: Cache with field-level expiration
    println!("\n=== Demo 3: Cache Management ===");
    
    // Store different cache entries with different TTLs
    redis.set_cache_field("embeddings", "thought_1", "vector", "[0.1, 0.2, 0.3]", 5).await?;
    redis.set_cache_field("embeddings", "thought_2", "vector", "[0.4, 0.5, 0.6]", 10).await?;
    println!("Cached two embeddings: thought_1 (5s TTL), thought_2 (10s TTL)");
    
    // Wait 6 seconds
    sleep(Duration::from_secs(6)).await;
    
    // Check both cache entries
    let cache1 = redis.get_cache_field("embeddings", "thought_1", "vector").await?;
    let cache2 = redis.get_cache_field("embeddings", "thought_2", "vector").await?;
    println!("After 6s - thought_1: {:?}, thought_2: {:?}", cache1, cache2);

    // Demo 4: Direct use of HGETEX with persist option
    println!("\n=== Demo 4: HGETEX Persist Option ===");
    
    // Set a field with expiration
    redis.hsetex("test:hash", "field1", "will_persist", 5).await?;
    println!("Set field1 with 5s TTL");
    
    // Get and persist (remove expiration)
    let value = redis.hgetex("test:hash", "field1", Some(0)).await?;
    println!("Retrieved and persisted field1: {:?}", value);
    
    // Wait 6 seconds (field should still exist since we persisted it)
    sleep(Duration::from_secs(6)).await;
    let value = redis.hgetex("test:hash", "field1", None).await?;
    println!("After 6s (persisted field): {:?}", value);

    println!("\n=== Demo Complete ===");
    Ok(())
}
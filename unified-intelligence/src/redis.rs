use std::env;
use std::sync::Arc;
use std::time::Duration;
use std::future::Future;
use deadpool_redis::{Config, Runtime, Pool};
use deadpool::{managed::{PoolConfig, Timeouts, QueueMode}};
use redis::{AsyncCommands, JsonAsyncCommands, Script};
use tracing;
use sha2::{Sha256, Digest};
use tokio::time::timeout;
use chrono;

use crate::error::{Result, UnifiedIntelligenceError};
use crate::lua_scripts::{self, LoadedScripts};

/// Redis connection manager
#[derive(Clone)]
pub struct RedisManager {
    pool: Arc<Pool>,
    scripts: Arc<tokio::sync::RwLock<LoadedScripts>>,
}

impl RedisManager {
    /// Create a new Redis manager with connection pool
    pub async fn new() -> Result<Self> {
        // Redis connection configuration from environment variables
        let redis_host = env::var("REDIS_HOST").unwrap_or_else(|_| "localhost".to_string());
        let redis_port = env::var("REDIS_PORT").unwrap_or_else(|_| "6379".to_string());
        let redis_password = env::var("REDIS_PASSWORD")
            .or_else(|_| env::var("REDIS_PASS"))  // Try alternate env var
            .unwrap_or_else(|_| {
                // For backward compatibility, check for the legacy hardcoded password
                // This should only be used temporarily during migration
                if env::var("ALLOW_DEFAULT_REDIS_PASSWORD").is_ok() {
                    tracing::warn!("REDIS_PASSWORD not set, using default for local development. This is insecure and should only be used for local testing.");
                    "legacymind_redis_pass".to_string()
                } else {
                    tracing::error!("REDIS_PASSWORD environment variable is required. Set REDIS_PASSWORD or REDIS_PASS to configure Redis authentication.");
                    panic!("Redis password not configured. Please set REDIS_PASSWORD environment variable.");
                }
            });
        let redis_db = env::var("REDIS_DB").unwrap_or_else(|_| "0".to_string());
        
        // Validate Redis password for URL compatibility
        if !redis_password.is_empty() {
            // Check for characters that could break the Redis URL format
            if redis_password.contains('@') || redis_password.contains(':') || redis_password.contains('/') {
                tracing::error!("Redis password contains invalid characters (@, :, or /). Please use a password without these characters for URL compatibility.");
                return Err(UnifiedIntelligenceError::Configuration("Invalid Redis password format - contains URL-unsafe characters".to_string()));
            }
        }
        
        let redis_url = if redis_password.is_empty() {
            format!("redis://{}:{}/{}", redis_host, redis_port, redis_db)
        } else {
            format!("redis://:{}@{}:{}/{}", redis_password, redis_host, redis_port, redis_db)
        };
        
        tracing::info!("Connecting to Redis at {}:{} (db: {})", redis_host, redis_port, redis_db);
        
        // Configure the connection pool with optimized settings
        let mut cfg = Config::from_url(&redis_url);
        
        // Set pool configuration
        cfg.pool = Some(PoolConfig {
            max_size: 16,  // Good for local high-throughput
            timeouts: Timeouts {
                wait: Some(Duration::from_secs(5)),  // Prevent hanging on connection acquisition
                create: Some(Duration::from_secs(5)),  // Timeout for creating new connections
                recycle: Some(Duration::from_secs(5)),  // Timeout for recycling connections
            },
            queue_mode: QueueMode::Fifo,
        });
        
        let pool = cfg.create_pool(Some(Runtime::Tokio1))
            .map_err(|e| UnifiedIntelligenceError::PoolCreation(e.to_string()))?;
        
        // Test the connection
        let mut conn = pool.get().await?;
        let _: String = redis::cmd("PING").query_async(&mut conn).await?;
        tracing::info!("Redis connection established");
        
        // Create instance with empty scripts for now
        let instance = Self {
            pool: Arc::new(pool),
            scripts: Arc::new(tokio::sync::RwLock::new(LoadedScripts::new())),
        };
        
        // Load Lua scripts
        instance.load_scripts().await?;
        
        Ok(instance)
    }
    
    /// Get a connection from the pool
    pub async fn get_connection(&self) -> Result<deadpool_redis::Connection> {
        Ok(self.pool.get().await?)
    }
    
    /// Get the pool for advanced operations
    pub fn get_pool(&self) -> &Arc<Pool> {
        &self.pool
    }
    
    /// Store API key in Redis for secure access
    pub async fn store_api_key(&self, key_name: &str, api_key: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        
        // Store with a 24-hour expiration (can be refreshed on service restart)
        conn.set_ex(format!("config:{}", key_name), api_key, 86400).await?;
        
        tracing::debug!("Stored API key '{}' in Redis", key_name);
        Ok(())
    }
    
    /// Retrieve API key from Redis
    pub async fn get_api_key(&self, key_name: &str) -> Result<Option<String>> {
        let mut conn = self.get_connection().await?;
        
        let result: Option<String> = conn.get(format!("config:{}", key_name)).await?;
        
        if result.is_some() {
            tracing::debug!("Retrieved API key '{}' from Redis", key_name);
        } else {
            tracing::debug!("API key '{}' not found in Redis", key_name);
        }
        
        Ok(result)
    }
    
    /// Create search index for thoughts
    pub async fn create_search_index(&self) -> Result<bool> {
        let mut conn = self.get_connection().await?;
        
        // Check if index already exists
        let index_exists: std::result::Result<Vec<String>, _> = redis::cmd("FT._LIST")
            .query_async(&mut *conn)
            .await;
        
        if let Ok(indices) = index_exists {
            if indices.contains(&"idx:thoughts".to_string()) {
                tracing::info!("Search index already exists");
                return Ok(true);
            }
        }
        
        // Create the index on JSON fields
        // Updated to handle multiple instance prefixes with proper pattern
        let result: std::result::Result<String, _> = redis::cmd("FT.CREATE")
            .arg("idx:thoughts")
            .arg("ON").arg("JSON")
            .arg("PREFIX").arg("3")
            .arg("Claude:Thoughts:")
            .arg("CC:Thoughts:")
            .arg("CCI:Thoughts:")
            .arg("SCHEMA")
            .arg("$.thought").arg("AS").arg("content").arg("TEXT")
            .arg("$.instance").arg("AS").arg("instance").arg("TAG")
            .arg("$.chain_id").arg("AS").arg("chain_id").arg("TAG")
            .arg("$.timestamp").arg("AS").arg("timestamp").arg("TEXT")
            .query_async(&mut *conn)
            .await;
        
        match result {
            Ok(_) => {
                tracing::info!("Search index created successfully");
                Ok(true)
            }
            Err(e) => {
                tracing::warn!("Failed to create search index: {}. Search will not be available.", e);
                Ok(false)
            }
        }
    }
    
    /// Store a JSON object in Redis
    pub async fn json_set<T: serde::Serialize + Send + Sync>(
        &self,
        key: &str,
        path: &str,
        value: &T,
    ) -> Result<()> {
        let mut conn = self.get_connection().await?;
        conn.json_set(key, path, value).await?;
        Ok(())
    }
    
    /// Get a JSON object from Redis
    pub async fn json_get<T: serde::de::DeserializeOwned>(
        &self,
        key: &str,
        path: &str,
    ) -> Result<Option<T>> {
        let mut conn = self.get_connection().await?;
        
        // Use raw command to handle RedisJSON response
        let result: Option<String> = redis::cmd("JSON.GET")
            .arg(key)
            .arg(path)
            .query_async(&mut *conn)
            .await?;
        
        match result {
            Some(json_str) => {
                // When using "$" path, RedisJSON returns an array
                if path == "$" {
                    // Parse as array and get first element
                    if let Ok(values) = serde_json::from_str::<Vec<serde_json::Value>>(&json_str) {
                        if let Some(first_value) = values.first() {
                            let value = serde_json::from_value(first_value.clone())?;
                            Ok(Some(value))
                        } else {
                            Ok(None)
                        }
                    } else {
                        // Try parsing directly if not an array
                        let value = serde_json::from_str(&json_str)?;
                        Ok(Some(value))
                    }
                } else {
                    // For other paths, parse directly
                    let value = serde_json::from_str(&json_str)?;
                    Ok(Some(value))
                }
            }
            None => Ok(None),
        }
    }
    
    /// Delete a JSON path
    pub async fn json_del(&self, key: &str, path: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        
        redis::cmd("JSON.DEL")
            .arg(key)
            .arg(path)
            .query_async(&mut *conn)
            .await?;
        
        Ok(())
    }
    
    /// Check if a key exists
    pub async fn exists(&self, key: &str) -> Result<bool> {
        let mut conn = self.get_connection().await?;
        Ok(conn.exists(key).await?)
    }
    
    /// Delete a key
    pub async fn del(&self, key: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        conn.del(key).await?;
        Ok(())
    }
    
    // NOTE: The dangerous keys() method has been removed to prevent blocking operations.
    // Use scan_match() instead for pattern matching, which is non-blocking and production-safe.
    
    /// Get a value from Redis
    pub async fn get(&self, key: &str) -> Result<Option<String>> {
        let mut conn = self.get_connection().await?;
        Ok(conn.get(key).await?)
    }
    
    /// Increment a value in a sorted set
    pub async fn zadd(&self, key: &str, member: &str, score: f64) -> Result<()> {
        let mut conn = self.get_connection().await?;
        conn.zadd(key, member, score).await?;
        Ok(())
    }
    
    /// Get members of a sorted set
    pub async fn zrange(&self, key: &str, start: isize, stop: isize) -> Result<Vec<String>> {
        let mut conn = self.get_connection().await?;
        Ok(conn.zrange(key, start, stop).await?)
    }
    
    /// Add member to a set
    pub async fn sadd(&self, key: &str, member: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        conn.sadd(key, member).await?;
        Ok(())
    }
    
    // ===== BOOST SCORE METHODS (Phase 3) =====
    
    /// Increment score in sorted set (for boost scores)
    pub async fn zincrby(&self, key: &str, member: &str, increment: f64) -> Result<f64> {
        let mut conn = self.get_connection().await?;
        
        // Use Redis ZINCRBY command manually
        let mut cmd = redis::cmd("ZINCRBY");
        cmd.arg(key).arg(increment).arg(member);
        
        let new_score: f64 = cmd.query_async(&mut *conn).await?;
        Ok(new_score)
    }
    
    /// Get score of member in sorted set
    pub async fn zscore(&self, key: &str, member: &str) -> Result<Option<f64>> {
        let mut conn = self.get_connection().await?;
        let score: Option<f64> = conn.zscore(key, member).await?;
        Ok(score)
    }
    
    /// Get members of sorted set with scores in descending order
    pub async fn zrevrange_withscores(&self, key: &str, start: isize, stop: isize) -> Result<Vec<(String, f64)>> {
        let mut conn = self.get_connection().await?;
        let mut cmd = redis::cmd("ZREVRANGE");
        cmd.arg(key).arg(start).arg(stop).arg("WITHSCORES");
        
        let results: Vec<String> = cmd.query_async(&mut *conn).await?;
        
        // Parse alternating member, score pairs
        let mut scored_members = Vec::new();
        for chunk in results.chunks(2) {
            if let [member, score_str] = chunk {
                if let Ok(score) = score_str.parse::<f64>() {
                    scored_members.push((member.clone(), score));
                }
            }
        }
        
        Ok(scored_members)
    }
    
    /// Get members within score range (for boost score filtering)
    pub async fn zrangebyscore(&self, key: &str, min_score: f64, max_score: f64) -> Result<Vec<String>> {
        let mut conn = self.get_connection().await?;
        let mut cmd = redis::cmd("ZRANGEBYSCORE");
        cmd.arg(key).arg(min_score).arg(max_score);
        
        let results: Vec<String> = cmd.query_async(&mut *conn).await?;
        Ok(results)
    }
    
    /// Add entry to Redis Stream
    pub async fn xadd(&self, key: &str, id: &str, fields: Vec<(&str, &str)>) -> Result<String> {
        let mut conn = self.get_connection().await?;
        
        // Build the XADD command
        let mut cmd = redis::cmd("XADD");
        cmd.arg(key).arg(id);
        
        // Add field-value pairs
        for (field, value) in fields {
            cmd.arg(field).arg(value);
        }
        
        let result: String = cmd.query_async(&mut *conn).await?;
        Ok(result)
    }
    
    /// Get intersection of multiple sets (SINTER)
    pub async fn sinter(&self, keys: &[String]) -> Result<Vec<String>> {
        if keys.is_empty() {
            return Ok(Vec::new());
        }
        
        let mut conn = self.get_connection().await?;
        
        let mut cmd = redis::cmd("SINTER");
        for key in keys {
            cmd.arg(key);
        }
        
        let result: Vec<String> = cmd.query_async(&mut *conn).await?;
        Ok(result)
    }
    
    /// Get union of multiple sets (SUNION)
    pub async fn sunion(&self, keys: &[String]) -> Result<Vec<String>> {
        if keys.is_empty() {
            return Ok(Vec::new());
        }
        
        let mut conn = self.get_connection().await?;
        
        let mut cmd = redis::cmd("SUNION");
        for key in keys {
            cmd.arg(key);
        }
        
        let result: Vec<String> = cmd.query_async(&mut *conn).await?;
        Ok(result)
    }
    
    /// Execute a Redis search query
    pub async fn search(
        &self,
        index: &str,
        query: &str,
        limit: usize,
    ) -> Result<Vec<(String, f64)>> {
        let mut conn = self.get_connection().await?;
        
        let result: std::result::Result<(i32, Vec<(String, f64)>), _> = redis::cmd("FT.SEARCH")
            .arg(index)
            .arg(query)
            .arg("LIMIT").arg("0").arg(limit)
            .arg("RETURN").arg("0")
            .query_async(&mut *conn)
            .await;
        
        match result {
            Ok((_, results)) => Ok(results),
            Err(e) => {
                tracing::debug!("Search failed: {}", e);
                Err(UnifiedIntelligenceError::SearchUnavailable(e.to_string()))
            }
        }
    }
    
    /// Scan for keys matching a pattern
    /// Get keys matching a pattern (use with caution in production)
    pub async fn keys(&self, pattern: &str) -> Result<Vec<String>> {
        self.scan_match(pattern, 1000).await
    }
    
    pub async fn scan_match(&self, pattern: &str, count: usize) -> Result<Vec<String>> {
        let mut conn = self.get_connection().await?;
        let mut cursor = 0;
        let mut all_keys = Vec::new();
        
        loop {
            let (new_cursor, keys): (u64, Vec<String>) = redis::cmd("SCAN")
                .arg(cursor)
                .arg("MATCH").arg(pattern)
                .arg("COUNT").arg(count)
                .query_async(&mut *conn)
                .await?;
            
            all_keys.extend(keys);
            cursor = new_cursor;
            
            if cursor == 0 {
                break;
            }
        }
        
        Ok(all_keys)
    }
    
    /// Initialize time series for tracking thought metrics
    pub async fn init_thought_metrics(&self, instance: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        let key = format!("ts:{}:thought_count", instance);
        
        // Check if time series already exists
        let exists: std::result::Result<Vec<String>, _> = redis::cmd("TS.INFO")
            .arg(&key)
            .query_async(&mut *conn)
            .await;
        
        if exists.is_ok() {
            tracing::debug!("Time series for instance {} already exists", instance);
            return Ok(());
        }
        
        // Create time series with 24-hour retention and sum duplicate policy
        let result: std::result::Result<String, _> = redis::cmd("TS.CREATE")
            .arg(&key)
            .arg("RETENTION").arg("86400000")  // 24 hours in milliseconds
            .arg("DUPLICATE_POLICY").arg("SUM")
            .arg("LABELS")
            .arg("instance").arg(instance)
            .arg("metric").arg("thought_count")
            .query_async(&mut *conn)
            .await;
        
        match result {
            Ok(_) => {
                tracing::info!("Created time series for tracking thoughts: {}", key);
                Ok(())
            }
            Err(e) => {
                tracing::warn!("Failed to create time series {}: {}. Metrics will not be available.", key, e);
                Ok(())  // Non-fatal error
            }
        }
    }
    
    /// Increment thought count for an instance
    pub async fn increment_thought_count(&self, instance: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        let key = format!("ts:{}:thought_count", instance);
        
        // Get current timestamp
        let timestamp = "*";  // Use server timestamp
        
        // Add value to time series
        let result: std::result::Result<i64, _> = redis::cmd("TS.ADD")
            .arg(&key)
            .arg(timestamp)
            .arg("1")  // Increment by 1
            .query_async(&mut *conn)
            .await;
        
        match result {
            Ok(ts) => {
                tracing::debug!("Incremented thought count for instance {} at timestamp {}", instance, ts);
                Ok(())
            }
            Err(e) => {
                // If time series doesn't exist, try to create it
                if e.to_string().contains("does not exist") {
                    tracing::info!("Time series not found, initializing for instance {}", instance);
                    self.init_thought_metrics(instance).await?;
                    
                    // Retry the increment
                    let retry_result: std::result::Result<i64, _> = redis::cmd("TS.ADD")
                        .arg(&key)
                        .arg(timestamp)
                        .arg("1")
                        .query_async(&mut *conn)
                        .await;
                    
                    match retry_result {
                        Ok(_) => Ok(()),
                        Err(e) => {
                            tracing::warn!("Failed to increment thought count after init: {}", e);
                            Ok(())  // Non-fatal error
                        }
                    }
                } else {
                    tracing::warn!("Failed to increment thought count: {}", e);
                    Ok(())  // Non-fatal error
                }
            }
        }
    }
    
    /// Initialize a Bloom filter for duplicate detection
    pub async fn init_bloom_filter(&self, instance: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        let key = format!("{}:bloom:thoughts", instance);
        
        // Check if bloom filter already exists
        if self.exists(&key).await? {
            tracing::debug!("Bloom filter for instance {} already exists", instance);
            return Ok(());
        }
        
        // Create a bloom filter using BF.RESERVE command
        // Parameters: key, error_rate, capacity
        // 0.01 = 1% false positive rate
        // 100000 = expected number of items
        let result: redis::RedisResult<()> = redis::cmd("BF.RESERVE")
            .arg(&key)
            .arg(0.01f64)  // 1% false positive rate
            .arg(100000i64) // 100k expected items
            .query_async(&mut conn)
            .await;
        
        match result {
            Ok(_) => {
                tracing::info!("Created native Redis bloom filter for instance {} with 0.01 error rate and 100k capacity", instance);
                Ok(())
            }
            Err(e) => {
                // Check if the error is because bloom filter module is not available
                if e.to_string().contains("unknown command") || e.to_string().contains("ERR unknown command 'BF.RESERVE'") {
                    Err(UnifiedIntelligenceError::Configuration(
                        "Redis Bloom Filter module (RedisBloom) is not installed. Please install RedisBloom module to use bloom filters.".to_string()
                    ))
                } else if e.to_string().contains("item exists") {
                    // Filter already exists, this is fine
                    tracing::debug!("Bloom filter for instance {} already exists", instance);
                    Ok(())
                } else {
                    Err(UnifiedIntelligenceError::Internal(format!("Failed to create bloom filter: {}", e)))
                }
            }
        }
    }
    
    /// Check if a thought is potentially a duplicate using the Bloom filter
    pub async fn is_duplicate_thought(&self, instance: &str, thought_content: &str) -> Result<bool> {
        let mut conn = self.get_connection().await?;
        let key = format!("{}:bloom:thoughts", instance);
        
        // Hash the thought content using SHA256
        let mut hasher = Sha256::new();
        hasher.update(thought_content.as_bytes());
        let hash = hasher.finalize();
        let hash_str = format!("{:x}", hash);
        
        // Use BF.EXISTS command to check if item exists in bloom filter
        let result: redis::RedisResult<i32> = redis::cmd("BF.EXISTS")
            .arg(&key)
            .arg(&hash_str)
            .query_async(&mut conn)
            .await;
        
        match result {
            Ok(exists) => {
                // BF.EXISTS returns 1 if item might exist, 0 if it definitely doesn't exist
                Ok(exists == 1)
            }
            Err(e) => {
                // Check if the error is because bloom filter module is not available
                if e.to_string().contains("unknown command") || e.to_string().contains("ERR unknown command 'BF.EXISTS'") {
                    tracing::warn!("Redis Bloom Filter module not available, duplicate detection disabled");
                    Ok(false) // Assume no duplicate if bloom filter is not available
                } else if e.to_string().contains("not found") {
                    // Bloom filter doesn't exist yet, so no duplicates
                    Ok(false)
                } else {
                    Err(UnifiedIntelligenceError::Internal(format!("Failed to check bloom filter: {}", e)))
                }
            }
        }
    }
    
    /// Add a thought hash to the Bloom filter after saving
    pub async fn add_to_bloom_filter(&self, instance: &str, thought_content: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        let key = format!("{}:bloom:thoughts", instance);
        
        // Hash the thought content using SHA256
        let mut hasher = Sha256::new();
        hasher.update(thought_content.as_bytes());
        let hash = hasher.finalize();
        let hash_str = format!("{:x}", hash);
        
        // Use BF.ADD command to add item to bloom filter
        let result: redis::RedisResult<i32> = redis::cmd("BF.ADD")
            .arg(&key)
            .arg(&hash_str)
            .query_async(&mut conn)
            .await;
        
        match result {
            Ok(added) => {
                // BF.ADD returns 1 if item was added, 0 if it already existed
                if added == 1 {
                    tracing::debug!("Added thought hash to bloom filter for instance {}", instance);
                } else {
                    tracing::debug!("Thought hash already existed in bloom filter for instance {}", instance);
                }
                Ok(())
            }
            Err(e) => {
                // Check if the error is because bloom filter module is not available
                if e.to_string().contains("unknown command") || e.to_string().contains("ERR unknown command 'BF.ADD'") {
                    tracing::warn!("Redis Bloom Filter module not available, skipping duplicate tracking");
                    Ok(()) // Don't fail if bloom filter is not available
                } else if e.to_string().contains("not found") {
                    // Bloom filter doesn't exist, try to create it first
                    tracing::info!("Bloom filter doesn't exist, creating it first");
                    self.init_bloom_filter(instance).await?;
                    
                    // Try adding again
                    let retry_result: redis::RedisResult<i32> = redis::cmd("BF.ADD")
                        .arg(&key)
                        .arg(&hash_str)
                        .query_async(&mut conn)
                        .await;
                    
                    match retry_result {
                        Ok(_) => {
                            tracing::debug!("Added thought hash to bloom filter after creating filter");
                            Ok(())
                        }
                        Err(e) => {
                            Err(UnifiedIntelligenceError::Internal(format!("Failed to add to bloom filter after creation: {}", e)))
                        }
                    }
                } else {
                    Err(UnifiedIntelligenceError::Internal(format!("Failed to add to bloom filter: {}", e)))
                }
            }
        }
    }
    
    /// Get bloom filter information (for debugging/monitoring)
    pub async fn get_bloom_filter_info(&self, instance: &str) -> Result<Option<serde_json::Value>> {
        let mut conn = self.get_connection().await?;
        let key = format!("{}:bloom:thoughts", instance);
        
        // Use BF.INFO command to get bloom filter information
        let result: redis::RedisResult<Vec<(String, redis::Value)>> = redis::cmd("BF.INFO")
            .arg(&key)
            .query_async(&mut conn)
            .await;
        
        match result {
            Ok(info) => {
                // Convert Redis response to JSON
                let mut json_info = serde_json::Map::new();
                
                for (key, value) in info {
                    let json_value = match value {
                        redis::Value::Int(i) => serde_json::Value::Number(i.into()),
                        redis::Value::BulkString(s) => {
                            serde_json::Value::String(String::from_utf8_lossy(&s).to_string())
                        }
                        redis::Value::SimpleString(s) => serde_json::Value::String(s),
                        _ => serde_json::Value::Null,
                    };
                    json_info.insert(key, json_value);
                }
                
                Ok(Some(serde_json::Value::Object(json_info)))
            }
            Err(e) => {
                if e.to_string().contains("unknown command") || e.to_string().contains("not found") {
                    Ok(None) // Bloom filter doesn't exist or module not available
                } else {
                    Err(UnifiedIntelligenceError::Internal(format!("Failed to get bloom filter info: {}", e)))
                }
            }
        }
    }
    
    // Timeout wrapper methods
    
    /// Execute an async operation with a timeout
    pub async fn with_timeout<F, T>(
        duration: Duration,
        operation: F,
    ) -> Result<T>
    where
        F: Future<Output = Result<T>>,
    {
        match timeout(duration, operation).await {
            Ok(result) => result,
            Err(_) => Err(UnifiedIntelligenceError::Timeout(duration.as_secs())),
        }
    }
    
    /// Get JSON value with timeout (default 5 seconds)
    pub async fn json_get_with_timeout<T>(
        &self,
        key: &str,
        path: &str,
    ) -> Result<Option<T>>
    where
        T: serde::de::DeserializeOwned,
    {
        Self::with_timeout(
            Duration::from_secs(5),
            self.json_get(key, path)
        ).await
    }
    
    /// Set JSON value with timeout (default 5 seconds)
    pub async fn json_set_with_timeout<T>(
        &self,
        key: &str,
        path: &str,
        value: &T,
    ) -> Result<()>
    where
        T: serde::Serialize + Send + Sync,
    {
        Self::with_timeout(
            Duration::from_secs(5),
            self.json_set(key, path, value)
        ).await
    }
    
    /// Execute search with timeout (default 10 seconds - searches can be slower)
    pub async fn search_with_timeout(
        &self,
        index: &str,
        query: &str,
        limit: usize,
    ) -> Result<Vec<(String, f64)>> {
        Self::with_timeout(
            Duration::from_secs(10),
            self.search(index, query, limit)
        ).await
    }
    
    // Lua Script Methods
    
    /// Load all Lua scripts into Redis and store their SHA hashes
    pub async fn load_scripts(&self) -> Result<()> {
        let mut conn = self.get_connection().await?;
        let mut scripts = LoadedScripts::new();
        
        // Load store thought script
        let store_script = Script::new(lua_scripts::STORE_THOUGHT_SCRIPT);
        scripts.store_thought = store_script.prepare_invoke()
            .load_async(&mut *conn)
            .await
            .map_err(|e| UnifiedIntelligenceError::Internal(format!("Failed to load store thought script: {}", e)))?;
        
        // Load get thought script
        let get_script = Script::new(lua_scripts::GET_THOUGHT_SCRIPT);
        scripts.get_thought = get_script.prepare_invoke()
            .load_async(&mut *conn)
            .await
            .map_err(|e| UnifiedIntelligenceError::Internal(format!("Failed to load get thought script: {}", e)))?;
        
        // Load search thoughts script
        let search_script = Script::new(lua_scripts::SEARCH_THOUGHTS_SCRIPT);
        scripts.search_thoughts = search_script.prepare_invoke()
            .load_async(&mut *conn)
            .await
            .map_err(|e| UnifiedIntelligenceError::Internal(format!("Failed to load search thoughts script: {}", e)))?;
        
        // Load update chain script
        let update_chain_script = Script::new(lua_scripts::UPDATE_CHAIN_SCRIPT);
        scripts.update_chain = update_chain_script.prepare_invoke()
            .load_async(&mut *conn)
            .await
            .map_err(|e| UnifiedIntelligenceError::Internal(format!("Failed to load update chain script: {}", e)))?;
        
        // Load get chain thoughts script
        let get_chain_script = Script::new(lua_scripts::GET_CHAIN_THOUGHTS_SCRIPT);
        scripts.get_chain_thoughts = get_chain_script.prepare_invoke()
            .load_async(&mut *conn)
            .await
            .map_err(|e| UnifiedIntelligenceError::Internal(format!("Failed to load get chain thoughts script: {}", e)))?;
        
        // Load cleanup expired script
        let cleanup_script = Script::new(lua_scripts::CLEANUP_EXPIRED_SCRIPT);
        scripts.cleanup_expired = cleanup_script.prepare_invoke()
            .load_async(&mut *conn)
            .await
            .map_err(|e| UnifiedIntelligenceError::Internal(format!("Failed to load cleanup expired script: {}", e)))?;
        
        // Update the scripts in the instance
        let mut script_store = self.scripts.write().await;
        *script_store = scripts;
        
        tracing::info!("Successfully loaded all Lua scripts");
        
        Ok(())
    }
    
    /// Execute atomic thought storage using Lua script
    pub async fn store_thought_atomic(
        &self,
        thought_key: &str,
        bloom_key: &str,
        ts_key: &str,
        chain_key: Option<&str>,
        thought_json: &str,
        uuid: &str,
        timestamp: i64,
        chain_id: Option<&str>,
    ) -> Result<bool> {
        let mut conn = self.get_connection().await?;
        
        // Prepare keys
        let mut keys = vec![thought_key, bloom_key, ts_key];
        if let Some(chain) = chain_key {
            keys.push(chain);
        } else {
            keys.push("");  // Placeholder
        }
        
        // Prepare arguments
        let args = vec![
            thought_json.to_string(),
            uuid.to_string(),
            timestamp.to_string(),
            chain_id.unwrap_or("").to_string(),
        ];
        
        // Get script SHA
        let script_sha = {
            let scripts = self.scripts.read().await;
            scripts.store_thought.clone()
        };
        
        // Execute script
        let result: String = redis::cmd("EVALSHA")
            .arg(&script_sha)
            .arg(keys.len())
            .arg(&keys)
            .arg(&args)
            .query_async(&mut *conn)
            .await
            .or_else(|e| {
                // If script not loaded, reload and retry
                if e.to_string().contains("NOSCRIPT") {
                    tracing::warn!("Script not found in cache, reloading...");
                    return Err(UnifiedIntelligenceError::Internal("Script needs reloading".to_string()));
                }
                Err(UnifiedIntelligenceError::Redis(e))
            })?;
        
        match result.as_str() {
            "OK" => Ok(true),
            "DUPLICATE" => Ok(false),
            _ => Err(UnifiedIntelligenceError::Internal(format!("Unexpected script result: {}", result))),
        }
    }
    
    /// Execute atomic thought retrieval using Lua script
    pub async fn get_thought_atomic(
        &self,
        thought_key: &str,
        access_count_key: &str,
        last_access_key: &str,
        timestamp: i64,
    ) -> Result<Option<String>> {
        let mut conn = self.get_connection().await?;
        
        let keys = vec![thought_key, access_count_key, last_access_key];
        let args = vec![timestamp.to_string()];
        
        // Get script SHA
        let script_sha = {
            let scripts = self.scripts.read().await;
            scripts.get_thought.clone()
        };
        
        let result: Option<String> = redis::cmd("EVALSHA")
            .arg(&script_sha)
            .arg(keys.len())
            .arg(&keys)
            .arg(&args)
            .query_async(&mut *conn)
            .await
            .or_else(|e| {
                if e.to_string().contains("NOSCRIPT") {
                    tracing::warn!("Get thought script not found in cache");
                    return Err(UnifiedIntelligenceError::Internal("Script needs reloading".to_string()));
                }
                Err(UnifiedIntelligenceError::Redis(e))
            })?;
        
        Ok(result)
    }
    
    /// Execute atomic chain update using Lua script
    pub async fn update_chain_atomic(
        &self,
        chain_key: &str,
        thought_key: &str,
        operation: &str,
        uuid: &str,
    ) -> Result<bool> {
        let mut conn = self.get_connection().await?;
        
        let keys = vec![chain_key, thought_key];
        let args = vec![operation, uuid];
        
        // Get script SHA
        let script_sha = {
            let scripts = self.scripts.read().await;
            scripts.update_chain.clone()
        };
        
        let result: i32 = redis::cmd("EVALSHA")
            .arg(&script_sha)
            .arg(keys.len())
            .arg(&keys)
            .arg(&args)
            .query_async(&mut *conn)
            .await
            .or_else(|e| {
                if e.to_string().contains("NOSCRIPT") {
                    tracing::warn!("Update chain script not found in cache");
                    return Err(UnifiedIntelligenceError::Internal("Script needs reloading".to_string()));
                }
                Err(UnifiedIntelligenceError::Redis(e))
            })?;
        
        Ok(result == 1)
    }
    
    /// Get all thoughts in a chain using Lua script
    pub async fn get_chain_thoughts_atomic(
        &self,
        chain_key: &str,
        instance: &str,
    ) -> Result<Vec<String>> {
        let mut conn = self.get_connection().await?;
        
        let keys = vec![chain_key];
        
        // Get script SHA
        let script_sha = {
            let scripts = self.scripts.read().await;
            scripts.get_chain_thoughts.clone()
        };
        
        let result: Vec<String> = redis::cmd("EVALSHA")
            .arg(&script_sha)
            .arg(keys.len())
            .arg(&keys)
            .arg(instance) // ARGV[1]
            .query_async(&mut *conn)
            .await
            .or_else(|e| {
                if e.to_string().contains("NOSCRIPT") {
                    tracing::warn!("Get chain thoughts script not found in cache");
                    return Err(UnifiedIntelligenceError::Internal("Script needs reloading".to_string()));
                }
                Err(UnifiedIntelligenceError::Redis(e))
            })?;
        
        Ok(result)
    }
    
    // Event Stream Methods
    
    /// Initialize event stream for an instance with max length
    pub async fn init_event_stream(&self, instance: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        let stream_key = format!("{}:events", instance);
        
        // Check if stream exists by trying to get info
        let exists: std::result::Result<Vec<Vec<String>>, _> = redis::cmd("XINFO")
            .arg("STREAM")
            .arg(&stream_key)
            .query_async(&mut *conn)
            .await;
        
        if exists.is_ok() {
            tracing::debug!("Event stream for instance {} already exists", instance);
            return Ok(());
        }
        
        // Create stream with initial entry
        let timestamp = "*";  // Let Redis assign timestamp
        let result: std::result::Result<String, _> = redis::cmd("XADD")
            .arg(&stream_key)
            .arg("MAXLEN")
            .arg("~")  // Approximate trimming for performance
            .arg("10000")  // Keep approximately 10k events
            .arg(timestamp)
            .arg("event_type")
            .arg("stream_initialized")
            .arg("instance")
            .arg(instance)
            .arg("timestamp")
            .arg(chrono::Utc::now().to_rfc3339())
            .query_async(&mut *conn)
            .await;
        
        match result {
            Ok(id) => {
                tracing::info!("Created event stream for instance {} with ID {}", instance, id);
                Ok(())
            }
            Err(e) => {
                tracing::error!("Failed to create event stream: {}", e);
                Err(UnifiedIntelligenceError::Redis(e))
            }
        }
    }
    
    /// Log a generic event to the stream
    pub async fn log_event(
        &self,
        instance: &str,
        event_type: &str,
        data: Vec<(&str, &str)>,
    ) -> Result<String> {
        let mut conn = self.get_connection().await?;
        let stream_key = format!("{}:events", instance);
        
        // Build arguments for XADD
        let mut args = vec![];
        args.push("MAXLEN");
        args.push("~");
        args.push("10000");
        args.push("*");  // Auto-generate ID
        
        // Add event type and instance
        args.push("event_type");
        args.push(event_type);
        args.push("instance");
        args.push(instance);
        args.push("timestamp");
        
        let timestamp = chrono::Utc::now().to_rfc3339();
        let timestamp_ref = &timestamp;
        args.push(timestamp_ref);
        
        // Add custom data fields
        for (key, value) in &data {
            args.push(key);
            args.push(value);
        }
        
        // Execute XADD
        let result: std::result::Result<String, _> = redis::cmd("XADD")
            .arg(&stream_key)
            .arg(&args)
            .query_async(&mut *conn)
            .await;
        
        match result {
            Ok(id) => {
                tracing::debug!("Logged {} event for instance {} with ID {}", event_type, instance, id);
                Ok(id)
            }
            Err(e) => {
                tracing::error!("Failed to log event: {}", e);
                Err(UnifiedIntelligenceError::Redis(e))
            }
        }
    }
    
    /// Log a thought-specific event
    pub async fn log_thought_event(
        &self,
        instance: &str,
        event_type: &str,
        thought_id: &str,
        chain_id: Option<&str>,
        additional_data: Option<Vec<(&str, &str)>>,
    ) -> Result<String> {
        let mut data = vec![
            ("thought_id", thought_id),
        ];
        
        // Add chain_id if present
        if let Some(chain) = chain_id {
            data.push(("chain_id", chain));
        }
        
        // Add any additional data
        if let Some(extra) = additional_data {
            data.extend(extra);
        }
        
        self.log_event(instance, event_type, data).await
    }
    
    // Vector Set Methods for Semantic Search
    
    /// Initialize a vector set for storing thought embeddings
    pub async fn init_vector_set(&self, instance: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        let vector_set_key = format!("vset:{}:thoughts", instance);
        
        // Check if vector set already exists
        if self.exists(&vector_set_key).await? {
            tracing::debug!("Vector set for instance {} already exists", instance);
            return Ok(());
        }
        
        // Create vector set with VSET.CREATE
        // Parameters: key, dimensionality, distance_metric, algorithm
        let result: redis::RedisResult<()> = redis::cmd("VSET.CREATE")
            .arg(&vector_set_key)
            .arg("DIM").arg(384i64)  // 384-dimensional vectors
            .arg("DISTANCE_METRIC").arg("COSINE")  // Cosine similarity
            .arg("INITIAL_CAP").arg(10000i64)  // Initial capacity
            .arg("M").arg(16i64)  // HNSW parameter M
            .arg("EF_CONSTRUCTION").arg(200i64)  // HNSW parameter
            .query_async(&mut conn)
            .await;
        
        match result {
            Ok(_) => {
                tracing::info!("Created vector set for instance {} with 384 dimensions and cosine distance", instance);
                Ok(())
            }
            Err(e) => {
                // Check if the error is because vector module is not available
                if e.to_string().contains("unknown command") || e.to_string().contains("ERR unknown command 'VSET.CREATE'") {
                    tracing::warn!("Redis Vector Sets module not available, semantic search disabled");
                    Ok(())  // Non-fatal error
                } else if e.to_string().contains("exists") {
                    // Vector set already exists, this is fine
                    tracing::debug!("Vector set for instance {} already exists", instance);
                    Ok(())
                } else {
                    Err(UnifiedIntelligenceError::Internal(format!("Failed to create vector set: {}", e)))
                }
            }
        }
    }
    
    /// Add a thought vector to the vector set
    pub async fn add_thought_vector(
        &self,
        instance: &str,
        thought_id: &str,
        embedding: &[f64],
    ) -> Result<()> {
        let mut conn = self.get_connection().await?;
        let vector_set_key = format!("vset:{}:thoughts", instance);
        
        // Ensure embedding is 384 dimensions
        if embedding.len() != 384 {
            return Err(UnifiedIntelligenceError::Validation {
                field: "embedding".to_string(),
                reason: format!("Embedding must be 384 dimensions, got {}", embedding.len()),
            });
        }
        
        // Convert f64 array to string representation for Redis
        let embedding_str: Vec<String> = embedding.iter()
            .map(|&v| v.to_string())
            .collect();
        
        // Add vector with VSET.ADD
        let result: redis::RedisResult<i32> = redis::cmd("VSET.ADD")
            .arg(&vector_set_key)
            .arg(thought_id)
            .arg(&embedding_str)
            .query_async(&mut conn)
            .await;
        
        match result {
            Ok(added) => {
                if added == 1 {
                    tracing::debug!("Added thought vector for {} to vector set", thought_id);
                } else {
                    tracing::debug!("Updated existing thought vector for {}", thought_id);
                }
                Ok(())
            }
            Err(e) => {
                if e.to_string().contains("unknown command") {
                    tracing::debug!("Vector Sets module not available, skipping vector addition");
                    Ok(())  // Non-fatal error
                } else if e.to_string().contains("not found") {
                    // Vector set doesn't exist, try to create it first
                    tracing::info!("Vector set doesn't exist, creating it first");
                    self.init_vector_set(instance).await?;
                    
                    // Try adding again
                    let retry_result: redis::RedisResult<i32> = redis::cmd("VSET.ADD")
                        .arg(&vector_set_key)
                        .arg(thought_id)
                        .arg(&embedding_str)
                        .query_async(&mut conn)
                        .await;
                    
                    match retry_result {
                        Ok(_) => {
                            tracing::debug!("Added thought vector after creating vector set");
                            Ok(())
                        }
                        Err(e) => {
                            Err(UnifiedIntelligenceError::Internal(format!("Failed to add vector after creation: {}", e)))
                        }
                    }
                } else {
                    Err(UnifiedIntelligenceError::Internal(format!("Failed to add thought vector: {}", e)))
                }
            }
        }
    }
    
    /// Search for similar thoughts using vector similarity
    pub async fn search_similar_thoughts(
        &self,
        instance: &str,
        query_embedding: &[f64],
        limit: usize,
    ) -> Result<Vec<(String, f64)>> {
        let mut conn = self.get_connection().await?;
        let vector_set_key = format!("vset:{}:thoughts", instance);
        
        // Ensure embedding is 384 dimensions
        if query_embedding.len() != 384 {
            return Err(UnifiedIntelligenceError::Validation {
                field: "query_embedding".to_string(),
                reason: format!("Query embedding must be 384 dimensions, got {}", query_embedding.len()),
            });
        }
        
        // Convert f64 array to string representation for Redis
        let embedding_str: Vec<String> = query_embedding.iter()
            .map(|&v| v.to_string())
            .collect();
        
        // Search with VSET.SEARCH
        let result: redis::RedisResult<Vec<(String, String)>> = redis::cmd("VSET.SEARCH")
            .arg(&vector_set_key)
            .arg(&embedding_str)
            .arg("K").arg(limit)
            .arg("EF_RUNTIME").arg(100)  // HNSW runtime parameter
            .query_async(&mut conn)
            .await;
        
        match result {
            Ok(results) => {
                // Convert results from (id, distance_str) to (id, distance_f64)
                let mut parsed_results = Vec::new();
                for (id, distance_str) in results {
                    if let Ok(distance) = distance_str.parse::<f64>() {
                        // Convert cosine distance to similarity score (1 - distance)
                        let similarity = 1.0 - distance;
                        parsed_results.push((id, similarity));
                    }
                }
                Ok(parsed_results)
            }
            Err(e) => {
                if e.to_string().contains("unknown command") || e.to_string().contains("not found") {
                    tracing::debug!("Vector search not available");
                    Ok(vec![])  // Return empty results if vector search not available
                } else {
                    Err(UnifiedIntelligenceError::Internal(format!("Failed to search similar thoughts: {}", e)))
                }
            }
        }
    }
    
    /// Get vector set information (for debugging/monitoring)
    pub async fn get_vector_set_info(&self, instance: &str) -> Result<Option<serde_json::Value>> {
        let mut conn = self.get_connection().await?;
        let vector_set_key = format!("vset:{}:thoughts", instance);
        
        // Use VSET.INFO command to get vector set information
        let result: redis::RedisResult<Vec<(String, redis::Value)>> = redis::cmd("VSET.INFO")
            .arg(&vector_set_key)
            .query_async(&mut conn)
            .await;
        
        match result {
            Ok(info) => {
                // Convert Redis response to JSON
                let mut json_info = serde_json::Map::new();
                
                for (key, value) in info {
                    let json_value = match value {
                        redis::Value::Int(i) => serde_json::Value::Number(i.into()),
                        redis::Value::BulkString(s) => {
                            serde_json::Value::String(String::from_utf8_lossy(&s).to_string())
                        }
                        redis::Value::SimpleString(s) => serde_json::Value::String(s),
                        _ => serde_json::Value::Null,
                    };
                    json_info.insert(key, json_value);
                }
                
                Ok(Some(serde_json::Value::Object(json_info)))
            }
            Err(e) => {
                if e.to_string().contains("unknown command") || e.to_string().contains("not found") {
                    Ok(None)  // Vector set doesn't exist or module not available
                } else {
                    Err(UnifiedIntelligenceError::Internal(format!("Failed to get vector set info: {}", e)))
                }
            }
        }
    }
    
    // Redis 8.0 Hash Field Expiration Methods
    
    /// Get hash field value and optionally set/update expiration using HGETEX (Redis 8.0+)
    /// Options:
    /// - None: Just get the value
    /// - Some(seconds): Get value and set expiration to N seconds
    /// - Some(0): Get value and persist (remove expiration)
    pub async fn hgetex(
        &self,
        key: &str,
        field: &str,
        expire_option: Option<i64>,
    ) -> Result<Option<String>> {
        let mut conn = self.get_connection().await?;
        
        // Build command based on expiration option
        let mut cmd = redis::cmd("HGETEX");
        cmd.arg(key).arg(field);
        
        if let Some(seconds) = expire_option {
            if seconds > 0 {
                cmd.arg("EX").arg(seconds);
            } else if seconds == 0 {
                cmd.arg("PERSIST");
            }
        }
        
        let result: redis::RedisResult<Option<String>> = cmd
            .query_async(&mut *conn)
            .await;
        
        match result {
            Ok(value) => Ok(value),
            Err(e) => {
                // Check if command is not available (Redis < 8.0)
                if e.to_string().contains("unknown command") || e.to_string().contains("ERR unknown command 'HGETEX'") {
                    tracing::debug!("HGETEX not available, falling back to HGET");
                    // Fallback to regular HGET
                    let value: Option<String> = conn.hget(key, field).await?;
                    Ok(value)
                } else {
                    Err(UnifiedIntelligenceError::Redis(e))
                }
            }
        }
    }
    
    /// Set hash field with expiration using HSETEX (Redis 8.0+)
    /// Atomically sets field value and expiration
    pub async fn hsetex(
        &self,
        key: &str,
        field: &str,
        value: &str,
        seconds: i64,
    ) -> Result<bool> {
        let mut conn = self.get_connection().await?;
        
        // HSETEX key field seconds value
        let result: redis::RedisResult<i32> = redis::cmd("HSETEX")
            .arg(key)
            .arg(field)
            .arg(seconds)
            .arg(value)
            .query_async(&mut *conn)
            .await;
        
        match result {
            Ok(created) => Ok(created == 1),  // 1 = new field, 0 = updated existing
            Err(e) => {
                // Check if command is not available (Redis < 8.0)
                if e.to_string().contains("unknown command") || e.to_string().contains("ERR unknown command 'HSETEX'") {
                    tracing::debug!("HSETEX not available, falling back to HSET (without expiration)");
                    // Fallback to regular HSET (no field-level expiration)
                    let created: bool = conn.hset(key, field, value).await?;
                    Ok(created)
                } else {
                    Err(UnifiedIntelligenceError::Redis(e))
                }
            }
        }
    }
    
    /// Atomically get and delete hash field using HGETDEL (Redis 8.0+)
    pub async fn hgetdel(
        &self,
        key: &str,
        field: &str,
    ) -> Result<Option<String>> {
        let mut conn = self.get_connection().await?;
        
        // HGETDEL key field
        let result: redis::RedisResult<Option<String>> = redis::cmd("HGETDEL")
            .arg(key)
            .arg(field)
            .query_async(&mut *conn)
            .await;
        
        match result {
            Ok(value) => Ok(value),
            Err(e) => {
                // Check if command is not available (Redis < 8.0)
                if e.to_string().contains("unknown command") || e.to_string().contains("ERR unknown command 'HGETDEL'") {
                    tracing::debug!("HGETDEL not available, falling back to HGET+HDEL");
                    // Fallback to non-atomic HGET + HDEL
                    let value: Option<String> = conn.hget(key, field).await?;
                    if value.is_some() {
                        let _: bool = conn.hdel(key, field).await?;
                    }
                    Ok(value)
                } else {
                    Err(UnifiedIntelligenceError::Redis(e))
                }
            }
        }
    }
    
    // Convenience wrapper methods
    
    /// Set hash field with TTL in seconds - convenience wrapper for HSETEX
    pub async fn set_hash_field_with_ttl(
        &self,
        key: &str,
        field: &str,
        value: &str,
        ttl_seconds: u64,
    ) -> Result<bool> {
        self.hsetex(key, field, value, ttl_seconds as i64).await
    }
    
    /// Get hash field and extend TTL on access - convenience wrapper for HGETEX
    pub async fn get_hash_field_extend_ttl(
        &self,
        key: &str,
        field: &str,
        ttl_seconds: u64,
    ) -> Result<Option<String>> {
        self.hgetex(key, field, Some(ttl_seconds as i64)).await
    }
    
    /// Get hash field without affecting expiration
    pub async fn get_hash_field_preserve_ttl(
        &self,
        key: &str,
        field: &str,
    ) -> Result<Option<String>> {
        self.hgetex(key, field, None).await
    }
    
    /// Get hash field and remove expiration (persist)
    pub async fn get_hash_field_persist(
        &self,
        key: &str,
        field: &str,
    ) -> Result<Option<String>> {
        self.hgetex(key, field, Some(0)).await
    }
    
    // Use case specific methods for unified-think
    
    /// Store temporary metadata with expiration
    pub async fn set_temp_metadata(
        &self,
        instance: &str,
        field: &str,
        value: &str,
        ttl_seconds: u64,
    ) -> Result<bool> {
        let key = format!("metadata:{}:temp", instance);
        self.set_hash_field_with_ttl(&key, field, value, ttl_seconds).await
    }
    
    /// Get temporary metadata and refresh TTL
    pub async fn get_temp_metadata(
        &self,
        instance: &str,
        field: &str,
        refresh_ttl_seconds: Option<u64>,
    ) -> Result<Option<String>> {
        let key = format!("metadata:{}:temp", instance);
        match refresh_ttl_seconds {
            Some(ttl) => self.get_hash_field_extend_ttl(&key, field, ttl).await,
            None => self.get_hash_field_preserve_ttl(&key, field).await,
        }
    }
    
    /// Store session data with expiration
    pub async fn set_session_field(
        &self,
        session_id: &str,
        field: &str,
        value: &str,
        ttl_seconds: u64,
    ) -> Result<bool> {
        let key = format!("session:{}", session_id);
        self.set_hash_field_with_ttl(&key, field, value, ttl_seconds).await
    }
    
    /// Get session data and extend session on access
    pub async fn get_session_field(
        &self,
        session_id: &str,
        field: &str,
        extend_ttl_seconds: Option<u64>,
    ) -> Result<Option<String>> {
        let key = format!("session:{}", session_id);
        match extend_ttl_seconds {
            Some(ttl) => self.get_hash_field_extend_ttl(&key, field, ttl).await,
            None => self.get_hash_field_preserve_ttl(&key, field).await,
        }
    }
    
    /// Pop session field (get and delete atomically)
    pub async fn pop_session_field(
        &self,
        session_id: &str,
        field: &str,
    ) -> Result<Option<String>> {
        let key = format!("session:{}", session_id);
        self.hgetdel(&key, field).await
    }
    
    /// Store cache entry with field-level expiration
    pub async fn set_cache_field(
        &self,
        cache_type: &str,
        cache_key: &str,
        field: &str,
        value: &str,
        ttl_seconds: u64,
    ) -> Result<bool> {
        let key = format!("cache:{}:{}", cache_type, cache_key);
        self.set_hash_field_with_ttl(&key, field, value, ttl_seconds).await
    }
    
    /// Get cache entry without affecting TTL
    pub async fn get_cache_field(
        &self,
        cache_type: &str,
        cache_key: &str,
        field: &str,
    ) -> Result<Option<String>> {
        let key = format!("cache:{}:{}", cache_type, cache_key);
        self.get_hash_field_preserve_ttl(&key, field).await
    }

    /// Publish an event to Redis Streams for background processing
    pub async fn publish_stream_event(
        &self,
        instance: &str,
        event_type: &str,
        data: &serde_json::Value,
    ) -> Result<String> {
        let stream_key = format!("{}:events", instance);
        let event_id = "*"; // Auto-generate timestamp
        
        let fields = vec![
            ("type", event_type.to_string()),
            ("data", data.to_string()),
            ("published_at", chrono::Utc::now().to_rfc3339()),
        ];
        
        let mut conn = self.get_connection().await?;
        let event_id: String = conn.xadd(&stream_key, event_id, &fields).await?;
        
        tracing::debug!("Published {} event to stream {}: {}", event_type, stream_key, event_id);
        Ok(event_id)
    }
}
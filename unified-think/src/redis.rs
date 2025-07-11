use std::env;
use std::sync::Arc;
use deadpool_redis::{Config, Runtime, Pool};
use redis::{AsyncCommands, JsonAsyncCommands};
use tracing;

use crate::error::{Result, UnifiedThinkError};

/// Redis connection manager
#[derive(Clone)]
pub struct RedisManager {
    pool: Arc<Pool>,
}

impl RedisManager {
    /// Create a new Redis manager with connection pool
    pub async fn new() -> Result<Self> {
        // Redis connection configuration from environment variables
        let redis_host = env::var("REDIS_HOST").unwrap_or_else(|_| "192.168.1.160".to_string());
        let redis_port = env::var("REDIS_PORT").unwrap_or_else(|_| "6379".to_string());
        let redis_password = env::var("REDIS_PASSWORD")
            .or_else(|_| env::var("REDIS_PASS"))  // Try alternate env var
            .unwrap_or_else(|_| {
                tracing::warn!("REDIS_PASSWORD not set, using default for local development");
                "legacymind_redis_pass".to_string()
            });
        let redis_db = env::var("REDIS_DB").unwrap_or_else(|_| "0".to_string());
        
        let redis_url = if redis_password.is_empty() {
            format!("redis://{}:{}/{}", redis_host, redis_port, redis_db)
        } else {
            format!("redis://:{}@{}:{}/{}", redis_password, redis_host, redis_port, redis_db)
        };
        
        tracing::info!("Connecting to Redis at {}:{} (db: {})", redis_host, redis_port, redis_db);
        let cfg = Config::from_url(&redis_url);
        let pool = cfg.create_pool(Some(Runtime::Tokio1))
            .map_err(|e| UnifiedThinkError::PoolCreation(e.to_string()))?;
        
        // Test the connection
        let mut conn = pool.get().await?;
        let _: String = redis::cmd("PING").query_async(&mut conn).await?;
        tracing::info!("Redis connection established");
        
        Ok(Self {
            pool: Arc::new(pool),
        })
    }
    
    /// Get a connection from the pool
    pub async fn get_connection(&self) -> Result<deadpool_redis::Connection> {
        Ok(self.pool.get().await?)
    }
    
    /// Get the pool for advanced operations
    pub fn get_pool(&self) -> &Arc<Pool> {
        &self.pool
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
        let result: std::result::Result<String, _> = redis::cmd("FT.CREATE")
            .arg("idx:thoughts")
            .arg("ON").arg("JSON")
            .arg("PREFIX").arg("1").arg("thought:")
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
    
    /// Get all keys matching a pattern
    pub async fn keys(&self, pattern: &str) -> Result<Vec<String>> {
        let mut conn = self.get_connection().await?;
        Ok(conn.keys(pattern).await?)
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
                Err(UnifiedThinkError::SearchUnavailable(e.to_string()))
            }
        }
    }
    
    /// Scan for keys matching a pattern
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
}
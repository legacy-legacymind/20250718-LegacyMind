use crate::error::{Result, UnifiedMindError};
use crate::models::CachedResult;
use chrono::{DateTime, Utc};
use deadpool_redis::{Config, Connection, Pool, Runtime};
use redis::AsyncCommands;
use std::env;
use tracing::{debug, info};
use uuid::Uuid;

pub struct RedisClient {
    pool: Pool,
    #[allow(dead_code)]
    instance_id: String,
}

impl RedisClient {
    pub async fn new() -> Result<Self> {
        let host = env::var("REDIS_HOST").unwrap_or_else(|_| "localhost".to_string());
        let port = env::var("REDIS_PORT")
            .unwrap_or_else(|_| "6379".to_string())
            .parse::<u16>()
            .map_err(|_| UnifiedMindError::EnvVar("Invalid REDIS_PORT".to_string()))?;
        
        let password = env::var("REDIS_PASSWORD").ok();
        let instance_id = env::var("INSTANCE_ID").unwrap_or_else(|_| "CC".to_string());
        
        let redis_url = if let Some(pwd) = password {
            format!("redis://:{}@{}:{}", pwd, host, port)
        } else {
            format!("redis://{}:{}", host, port)
        };
        
        info!("Connecting to Redis at {}:{}", host, port);
        
        let cfg = Config::from_url(redis_url);
        let pool = cfg.create_pool(Some(Runtime::Tokio1))
            .map_err(|e| UnifiedMindError::Config(format!("Failed to create Redis pool: {}", e)))?;
        
        // Test connection
        let mut conn = pool.get().await?;
        let _: String = redis::cmd("PING").query_async(&mut conn).await?;
        info!("Redis connection established");
        
        Ok(Self { pool, instance_id })
    }
    
    pub async fn get_connection(&self) -> Result<Connection> {
        Ok(self.pool.get().await?)
    }
    
    pub async fn get_cached_result(&self, query_hash: &str) -> Result<Option<CachedResult>> {
        let mut conn = self.get_connection().await?;
        let key = format!("um:cache:{}", query_hash);
        
        let data: Option<String> = conn.get(&key).await?;
        match data {
            Some(json) => {
                debug!("Cache hit for query hash: {}", query_hash);
                Ok(Some(serde_json::from_str(&json)?))
            }
            None => {
                debug!("Cache miss for query hash: {}", query_hash);
                Ok(None)
            }
        }
    }
    
    pub async fn set_cached_result(
        &self,
        query_hash: &str,
        result: &CachedResult,
        ttl_seconds: u64,
    ) -> Result<()> {
        let mut conn = self.get_connection().await?;
        let key = format!("um:cache:{}", query_hash);
        let json = serde_json::to_string(result)?;
        
        conn.set_ex::<_, _, ()>(&key, json, ttl_seconds).await?;
        debug!("Cached result for query hash: {} (TTL: {}s)", query_hash, ttl_seconds);
        Ok(())
    }
    
    pub async fn get_thought_metadata(&self, thought_id: &Uuid) -> Result<Option<ThoughtMetadata>> {
        let mut conn = self.get_connection().await?;
        let key = format!("thought:{}:metadata", thought_id);
        
        let data: Option<String> = conn.get(&key).await?;
        match data {
            Some(json) => Ok(Some(serde_json::from_str(&json)?)),
            None => Ok(None),
        }
    }
    
    pub async fn increment_usage_count(&self, thought_id: &Uuid) -> Result<()> {
        let mut conn = self.get_connection().await?;
        let key = format!("thought:{}:usage", thought_id);
        
        conn.incr::<_, _, ()>(&key, 1).await?;
        conn.expire::<_, ()>(&key, 86400 * 30).await?; // 30 days TTL
        Ok(())
    }
    
    pub async fn get_cached_embedding(&self, text: &str) -> Result<Option<Vec<f32>>> {
        let mut conn = self.get_connection().await?;
        let key = format!("um:embedding:{:x}", md5::compute(text));
        
        let data: Option<String> = conn.get(&key).await?;
        match data {
            Some(json) => {
                debug!("Embedding cache hit for text: {}", text);
                Ok(Some(serde_json::from_str(&json)?))
            }
            None => {
                debug!("Embedding cache miss for text: {}", text);
                Ok(None)
            }
        }
    }
    
    pub async fn set_cached_embedding(
        &self,
        text: &str,
        embedding: &[f32],
        ttl_seconds: u64,
    ) -> Result<()> {
        let mut conn = self.get_connection().await?;
        let key = format!("um:embedding:{:x}", md5::compute(text));
        let json = serde_json::to_string(embedding)?;
        
        conn.set_ex::<_, _, ()>(&key, json, ttl_seconds).await?;
        debug!("Cached embedding for text: {} (TTL: {}s)", text, ttl_seconds);
        Ok(())
    }
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct ThoughtMetadata {
    pub usage_count: u64,
    pub last_accessed: DateTime<Utc>,
    pub access_history: Vec<DateTime<Utc>>,
}
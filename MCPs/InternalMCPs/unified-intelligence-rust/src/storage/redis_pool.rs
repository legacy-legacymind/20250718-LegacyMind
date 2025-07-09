use anyhow::{Context, Result};
use deadpool_redis::{Config, Pool, Runtime};
use redis::AsyncCommands;

// A type alias is simpler and more direct than a custom struct.
pub type RedisPool = Pool;

pub async fn create_pool(redis_url: &str) -> Result<RedisPool> {
    let cfg = Config::from_url(redis_url);
    let pool = cfg.create_pool(Some(Runtime::Tokio1))?;
    
    // Test connection to ensure the pool is valid
    pool.get().await.context("Failed to get initial Redis connection from pool")?;
    
    tracing::info!("Redis connection pool established");
    
    Ok(pool)
}

// The following functions are now standalone and take the pool as an argument.
// This makes them more testable and decoupled.

pub async fn get_json<T: serde::de::DeserializeOwned>(pool: &RedisPool, key: &str) -> Result<Option<T>> {
    let mut conn = pool.get().await.context("Failed to get Redis connection from pool")?;
    let value: Option<String> = conn.get(key).await.with_context(|| format!("Failed to GET key: {}", key))?;
    
    match value {
        Some(json_str) => {
            let parsed = serde_json::from_str(&json_str)
                .with_context(|| format!("Failed to parse JSON for key: {}", key))?;
            Ok(Some(parsed))
        },
        None => Ok(None),
    }
}

pub async fn set_json<T: serde::Serialize>(pool: &RedisPool, key: &str, value: &T) -> Result<()> {
    let json_str = serde_json::to_string(value).context("Failed to serialize value to JSON")?;
    let mut conn = pool.get().await.context("Failed to get Redis connection from pool")?;
    conn.set(key, &json_str).await.with_context(|| format!("Failed to SET key: {}", key))?;
    Ok(())
}
use anyhow::{Context, Result};
use redis::AsyncCommands;
use std::sync::Arc;

use crate::storage::redis_pool::RedisPool;

pub struct SessionResolver {
    redis_pool: Arc<RedisPool>,
}

impl SessionResolver {
    pub fn new(redis_pool: Arc<RedisPool>) -> Self {
        Self { redis_pool }
    }

    pub async fn resolve_instance(&self, session_id: &Option<String>) -> Result<String> {
        if let Some(sid) = session_id {
            let session_key = format!("session:{}", sid);
            let mut conn = self.redis_pool.get().await.context("Failed to get Redis connection")?;
            let instance_id: String = conn.get(&session_key).await.with_context(|| format!("Failed to resolve session: {}", sid))?;
            Ok(instance_id)
        } else {
            // For now, we can default to the instance_id from the config if no session is provided.
            // This part of the logic might need to be revisited depending on how sessions are managed.
            Ok("default".to_string()) // Placeholder
        }
    }
}
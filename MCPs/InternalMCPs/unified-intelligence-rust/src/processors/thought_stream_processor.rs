use anyhow::{anyhow, Context, Result};
use redis::AsyncCommands;
use redis::streams::{StreamReadOptions, StreamReadReply};
use std::sync::Arc;
use tokio::sync::RwLock;
use std::collections::HashMap;
use serde_json;
use tracing::{info, warn, error, debug};

use crate::storage::{redis_pool, RedisPool, Thought};

// ... (structs and traits remain the same) ...
#[async_trait::async_trait]
pub trait ThoughtProcessor: Send + Sync {
    async fn process(&self, thought: &Thought) -> Result<()>;
    fn name(&self) -> &str;
}

pub struct PatternAnalyzer {
    significance_threshold: u8,
}

#[async_trait::async_trait]
impl ThoughtProcessor for PatternAnalyzer {
    async fn process(&self, thought: &Thought) -> Result<()> {
        if thought.significance >= self.significance_threshold {
            info!("High significance thought detected: {} (score: {})", 
                  thought.id, thought.significance);
        }
        Ok(())
    }
    
    fn name(&self) -> &str { "PatternAnalyzer" }
}

pub struct MemoryFormationProcessor {
    redis_pool: Arc<RedisPool>,
}

#[async_trait::async_trait]
impl ThoughtProcessor for MemoryFormationProcessor {
    async fn process(&self, thought: &Thought) -> Result<()> {
        if thought.significance >= 7 {
            debug!("Forming memory from high-significance thought: {}", thought.id);
            
            let memory_key = format!("{}:memories:thoughts:{}", thought.instance_id, thought.id);
            let memory_data = serde_json::json!({
                "thought_id": thought.id, "content": thought.content,
                "significance": thought.significance, "framework": thought.framework,
                "timestamp": thought.timestamp, "tags": thought.tags,
                "processed_at": chrono::Utc::now(),
            });
            
            redis_pool::set_json(&self.redis_pool, &memory_key, &memory_data).await?;
            
            let index_key = format!("{}:memories:index", thought.instance_id);
            let mut conn = self.redis_pool.get().await?;
            let _: () = conn.zadd(&index_key, &thought.id, thought.significance as f64).await?;
        }
        Ok(())
    }
    
    fn name(&self) -> &str { "MemoryFormationProcessor" }
}


/// Processes thoughts from Redis streams in real-time
pub struct ThoughtStreamProcessor {
    redis_pool: Arc<RedisPool>,
    instance_id: String,
    consumer_group: String,
    consumer_name: String,
    processors: Arc<RwLock<HashMap<String, Box<dyn ThoughtProcessor + Send + Sync>>>>,
}


impl ThoughtStreamProcessor {
    pub fn new(redis_pool: Arc<RedisPool>, instance_id: String) -> Self {
        let consumer_group = format!("{}_processors", instance_id);
        let consumer_name = format!("{}_consumer_{}", instance_id, uuid::Uuid::new_v4());
        
        Self {
            redis_pool,
            instance_id,
            consumer_group,
            consumer_name,
            processors: Arc::new(RwLock::new(HashMap::new())),
        }
    }
    
    pub async fn init(&self) -> Result<()> {
        let stream_key = format!("{}:thoughts", self.instance_id);
        let mut conn = self.redis_pool.get().await?;
        
        let result: Result<(), redis::RedisError> = redis::cmd("XGROUP")
            .arg("CREATE").arg(&stream_key).arg(&self.consumer_group)
            .arg("0").arg("MKSTREAM").query_async(&mut conn).await;
            
        if let Err(e) = result {
            if !e.to_string().contains("BUSYGROUP") {
                return Err(anyhow!("Failed to create consumer group: {}", e));
            }
            debug!("Consumer group already exists: {}", self.consumer_group);
        } else {
            info!("Created consumer group: {}", self.consumer_group);
        }
        
        let mut processors = self.processors.write().await;
        processors.insert("pattern_analyzer".to_string(), Box::new(PatternAnalyzer { significance_threshold: 6 }));
        processors.insert("memory_formation".to_string(), Box::new(MemoryFormationProcessor { redis_pool: self.redis_pool.clone() }));
        
        Ok(())
    }
    
    pub async fn start_processing(&self) -> Result<()> {
        let stream_key = format!("{}:thoughts", self.instance_id);
        info!("Starting thought stream processing for instance: {}", self.instance_id);
        
        loop {
            let mut conn = self.redis_pool.get().await?;
            let opts = StreamReadOptions::default().group(&self.consumer_group, &self.consumer_name).block(5000).count(10);
            
            let result: Result<StreamReadReply, _> = conn.xread_options(&[&stream_key], &[">"], &opts).await;
                
            match result {
                Ok(reply) => {
                    for stream_key_reply in reply.keys {
                        for stream_id in stream_key_reply.ids {
                            if let Err(e) = self.process_message(&stream_key_reply.key, &stream_id.id, &stream_id.map).await {
                                error!("Failed to process message {}: {}", stream_id.id, e);
                            }
                        }
                    }
                }
                Err(e) if e.to_string().contains("timed out") => continue,
                Err(e) => {
                    error!("Stream read error: {}", e);
                    tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
                }
            }
        }
    }
    
    async fn process_message(&self, stream_key: &str, message_id: &str, data: &HashMap<String, redis::Value>) -> Result<()> {
        let thought_data = data.get("thought")
            .and_then(|v| if let redis::Value::BulkString(bytes) = v { Some(bytes) } else { None })
            .context("Missing thought data")?;
            
        let thought: Thought = serde_json::from_slice(thought_data)?;
        
        for (name, processor) in self.processors.read().await.iter() {
            if let Err(e) = processor.process(&thought).await {
                warn!("Processor {} failed for thought {}: {}", name, thought.id, e);
            }
        }
        
        let mut conn = self.redis_pool.get().await?;
        let _: () = conn.xack(stream_key, &self.consumer_group, &[message_id]).await?;
        Ok(())
    }
}

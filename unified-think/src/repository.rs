use async_trait::async_trait;
use std::sync::Arc;

use crate::error::Result;
use crate::models::{ThoughtRecord, ChainMetadata};
use crate::redis::RedisManager;
use crate::search_optimization::{SearchCache, OptimizedSearch};

/// Repository trait for thought storage operations
#[async_trait]
pub trait ThoughtRepository: Send + Sync {
    /// Store a thought record
    async fn save_thought(&self, thought: &ThoughtRecord) -> Result<()>;
    
    /// Get a thought by ID
    async fn get_thought(&self, instance: &str, thought_id: &str) -> Result<Option<ThoughtRecord>>;
    
    /// Get thoughts by chain ID
    async fn get_chain_thoughts(&self, instance: &str, chain_id: &str) -> Result<Vec<ThoughtRecord>>;
    
    /// Search thoughts by query
    async fn search_thoughts(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
    ) -> Result<Vec<ThoughtRecord>>;
    
    /// Get all thoughts for an instance
    async fn get_instance_thoughts(&self, instance: &str, limit: usize) -> Result<Vec<ThoughtRecord>>;
    
    /// Create or update chain metadata
    async fn save_chain_metadata(&self, metadata: &ChainMetadata) -> Result<()>;
    
    /// Get chain metadata
    async fn get_chain_metadata(&self, chain_id: &str) -> Result<Option<ChainMetadata>>;
    
    /// Check if chain exists
    async fn chain_exists(&self, chain_id: &str) -> Result<bool>;
}

/// Redis implementation of ThoughtRepository
pub struct RedisThoughtRepository {
    redis: Arc<RedisManager>,
    search_available: Arc<std::sync::atomic::AtomicBool>,
    search_cache: Arc<std::sync::Mutex<SearchCache>>,
}

impl RedisThoughtRepository {
    pub fn new(
        redis: Arc<RedisManager>, 
        search_available: Arc<std::sync::atomic::AtomicBool>,
        search_cache: Arc<std::sync::Mutex<SearchCache>>,
    ) -> Self {
        Self {
            redis,
            search_available,
            search_cache,
        }
    }
    
    fn thought_key(&self, instance: &str, thought_id: &str) -> String {
        format!("thought:{}:{}", instance, thought_id)
    }
    
    fn chain_metadata_key(&self, chain_id: &str) -> String {
        format!("chain:metadata:{}", chain_id)
    }
    
    /// Fallback search implementation when Redis Search is not available
    async fn fallback_search(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
    ) -> Result<Vec<ThoughtRecord>> {
        let pattern = format!("thought:{}:*", instance);
        let keys = self.redis.scan_match(&pattern, 100).await?;
        
        let mut thoughts = Vec::new();
        for key in keys {
            if let Some(thought) = self.redis.json_get::<ThoughtRecord>(&key, "$").await? {
                if thought.thought.to_lowercase().contains(&query.to_lowercase()) {
                    thoughts.push(thought);
                    if thoughts.len() >= limit {
                        break;
                    }
                }
            }
        }
        
        Ok(thoughts)
    }
}

#[async_trait]
impl ThoughtRepository for RedisThoughtRepository {
    async fn save_thought(&self, thought: &ThoughtRecord) -> Result<()> {
        let key = self.thought_key(&thought.instance, &thought.id);
        
        // Store the thought
        self.redis.json_set(&key, "$", thought).await?;
        
        // Add to chain index if part of a chain
        if let Some(chain_id) = &thought.chain_id {
            let chain_key = format!("chain:thoughts:{}", chain_id);
            self.redis.zadd(
                &chain_key,
                &thought.id,
                thought.thought_number as f64,
            ).await?;
        }
        
        Ok(())
    }
    
    async fn get_thought(&self, instance: &str, thought_id: &str) -> Result<Option<ThoughtRecord>> {
        let key = self.thought_key(instance, thought_id);
        self.redis.json_get(&key, "$").await
    }
    
    async fn get_chain_thoughts(&self, instance: &str, chain_id: &str) -> Result<Vec<ThoughtRecord>> {
        let chain_key = format!("chain:thoughts:{}", chain_id);
        let thought_ids = self.redis.zrange(&chain_key, 0, -1).await?;
        
        if thought_ids.is_empty() {
            return Ok(Vec::new());
        }
        
        // Build keys for batch fetch
        let keys: Vec<String> = thought_ids.iter()
            .map(|id| self.thought_key(instance, id))
            .collect();
        
        // Get connection for batch operation
        let mut conn = self.redis.get_pool().get().await
            .map_err(|e| crate::error::UnifiedThinkError::PoolGet(e.to_string()))?;
        
        // Use batch fetch from OptimizedSearch
        let batch_results = OptimizedSearch::batch_fetch_thoughts(&mut conn, &keys).await
            .map_err(|e| crate::error::UnifiedThinkError::Internal(format!("Batch fetch failed: {:?}", e)))?;
        
        // Extract just the thoughts in order
        let thoughts: Vec<ThoughtRecord> = batch_results.into_iter()
            .map(|(_, thought)| thought)
            .collect();
        
        Ok(thoughts)
    }
    
    async fn search_thoughts(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
    ) -> Result<Vec<ThoughtRecord>> {
        // Create cache key
        let cache_key = format!("{}_{}_{}", query, instance, limit);
        
        // Check cache first
        if let Ok(cache) = self.search_cache.lock() {
            if let Some(cached_results) = cache.get(&cache_key) {
                tracing::debug!("Cache hit for search: {}", cache_key);
                return Ok(cached_results.clone());
            }
        }
        
        tracing::debug!("Cache miss for search: {}", cache_key);
        
        // Perform search
        let thoughts = if self.search_available.load(std::sync::atomic::Ordering::SeqCst) {
            let search_query = format!("(@content:{}) (@instance:{{{}}})", query, instance);
            
            match self.redis.search("idx:thoughts", &search_query, limit).await {
                Ok(results) => {
                    let mut thoughts = Vec::new();
                    for (key, _score) in results {
                        if let Some(thought) = self.redis.json_get::<ThoughtRecord>(&key, "$").await? {
                            thoughts.push(thought);
                        }
                    }
                    thoughts
                }
                Err(_) => {
                    // Fall through to scan-based search
                    self.fallback_search(instance, query, limit).await?
                }
            }
        } else {
            // Use fallback search
            self.fallback_search(instance, query, limit).await?
        };
        
        // Store in cache
        if let Ok(mut cache) = self.search_cache.lock() {
            cache.insert(cache_key, thoughts.clone());
        }
        
        Ok(thoughts)
    }
    
    async fn get_instance_thoughts(&self, instance: &str, limit: usize) -> Result<Vec<ThoughtRecord>> {
        let pattern = format!("thought:{}:*", instance);
        let keys = self.redis.scan_match(&pattern, 100).await?;
        
        let mut thoughts = Vec::new();
        for key in keys.into_iter().take(limit) {
            if let Some(thought) = self.redis.json_get::<ThoughtRecord>(&key, "$").await? {
                thoughts.push(thought);
            }
        }
        
        Ok(thoughts)
    }
    
    async fn save_chain_metadata(&self, metadata: &ChainMetadata) -> Result<()> {
        let key = self.chain_metadata_key(&metadata.chain_id);
        self.redis.json_set(&key, "$", metadata).await
    }
    
    async fn get_chain_metadata(&self, chain_id: &str) -> Result<Option<ChainMetadata>> {
        let key = self.chain_metadata_key(chain_id);
        self.redis.json_get(&key, "$").await
    }
    
    async fn chain_exists(&self, chain_id: &str) -> Result<bool> {
        let key = self.chain_metadata_key(chain_id);
        self.redis.exists(&key).await
    }
}
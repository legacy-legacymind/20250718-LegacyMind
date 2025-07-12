use async_trait::async_trait;
use std::sync::Arc;

use crate::error::Result;
use crate::models::{ThoughtRecord, ChainMetadata, Identity};
use crate::redis::RedisManager;
use crate::search_optimization::SearchCache;
use crate::embeddings::EmbeddingGenerator;

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
    
    /// Search thoughts using semantic similarity
    async fn search_thoughts_semantic(
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
    
    // ===== IDENTITY METHODS =====
    
    /// Get identity for instance
    async fn get_identity(&self, identity_key: &str) -> Result<Option<Identity>>;
    
    /// Save identity for instance
    async fn save_identity(&self, identity_key: &str, identity: &Identity) -> Result<()>;
    
    /// Append to JSON array field
    async fn json_array_append(&self, key: &str, path: &str, value: &serde_json::Value) -> Result<()>;
    
    /// Set JSON field
    async fn json_set(&self, key: &str, path: &str, value: &serde_json::Value) -> Result<()>;
    
    /// Get JSON array field
    async fn json_get_array(&self, key: &str, path: &str) -> Result<Option<Vec<serde_json::Value>>>;
    
    /// Delete JSON field
    async fn json_delete(&self, key: &str, path: &str) -> Result<()>;
    
    /// Increment JSON numeric field
    async fn json_increment(&self, key: &str, path: &str, increment: i64) -> Result<()>;
    
    /// Log event to instance stream
    async fn log_event(&self, instance: &str, event_type: &str, fields: Vec<(&str, &str)>) -> Result<()>;
}

/// Redis implementation of ThoughtRepository
pub struct RedisThoughtRepository {
    redis: Arc<RedisManager>,
    search_available: Arc<std::sync::atomic::AtomicBool>,
    search_cache: Arc<std::sync::Mutex<SearchCache>>,
    embedding_generator: Arc<EmbeddingGenerator>,
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
            embedding_generator: Arc::new(EmbeddingGenerator::new()),
        }
    }
    
    fn thought_key(&self, instance: &str, thought_id: &str) -> String {
        format!("{}/Thoughts/{}", instance, thought_id)
    }
    
    fn chain_metadata_key(&self, chain_id: &str) -> String {
        format!("Chains/metadata/{}", chain_id)
    }
    
    /// Fallback search implementation when Redis Search is not available
    async fn fallback_search(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
    ) -> Result<Vec<ThoughtRecord>> {
        let pattern = format!("{}/Thoughts/*", instance);
        let keys = self.redis.scan_match(&pattern, 100).await?;
        
        let mut thoughts = Vec::new();
        for key in keys {
            // Thoughts are stored as regular strings, not RedisJSON
            if let Some(json_str) = self.redis.get(&key).await? {
                if let Ok(thought) = serde_json::from_str::<ThoughtRecord>(&json_str) {
                    if thought.thought.to_lowercase().contains(&query.to_lowercase()) {
                        thoughts.push(thought);
                        if thoughts.len() >= limit {
                            break;
                        }
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
        let thought_key = self.thought_key(&thought.instance, &thought.id);
        let bloom_key = format!("{}/bloom/thoughts", thought.instance);
        let ts_key = format!("{}/metrics/thought_count", thought.instance);
        let chain_key = thought.chain_id.as_ref()
            .map(|id| format!("{}/chains/{}", thought.instance, id));
        
        // Serialize thought to JSON
        let thought_json = serde_json::to_string(thought)
            .map_err(|e| crate::error::UnifiedThinkError::Json(e))?;
        
        // Parse timestamp from ISO string to epoch seconds
        let timestamp = chrono::DateTime::parse_from_rfc3339(&thought.timestamp)
            .map(|dt| dt.timestamp())
            .unwrap_or_else(|_| {
                // Fallback to current time if parsing fails
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs() as i64
            });
        
        // Use atomic script for all operations
        let success = self.redis.store_thought_atomic(
            &thought_key,
            &bloom_key,
            &ts_key,
            chain_key.as_deref(),
            &thought_json,
            &thought.id,
            timestamp,
            thought.chain_id.as_deref(),
        ).await?;
        
        if !success {
            tracing::warn!("Duplicate thought detected for instance {}: {}", 
                thought.instance, 
                thought.thought.chars().take(50).collect::<String>()
            );
            // In production, you might want to return an error here
            // For now, we'll log and continue
        } else {
            // Generate and add vector embedding for the thought
            let embedding = self.embedding_generator.generate(&thought.thought);
            if let Err(e) = self.redis.add_thought_vector(&thought.instance, &thought.id, &embedding).await {
                tracing::debug!("Failed to add thought vector: {}. Semantic search may not be available.", e);
            }
            
            // Log thought created event
            let thought_preview = thought.thought.chars().take(100).collect::<String>();
            let _ = self.redis.log_thought_event(
                &thought.instance,
                "thought_created",
                &thought.id,
                thought.chain_id.as_deref(),
                Some(vec![
                    ("thought_preview", &thought_preview),
                    ("thought_number", &thought.thought_number.to_string()),
                ]),
            ).await;
        }
        
        Ok(())
    }
    
    async fn get_thought(&self, instance: &str, thought_id: &str) -> Result<Option<ThoughtRecord>> {
        let thought_key = self.thought_key(instance, thought_id);
        let access_count_key = format!("{}/metrics/access_count", instance);
        let last_access_key = format!("{}/last_access", thought_key);
        
        // Get current timestamp
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64;
        
        // Use atomic script to get thought and update metrics
        let result = self.redis.get_thought_atomic(
            &thought_key,
            &access_count_key,
            &last_access_key,
            timestamp,
        ).await?;
        
        match result {
            Some(json) => {
                let thought: ThoughtRecord = serde_json::from_str(&json)
                    .map_err(|e| crate::error::UnifiedThinkError::Json(e))?;
                
                // Log thought accessed event
                let _ = self.redis.log_thought_event(
                    instance,
                    "thought_accessed",
                    thought_id,
                    thought.chain_id.as_deref(),
                    None,
                ).await;
                
                Ok(Some(thought))
            }
            None => Ok(None),
        }
    }
    
    async fn get_chain_thoughts(&self, _instance: &str, chain_id: &str) -> Result<Vec<ThoughtRecord>> {
        let chain_key = format!("{}/chains/{}", _instance, chain_id);
        
        // Use atomic script to get all thoughts in chain
        let json_results = self.redis.get_chain_thoughts_atomic(&chain_key, _instance).await?;
        
        if json_results.is_empty() {
            return Ok(Vec::new());
        }
        
        // Parse all JSON results
        let mut thoughts = Vec::new();
        for json in json_results {
            let thought: ThoughtRecord = serde_json::from_str(&json)
                .map_err(|e| crate::error::UnifiedThinkError::Json(e))?;
            thoughts.push(thought);
        }
        
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
            
            match self.redis.search_with_timeout("idx:thoughts", &search_query, limit).await {
                Ok(results) => {
                    let mut thoughts = Vec::new();
                    for (key, _score) in results {
                        // Thoughts are stored as regular strings, not RedisJSON
                        if let Some(json_str) = self.redis.get(&key).await? {
                            if let Ok(thought) = serde_json::from_str::<ThoughtRecord>(&json_str) {
                                thoughts.push(thought);
                            }
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
    
    async fn search_thoughts_semantic(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
    ) -> Result<Vec<ThoughtRecord>> {
        // Generate query embedding
        let query_embedding = self.embedding_generator.generate_query_embedding(query);
        
        // Search for similar thought vectors
        let similar_thoughts = self.redis.search_similar_thoughts(instance, &query_embedding, limit).await?;
        
        if similar_thoughts.is_empty() {
            tracing::debug!("No similar thoughts found using vector search for instance {}", instance);
            return Ok(Vec::new());
        }
        
        // Retrieve the actual thought records
        let mut thoughts = Vec::new();
        for (thought_id, similarity) in similar_thoughts {
            if let Some(thought) = self.get_thought(instance, &thought_id).await? {
                thoughts.push(thought);
                tracing::debug!("Found similar thought {} with similarity score {:.3}", thought_id, similarity);
            }
        }
        
        Ok(thoughts)
    }
    
    async fn get_instance_thoughts(&self, instance: &str, limit: usize) -> Result<Vec<ThoughtRecord>> {
        let pattern = format!("{}/Thoughts/*", instance);
        let keys = self.redis.scan_match(&pattern, 100).await?;
        
        let mut thoughts = Vec::new();
        for key in keys.into_iter().take(limit) {
            // Thoughts are stored as regular strings, not RedisJSON
            if let Some(json_str) = self.redis.get(&key).await? {
                if let Ok(thought) = serde_json::from_str::<ThoughtRecord>(&json_str) {
                    thoughts.push(thought);
                }
            }
        }
        
        Ok(thoughts)
    }
    
    async fn save_chain_metadata(&self, metadata: &ChainMetadata) -> Result<()> {
        let key = self.chain_metadata_key(&metadata.chain_id);
        
        // Check if chain already exists
        let is_new_chain = !self.redis.exists(&key).await?;
        
        // Save the metadata
        self.redis.json_set_with_timeout(&key, "$", metadata).await?;
        
        // Log appropriate event
        let event_type = if is_new_chain { "chain_created" } else { "chain_updated" };
        let _ = self.redis.log_event(
            &metadata.instance,
            event_type,
            vec![
                ("chain_id", &metadata.chain_id),
                ("thought_count", &metadata.thought_count.to_string()),
                ("created_at", &metadata.created_at),
            ],
        ).await;
        
        Ok(())
    }
    
    async fn get_chain_metadata(&self, chain_id: &str) -> Result<Option<ChainMetadata>> {
        let key = self.chain_metadata_key(chain_id);
        self.redis.json_get_with_timeout(&key, "$").await
    }
    
    async fn chain_exists(&self, chain_id: &str) -> Result<bool> {
        let key = self.chain_metadata_key(chain_id);
        self.redis.exists(&key).await
    }
    
    // ===== IDENTITY IMPLEMENTATIONS =====
    
    async fn get_identity(&self, identity_key: &str) -> Result<Option<Identity>> {
        self.redis.json_get_with_timeout(identity_key, "$").await
    }
    
    async fn save_identity(&self, identity_key: &str, identity: &Identity) -> Result<()> {
        self.redis.json_set_with_timeout(identity_key, "$", identity).await
    }
    
    async fn json_array_append(&self, key: &str, path: &str, value: &serde_json::Value) -> Result<()> {
        use redis::JsonAsyncCommands;
        let mut conn = self.redis.get_connection().await?;
        
        // Use Redis JSON.ARRAPPEND command
        let _: () = conn.json_arr_append(key, path, value).await
            .map_err(|e| crate::error::UnifiedThinkError::Redis(e))?;
        
        Ok(())
    }
    
    async fn json_set(&self, key: &str, path: &str, value: &serde_json::Value) -> Result<()> {
        use redis::JsonAsyncCommands;
        let mut conn = self.redis.get_connection().await?;
        
        // Use Redis JSON.SET command
        let _: () = conn.json_set(key, path, value).await
            .map_err(|e| crate::error::UnifiedThinkError::Redis(e))?;
        
        Ok(())
    }
    
    async fn json_get_array(&self, key: &str, path: &str) -> Result<Option<Vec<serde_json::Value>>> {
        use redis::JsonAsyncCommands;
        let mut conn = self.redis.get_connection().await?;
        
        // Use Redis JSON.GET command to get array
        let result: redis::RedisResult<Option<String>> = conn.json_get(key, path).await;
        
        match result {
            Ok(Some(json_str)) => {
                let parsed: serde_json::Value = serde_json::from_str(&json_str)
                    .map_err(|e| crate::error::UnifiedThinkError::Json(e))?;
                
                if let serde_json::Value::Array(arr) = parsed {
                    Ok(Some(arr))
                } else {
                    Ok(None)
                }
            }
            Ok(None) => Ok(None),
            Err(e) => Err(crate::error::UnifiedThinkError::Redis(e)),
        }
    }
    
    async fn json_delete(&self, key: &str, path: &str) -> Result<()> {
        use redis::JsonAsyncCommands;
        let mut conn = self.redis.get_connection().await?;
        
        // Use Redis JSON.DEL command
        let _: i64 = conn.json_del(key, path).await
            .map_err(|e| crate::error::UnifiedThinkError::Redis(e))?;
        
        Ok(())
    }
    
    async fn json_increment(&self, key: &str, path: &str, increment: i64) -> Result<()> {
        use redis::JsonAsyncCommands;
        let mut conn = self.redis.get_connection().await?;
        
        // Use Redis JSON.NUMINCRBY command
        let _: () = conn.json_num_incr_by(key, path, increment).await
            .map_err(|e| crate::error::UnifiedThinkError::Redis(e))?;
        
        Ok(())
    }
    
    async fn log_event(&self, instance: &str, event_type: &str, fields: Vec<(&str, &str)>) -> Result<()> {
        // Delegate to redis manager log_event method and ignore the returned event ID
        let _ = self.redis.log_event(instance, event_type, fields).await?;
        Ok(())
    }
}
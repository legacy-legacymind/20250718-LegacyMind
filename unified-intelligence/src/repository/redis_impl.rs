use async_trait::async_trait;
use std::sync::Arc;

use crate::error::Result;
use crate::models::{ThoughtRecord, ChainMetadata, Identity, ThoughtMetadata, UiRecallFeedbackParams};
use crate::redis::RedisManager;
use crate::search_optimization::SearchCache;
use crate::redisvl_service::RedisVLService;
use crate::identity_documents::IdentityDocument;
use super::*;

/// Redis implementation of all repository traits
pub struct RedisRepository {
    redis: Arc<RedisManager>,
    search_available: Arc<std::sync::atomic::AtomicBool>,
    search_cache: Arc<std::sync::Mutex<SearchCache>>,
    vector_service: Arc<RedisVLService>,
}

impl RedisRepository {
    pub fn new(
        redis: Arc<RedisManager>, 
        search_available: Arc<std::sync::atomic::AtomicBool>,
        search_cache: Arc<std::sync::Mutex<SearchCache>>,
        instance_id: String,
    ) -> Self {
        Self {
            redis: redis.clone(),
            search_available,
            search_cache,
            vector_service: Arc::new(RedisVLService::new(instance_id, redis)),
        }
    }
    
    fn thought_key(&self, instance: &str, thought_id: &str) -> String {
        format!("{}:Thoughts:{}", instance, thought_id)
    }
    
    fn chain_metadata_key(&self, chain_id: &str) -> String {
        format!("Chains:metadata:{}", chain_id)
    }
    
    /// Fallback search implementation when Redis Search is not available
    async fn fallback_search(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
    ) -> Result<Vec<ThoughtRecord>> {
        let pattern = format!("{}:Thoughts:*", instance);
        let keys = self.redis.scan_match(&pattern, 100).await?;
        
        let mut thoughts = Vec::new();
        for key in keys {
            // Try to get as JSON first, fallback to string
            let json_str = match self.redis.json_get::<serde_json::Value>(&key, ".").await {
                Ok(Some(json_val)) => {
                    // Got JSON value, convert to string
                    json_val.to_string()
                }
                _ => {
                    // Fallback to regular string get
                    match self.redis.get(&key).await? {
                        Some(s) => s,
                        None => continue,
                    }
                }
            };
            
            if let Ok(thought) = serde_json::from_str::<ThoughtRecord>(&json_str) {
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
    
    async fn fallback_search_global(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<ThoughtRecord>> {
        // Search across all instances using wildcard pattern
        let pattern = "*:Thoughts:*";
        let keys = self.redis.scan_match(&pattern, 200).await?; // Get more keys since we're searching globally
        
        let mut thoughts = Vec::new();
        for key in keys {
            // Try to get as JSON first, fallback to string
            let json_str = match self.redis.json_get::<serde_json::Value>(&key, ".").await {
                Ok(Some(json_val)) => json_val.to_string(),
                _ => {
                    // Fallback to regular string get
                    match self.redis.get(&key).await? {
                        Some(s) => s,
                        None => continue,
                    }
                }
            };
            
            if let Ok(thought) = serde_json::from_str::<ThoughtRecord>(&json_str) {
                if thought.thought.to_lowercase().contains(&query.to_lowercase()) {
                    thoughts.push(thought);
                    if thoughts.len() >= limit {
                        break;
                    }
                }
            }
        }
        
        // Sort by timestamp (most recent first)
        thoughts.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
        
        Ok(thoughts)
    }
    
    // Helper method to apply metadata filters
    async fn apply_metadata_filters(
        &self,
        thoughts: &mut Vec<ThoughtRecord>,
        thought_ids_filter: Option<Vec<String>>,
        min_importance: Option<i32>,
        min_relevance: Option<i32>,
        category_filter: Option<String>,
        instance: &str,
    ) -> Result<()> {
        if thought_ids_filter.is_none() && min_importance.is_none() && 
           min_relevance.is_none() && category_filter.is_none() {
            return Ok(()); // No filters to apply
        }
        
        let mut filtered_thoughts = Vec::new();
        
        for thought in thoughts.drain(..) {
            // Apply tag filter first (most selective)
            if let Some(ref allowed_ids) = thought_ids_filter {
                if !allowed_ids.contains(&thought.id) {
                    continue;
                }
            }
            
            // Check metadata filters if any are specified
            if min_importance.is_some() || min_relevance.is_some() || category_filter.is_some() {
                if let Some(metadata) = self.get_thought_metadata(instance, &thought.id).await? {
                    // Apply importance filter
                    if let Some(min_imp) = min_importance {
                        if metadata.importance.map_or(true, |imp| imp < min_imp) {
                            continue;
                        }
                    }
                    
                    // Apply relevance filter
                    if let Some(min_rel) = min_relevance {
                        if metadata.relevance.map_or(true, |rel| rel < min_rel) {
                            continue;
                        }
                    }
                    
                    // Apply category filter
                    if let Some(ref required_category) = category_filter {
                        if metadata.category.as_ref() != Some(required_category) {
                            continue;
                        }
                    }
                }
            }
            
            filtered_thoughts.push(thought);
        }
        
        *thoughts = filtered_thoughts;
        Ok(())
    }
    
    // Helper method for global metadata filtering
    async fn apply_metadata_filters_global(
        &self,
        thoughts: &mut Vec<ThoughtRecord>,
        tags_filter: Option<Vec<String>>,
        min_importance: Option<i32>,
        min_relevance: Option<i32>,
        category_filter: Option<String>,
    ) -> Result<()> {
        if tags_filter.is_none() && min_importance.is_none() && 
           min_relevance.is_none() && category_filter.is_none() {
            return Ok(()); // No filters to apply
        }
        
        let mut filtered_thoughts = Vec::new();
        
        for thought in thoughts.drain(..) {
            // For global search with tag filtering, check each thought's instance tags
            if let Some(ref required_tags) = tags_filter {
                let thought_tags = self.get_thoughts_by_tags(&thought.instance, required_tags).await?;
                if !thought_tags.contains(&thought.id) {
                    continue;
                }
            }
            
            // Apply other metadata filters
            if min_importance.is_some() || min_relevance.is_some() || category_filter.is_some() {
                if let Some(metadata) = self.get_thought_metadata(&thought.instance, &thought.id).await? {
                    if let Some(min_imp) = min_importance {
                        if metadata.importance.map_or(true, |imp| imp < min_imp) {
                            continue;
                        }
                    }
                    
                    if let Some(min_rel) = min_relevance {
                        if metadata.relevance.map_or(true, |rel| rel < min_rel) {
                            continue;
                        }
                    }
                    
                    if let Some(ref required_category) = category_filter {
                        if metadata.category.as_ref() != Some(required_category) {
                            continue;
                        }
                    }
                }
            }
            
            filtered_thoughts.push(thought);
        }
        
        *thoughts = filtered_thoughts;
        Ok(())
    }
}

// ===== THOUGHT STORAGE IMPLEMENTATION =====
#[async_trait]
impl ThoughtStorage for RedisRepository {
    async fn save_thought(&self, thought: &ThoughtRecord) -> Result<()> {
        let thought_key = self.thought_key(&thought.instance, &thought.id);
        let bloom_key = format!("{}:bloom:thoughts", thought.instance);
        let ts_key = format!("{}:metrics:thought_count", thought.instance);
        let chain_key = thought.chain_id.as_ref()
            .map(|id| format!("{}:chains:{}", thought.instance, id));
        
        // Serialize thought to JSON
        let thought_json = serde_json::to_string(thought)
            .map_err(|e| crate::error::UnifiedIntelligenceError::Json(e))?;
        
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
        } else {
            // Publish thought_created event to Redis Streams for background embedding processing
            let timestamp = chrono::DateTime::parse_from_rfc3339(&thought.timestamp)
                .map(|dt| dt.timestamp())
                .unwrap_or_else(|_| {
                    std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap()
                        .as_secs() as i64
                });
            
            // Publish to Redis Streams for background embedding service
            let event_data = serde_json::json!({
                "type": "thought_created",
                "thought_id": thought.id,
                "instance": thought.instance,
                "timestamp": timestamp,
                "content_preview": thought.thought.chars().take(100).collect::<String>()
            });
            
            if let Err(e) = self.redis.publish_stream_event(&thought.instance, "thought_created", &event_data).await {
                tracing::debug!("Failed to publish thought_created event: {}. Background embedding may not be triggered.", e);
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
        let access_count_key = format!("{}:metrics:access_count", instance);
        let last_access_key = format!("{}:last_access", thought_key);
        
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
                    .map_err(|e| crate::error::UnifiedIntelligenceError::Json(e))?;
                
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
        let chain_key = format!("{}:chains:{}", _instance, chain_id);
        
        // Use atomic script to get all thoughts in chain
        let json_results = self.redis.get_chain_thoughts_atomic(&chain_key, _instance).await?;
        
        if json_results.is_empty() {
            return Ok(Vec::new());
        }
        
        // Parse all JSON results
        let mut thoughts = Vec::new();
        for json in json_results {
            let thought: ThoughtRecord = serde_json::from_str(&json)
                .map_err(|e| crate::error::UnifiedIntelligenceError::Json(e))?;
            thoughts.push(thought);
        }
        
        Ok(thoughts)
    }
    
    async fn get_instance_thoughts(&self, instance: &str, limit: usize) -> Result<Vec<ThoughtRecord>> {
        let pattern = format!("{}:Thoughts:*", instance);
        let keys = self.redis.scan_match(&pattern, 100).await?;
        
        let mut thoughts = Vec::new();
        for key in keys.into_iter().take(limit) {
            // Try to get as JSON first, fallback to string
            let json_str = match self.redis.json_get::<serde_json::Value>(&key, ".").await {
                Ok(Some(json_val)) => {
                    // Got JSON value, convert to string
                    json_val.to_string()
                }
                _ => {
                    // Fallback to regular string get
                    match self.redis.get(&key).await? {
                        Some(s) => s,
                        None => continue,
                    }
                }
            };
            
            if let Ok(thought) = serde_json::from_str::<ThoughtRecord>(&json_str) {
                thoughts.push(thought);
            }
        }
        
        Ok(thoughts)
    }
    
    async fn get_all_thoughts(&self, limit: usize) -> Result<Vec<ThoughtRecord>> {
        // Search for all thought keys across all instances
        let pattern = "*:Thoughts:*";
        let keys = self.redis.scan_match(pattern, limit * 2).await?; // Get more keys to ensure we have enough
        
        let mut thoughts = Vec::new();
        for key in keys.into_iter().take(limit) {
            // Try to get as JSON first, fallback to string
            let json_str = match self.redis.json_get::<serde_json::Value>(&key, ".").await {
                Ok(Some(json_val)) => json_val.to_string(),
                _ => {
                    // Fallback to regular string get
                    match self.redis.get(&key).await? {
                        Some(s) => s,
                        None => continue,
                    }
                }
            };
            
            if let Ok(thought) = serde_json::from_str::<ThoughtRecord>(&json_str) {
                thoughts.push(thought);
            }
        }
        
        // Sort by timestamp (most recent first)
        thoughts.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
        
        Ok(thoughts)
    }
}

// ===== THOUGHT SEARCH IMPLEMENTATION =====
#[async_trait]
impl ThoughtSearch for RedisRepository {
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
                        // Try to get as JSON first, fallback to string
                        let json_str = match self.redis.json_get::<serde_json::Value>(&key, ".").await {
                            Ok(Some(json_val)) => {
                                // Got JSON value, convert to string
                                json_val.to_string()
                            }
                            _ => {
                                // Fallback to regular string get
                                match self.redis.get(&key).await? {
                                    Some(s) => s,
                                    None => continue,
                                }
                            }
                        };
                        
                        if let Ok(thought) = serde_json::from_str::<ThoughtRecord>(&json_str) {
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
    
    async fn search_thoughts_semantic(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
        threshold: f32,
    ) -> Result<Vec<ThoughtRecord>> {
        // Use RedisVL for semantic search with specified threshold
        tracing::info!("Repository semantic search - instance: {}, query: {}, limit: {}, threshold: {}", instance, query, limit, threshold);
        self.vector_service.semantic_search(query, limit, threshold).await
    }
    
    async fn search_thoughts_global(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<ThoughtRecord>> {
        // Create cache key for global search
        let cache_key = format!("global_{}_{}", query, limit);
        
        // Check cache first
        if let Ok(cache) = self.search_cache.lock() {
            if let Some(cached_results) = cache.get(&cache_key) {
                tracing::debug!("Cache hit for global search: {}", cache_key);
                return Ok(cached_results.clone());
            }
        }
        
        tracing::debug!("Cache miss for global search: {}", cache_key);
        
        // Perform search across all instances
        let thoughts = if self.search_available.load(std::sync::atomic::Ordering::SeqCst) {
            // Search without instance filter to get results from all instances
            let search_query = format!("(@content:{})", query);
            
            match self.redis.search_with_timeout("idx:thoughts", &search_query, limit).await {
                Ok(results) => {
                    tracing::info!("Global text search found {} results", results.len());
                    let mut thoughts = Vec::new();
                    for (key, _score) in results {
                        // Try to get as JSON first, fallback to string
                        let json_str = match self.redis.json_get::<serde_json::Value>(&key, ".").await {
                            Ok(Some(json_val)) => json_val.to_string(),
                            _ => {
                                // Fallback to regular string get
                                match self.redis.get(&key).await? {
                                    Some(s) => s,
                                    None => continue,
                                }
                            }
                        };
                        
                        if let Ok(thought) = serde_json::from_str::<ThoughtRecord>(&json_str) {
                            thoughts.push(thought);
                        }
                    }
                    thoughts
                }
                Err(e) => {
                    tracing::warn!("Global Redis search failed: {}, falling back to scan", e);
                    self.fallback_search_global(query, limit).await?
                }
            }
        } else {
            self.fallback_search_global(query, limit).await?
        };
        
        // Cache results
        if let Ok(mut cache) = self.search_cache.lock() {
            cache.insert(cache_key, thoughts.clone());
        }
        
        Ok(thoughts)
    }
    
    async fn search_thoughts_semantic_global(
        &self,
        query: &str,
        limit: usize,
        threshold: f32,
    ) -> Result<Vec<ThoughtRecord>> {
        tracing::info!("Global semantic search - query: '{}', limit: {}, threshold: {}", query, limit, threshold);
        
        // Use RedisVL service but with wildcard instance pattern
        let redisvl_service = RedisVLService::new("*".to_string(), self.redis.clone());
        redisvl_service.semantic_search(query, limit, threshold).await
    }
    
    async fn generate_search_id(&self) -> Result<String> {
        // Generate unique search ID using timestamp + UUID
        let timestamp = chrono::Utc::now().timestamp();
        let uuid = uuid::Uuid::new_v4().to_string()[..8].to_string(); // Short UUID
        Ok(format!("search_{}_{}", timestamp, uuid))
    }
}

// ===== ENHANCED SEARCH IMPLEMENTATION =====
#[async_trait]
impl EnhancedSearch for RedisRepository {
    async fn search_thoughts_semantic_enhanced(
        &self,
        instance: &str,
        query: &str,
        limit: usize,
        threshold: f32,
        tags_filter: Option<Vec<String>>,
        min_importance: Option<i32>,
        min_relevance: Option<i32>,
        category_filter: Option<String>,
    ) -> Result<Vec<ThoughtRecord>> {
        // First apply tag filtering if specified
        let thought_ids_filter = if let Some(tags) = tags_filter {
            Some(self.get_thoughts_by_tags(instance, &tags).await?)
        } else {
            None
        };
        
        // Get base semantic search results
        let mut thoughts = self.search_thoughts_semantic(instance, query, limit * 2, threshold).await?;
        
        // Apply metadata filtering
        self.apply_metadata_filters(
            &mut thoughts,
            thought_ids_filter,
            min_importance,
            min_relevance,
            category_filter,
            instance,
        ).await?;
        
        // Limit results and return
        thoughts.truncate(limit);
        Ok(thoughts)
    }
    
    async fn search_thoughts_semantic_global_enhanced(
        &self,
        query: &str,
        limit: usize,
        threshold: f32,
        tags_filter: Option<Vec<String>>,
        min_importance: Option<i32>,
        min_relevance: Option<i32>,
        category_filter: Option<String>,
    ) -> Result<Vec<ThoughtRecord>> {
        // For global search, we need to handle tag filtering differently
        // since tags are instance-specific. For now, get all results and filter.
        let mut thoughts = self.search_thoughts_semantic_global(query, limit * 2, threshold).await?;
        
        // Apply metadata filtering (will need to check each thought's instance for tags)
        self.apply_metadata_filters_global(
            &mut thoughts,
            tags_filter,
            min_importance,
            min_relevance,
            category_filter,
        ).await?;
        
        thoughts.truncate(limit);
        Ok(thoughts)
    }
    
    async fn get_thoughts_by_tags(&self, instance: &str, tags: &[String]) -> Result<Vec<String>> {
        if tags.is_empty() {
            return Ok(Vec::new());
        }
        
        // Build tag set keys
        let tag_keys: Vec<String> = tags.iter()
            .map(|tag| format!("{}:tags:{}", instance, tag))
            .collect();
        
        // Get intersection of all tag sets
        let thought_ids = self.redis.sinter(&tag_keys).await?;
        
        tracing::debug!("Tag intersection for {} tags in instance {}: {} thoughts", 
            tags.len(), instance, thought_ids.len());
        
        Ok(thought_ids)
    }
}

// ===== CHAIN OPERATIONS IMPLEMENTATION =====
#[async_trait]
impl ChainOperations for RedisRepository {
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
    
    
    async fn chain_exists(&self, chain_id: &str) -> Result<bool> {
        let key = self.chain_metadata_key(chain_id);
        self.redis.exists(&key).await
    }
}

// ===== FEEDBACK OPERATIONS IMPLEMENTATION =====
#[async_trait]
impl FeedbackOperations for RedisRepository {
    async fn save_thought_metadata(&self, metadata: &ThoughtMetadata) -> Result<()> {
        let key = format!("{}:thought_meta:{}", metadata.instance, metadata.thought_id);
        
        // Store metadata as JSON
        let metadata_json = serde_json::to_string(metadata)
            .map_err(|e| crate::error::UnifiedIntelligenceError::Json(e))?;
        
        self.redis.json_set(&key, ".", &serde_json::from_str::<serde_json::Value>(&metadata_json)?).await?;
        
        // Build tag indexes if tags are provided
        if let Some(ref tags) = metadata.tags {
            for tag in tags {
                let tag_key = format!("{}:tags:{}", metadata.instance, tag);
                self.redis.sadd(&tag_key, &metadata.thought_id).await?;
            }
        }
        
        tracing::debug!("Saved metadata for thought {} in instance {}", metadata.thought_id, metadata.instance);
        Ok(())
    }
    
    async fn get_thought_metadata(&self, instance: &str, thought_id: &str) -> Result<Option<ThoughtMetadata>> {
        let key = format!("{}:thought_meta:{}", instance, thought_id);
        
        match self.redis.json_get::<serde_json::Value>(&key, ".").await? {
            Some(json_val) => {
                let metadata = serde_json::from_value::<ThoughtMetadata>(json_val)
                    .map_err(|e| crate::error::UnifiedIntelligenceError::Json(e))?;
                Ok(Some(metadata))
            }
            None => Ok(None),
        }
    }
    
    async fn record_feedback(&self, feedback: &UiRecallFeedbackParams, instance: &str) -> Result<()> {
        // Store feedback event in Redis Stream for background processing
        let feedback_event = serde_json::json!({
            "event_type": "feedback_provided",
            "search_id": feedback.search_id,
            "thought_id": feedback.thought_id,
            "instance": instance,
            "action": feedback.action,
            "dwell_time": feedback.dwell_time,
            "relevance_rating": feedback.relevance_rating,
            "timestamp": chrono::Utc::now().to_rfc3339(),
        });
        
        self.publish_feedback_event(&feedback_event).await?;
        
        // Update boost score immediately (Phase 3 enhancement)
        let new_score = self.update_boost_score(
            instance,
            &feedback.thought_id,
            &feedback.action,
            feedback.relevance_rating,
            feedback.dwell_time,
        ).await?;
        
        tracing::info!("Recorded feedback for search {} thought {} action {} - new boost score: {}", 
            feedback.search_id, feedback.thought_id, feedback.action, new_score);
        
        Ok(())
    }
    
    async fn update_boost_score(&self, instance: &str, thought_id: &str, feedback_action: &str, relevance_rating: Option<i32>, dwell_time: Option<i32>) -> Result<f64> {
        let boost_key = format!("{}:boost_scores", instance);
        
        // Calculate boost increment based on feedback action
        let mut base_increment = match feedback_action {
            "helpful" => 2.0,
            "used" => 1.5,
            "viewed" => {
                // Award viewing boost based on dwell time
                if let Some(dwell) = dwell_time {
                    if dwell >= 30 { 0.5 } else if dwell >= 15 { 0.3 } else { 0.1 }
                } else { 0.1 }
            },
            "irrelevant" => -1.0,
            _ => 0.0,
        };
        
        // Apply relevance rating multiplier if provided
        if let Some(rating) = relevance_rating {
            let multiplier = rating as f64 / 10.0; // Scale 1-10 to 0.1-1.0
            base_increment *= multiplier;
        }
        
        // Increment the boost score in Redis sorted set
        let new_score = self.redis.zincrby(&boost_key, thought_id, base_increment).await?;
        
        tracing::info!("Updated boost score for thought {} in instance {}: {} (increment: {})", 
            thought_id, instance, new_score, base_increment);
        
        Ok(new_score)
    }
    
    
    async fn apply_boost_scores(&self, instance: &str, thoughts: &mut Vec<ThoughtRecord>) -> Result<()> {
        if thoughts.is_empty() {
            return Ok(());
        }
        
        let boost_key = format!("{}:boost_scores", instance);
        
        // Get boost scores for all thoughts
        for thought in thoughts.iter_mut() {
            let boost_score = self.redis.zscore(&boost_key, &thought.id).await?.unwrap_or(0.0);
            
            // Apply boost to similarity score (if present) or create composite score
            if let Some(sim_score) = thought.similarity {
                // Combine semantic similarity + boost: similarity gets 90% weight, boost gets 10%
                let boosted_score = sim_score + (boost_score as f32 * 0.1);
                thought.similarity = Some(boosted_score);
            } else {
                // For non-semantic searches, use boost score directly
                thought.similarity = Some(boost_score as f32);
            }
        }
        
        // Re-sort by the new boosted scores (highest first)
        thoughts.sort_by(|a, b| {
            let score_a = a.similarity.unwrap_or(0.0);
            let score_b = b.similarity.unwrap_or(0.0);
            score_b.partial_cmp(&score_a).unwrap_or(std::cmp::Ordering::Equal)
        });
        
        tracing::debug!("Applied boost scores to {} thoughts in instance {}", thoughts.len(), instance);
        Ok(())
    }
}

// ===== IDENTITY OPERATIONS IMPLEMENTATION =====
#[async_trait]
impl IdentityOperations for RedisRepository {
    async fn get_identity(&self, identity_key: &str) -> Result<Option<Identity>> {
        self.redis.json_get_with_timeout(identity_key, "$").await
    }
    
}

// ===== IDENTITY DOCUMENT OPERATIONS IMPLEMENTATION =====
#[async_trait]
impl IdentityDocumentOperations for RedisRepository {
    async fn get_identity_documents_by_field(&self, instance_id: &str, field_type: &str) -> Result<Vec<IdentityDocument>> {
        let pattern = format!("{}:identity:{}:*", instance_id, field_type);
        let keys: Vec<String> = self.redis.keys(&pattern).await?;
        
        let mut documents = Vec::new();
        
        for key in keys {
            if let Some(value) = self.redis.json_get(&key, ".").await? {
                let doc: IdentityDocument = serde_json::from_value(value)?;
                documents.push(doc);
            }
        }
        
        // Sort by creation date (newest first)
        documents.sort_by(|a, b| b.created_at.cmp(&a.created_at));
        
        Ok(documents)
    }
    
    async fn save_identity_document(&self, document: &IdentityDocument) -> Result<()> {
        let key = document.redis_key();
        let value = serde_json::to_value(document)?;
        
        // Save the document
        self.redis.json_set(&key, ".", &value).await?;
        
        // Log the event
        self.log_event(
            &document.instance,
            "identity_document_saved",
            vec![
                ("field_type", &document.field_type),
                ("document_id", &document.id),
            ],
        ).await?;
        
        Ok(())
    }
    
    async fn delete_identity_document(&self, instance_id: &str, field_type: &str, document_id: &str) -> Result<()> {
        let key = format!("{}:identity:{}:{}", instance_id, field_type, document_id);
        
        // Delete the document
        self.redis.json_del(&key, ".").await?;
        
        // Log the event
        self.log_event(
            instance_id,
            "identity_document_deleted",
            vec![
                ("field_type", field_type),
                ("document_id", document_id),
            ],
        ).await?;
        
        Ok(())
    }
    
    async fn get_all_identity_documents(&self, instance_id: &str) -> Result<Vec<IdentityDocument>> {
        let pattern = format!("{}:identity:*:*", instance_id);
        tracing::info!("🔍 Scanning for identity documents with pattern: {}", pattern);
        
        let keys: Vec<String> = self.redis.scan_match(&pattern, 1000).await?;
        tracing::info!("🔍 Found {} keys matching pattern", keys.len());
        
        if keys.len() > 0 {
            tracing::info!("🔍 First few keys: {:?}", keys.iter().take(3).collect::<Vec<_>>());
        }
        
        let mut documents = Vec::new();
        
        for key in keys {
            // Skip index keys
            if key.ends_with(":index") {
                tracing::info!("🔍 Skipping index key: {}", key);
                continue;
            }
            
            tracing::info!("🔍 Processing key: {}", key);
            if let Some(value) = self.redis.json_get(&key, ".").await? {
                match serde_json::from_value::<IdentityDocument>(value) {
                    Ok(doc) => {
                        tracing::info!("🔍 Successfully parsed document from key: {}", key);
                        documents.push(doc);
                    },
                    Err(e) => {
                        tracing::error!("🔍 Failed to parse document from key {}: {}", key, e);
                    }
                }
            } else {
                tracing::warn!("🔍 No data found for key: {}", key);
            }
        }
        
        tracing::info!("🔍 Total documents parsed: {}", documents.len());
        Ok(documents)
    }
    
    
    async fn get_identity_document_by_id(&self, instance_id: &str, document_id: &str) -> Result<Option<IdentityDocument>> {
        // Search for document by ID across all field types
        let pattern = format!("{}:identity:*:{}", instance_id, document_id);
        let keys: Vec<String> = self.redis.keys(&pattern).await?;
        
        if let Some(key) = keys.first() {
            if let Some(value) = self.redis.json_get(key, ".").await? {
                let doc: IdentityDocument = serde_json::from_value(value)?;
                return Ok(Some(doc));
            }
        }
        
        Ok(None)
    }
    
}

// ===== EVENT OPERATIONS IMPLEMENTATION =====
#[async_trait]
impl EventOperations for RedisRepository {
    async fn log_event(&self, instance: &str, event_type: &str, fields: Vec<(&str, &str)>) -> Result<()> {
        // Delegate to redis manager log_event method and ignore the returned event ID
        let _ = self.redis.log_event(instance, event_type, fields).await?;
        Ok(())
    }
    
    async fn publish_feedback_event(&self, event: &serde_json::Value) -> Result<()> {
        // Extract instance from event or use a default stream
        let instance = event.get("instance")
            .and_then(|v| v.as_str())
            .unwrap_or("global");
        
        let stream_key = format!("{}:feedback_events", instance);
        
        // Convert JSON object to Redis Stream fields with owned strings
        let mut field_pairs = Vec::new();
        if let Some(obj) = event.as_object() {
            for (key, value) in obj {
                let value_str = match value {
                    serde_json::Value::String(s) => s.clone(),
                    other => other.to_string(),
                };
                field_pairs.push((key.clone(), value_str));
            }
        }
        
        // Convert to string references for Redis command
        let fields: Vec<(&str, &str)> = field_pairs.iter()
            .map(|(k, v)| (k.as_str(), v.as_str()))
            .collect();
        
        let field_count = fields.len();
        
        // Publish to Redis Stream using XADD
        self.redis.xadd(&stream_key, "*", fields).await?;
        
        tracing::debug!("Published feedback event to stream {} with {} fields", stream_key, field_count);
        Ok(())
    }
}


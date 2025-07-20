use crate::error::{Result, UnifiedMindError};
use crate::models::*;
use crate::redis::RedisClient;
use chrono::{DateTime, Utc};
use qdrant_client::Qdrant;
use qdrant_client::qdrant::{
    Filter, PointId, point_id, ScrollPoints, Value, value, Condition,
    with_payload_selector::SelectorOptions, WithPayloadSelector, SearchPoints
};
use reqwest;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::env;
use std::time::Instant;
use tracing::{error, info, warn};
use uuid::Uuid;

#[derive(Debug, Serialize)]
struct OpenAIEmbeddingRequest {
    input: String,
    model: String,
}

#[derive(Debug, Deserialize)]
struct OpenAIEmbeddingResponse {
    data: Vec<OpenAIEmbedding>,
}

#[derive(Debug, Deserialize)]
struct OpenAIEmbedding {
    embedding: Vec<f32>,
}

#[derive(Debug, Serialize)]
struct GroqEmbeddingRequest {
    input: String,
    model: String,
}

#[derive(Debug, Deserialize)]
struct GroqEmbeddingResponse {
    data: Vec<GroqEmbedding>,
}

#[derive(Debug, Deserialize)]
struct GroqEmbedding {
    embedding: Vec<f32>,
}

pub struct RecallHandler {
    redis_client: RedisClient,
    qdrant_client: Qdrant,
    instance_id: String,
    openai_api_key: String,
    groq_api_key: String,
    http_client: reqwest::Client,
}

impl RecallHandler {
    pub async fn new(redis_client: RedisClient) -> Result<Self> {
        let qdrant_host = env::var("QDRANT_HOST").unwrap_or_else(|_| "localhost".to_string());
        let qdrant_port = env::var("QDRANT_PORT")
            .unwrap_or_else(|_| "6334".to_string())
            .parse::<u16>()
            .map_err(|_| UnifiedMindError::EnvVar("Invalid QDRANT_PORT".to_string()))?;
        
        let instance_id = env::var("INSTANCE_ID").unwrap_or_else(|_| "CC".to_string());
        
        // Get API keys
        let openai_api_key = env::var("OPENAI_API_KEY")
            .map_err(|_| UnifiedMindError::EnvVar("OPENAI_API_KEY not found".to_string()))?;
        let groq_api_key = env::var("GROQ_API_KEY").unwrap_or_default();
        
        info!("Connecting to Qdrant at {}:{}", qdrant_host, qdrant_port);
        let qdrant_client = Qdrant::from_url(&format!("http://{}:{}", qdrant_host, qdrant_port))
            .build()
            .map_err(|e| UnifiedMindError::Config(format!("Failed to create Qdrant client: {}", e)))?;
        
        // Check if collection exists (no creation since we're using existing collections)
        let collection_name = format!("{}_thoughts", instance_id);
        if !qdrant_client.collection_exists(&collection_name).await? {
            warn!("Collection {} does not exist - will search available collections", collection_name);
        }
        
        let http_client = reqwest::Client::new();
        
        Ok(Self {
            redis_client,
            qdrant_client,
            instance_id,
            openai_api_key,
            groq_api_key,
            http_client,
        })
    }
    
    async fn generate_embedding(&self, text: &str, use_openai: bool) -> Result<Vec<f32>> {
        if use_openai {
            self.generate_openai_embedding(text).await
        } else {
            self.generate_groq_embedding(text).await
        }
    }
    
    async fn generate_openai_embedding(&self, text: &str) -> Result<Vec<f32>> {
        // Check cache first
        if let Ok(Some(cached_embedding)) = self.redis_client.get_cached_embedding(text).await {
            info!("Using cached embedding for text: {}", text);
            return Ok(cached_embedding);
        }
        
        info!("Generating new OpenAI embedding for text: {}", text);
        
        let request = OpenAIEmbeddingRequest {
            input: text.to_string(),
            model: "text-embedding-3-small".to_string(),
        };
        
        let response = self.http_client
            .post("https://api.openai.com/v1/embeddings")
            .header("Authorization", format!("Bearer {}", self.openai_api_key))
            .json(&request)
            .send()
            .await
            .map_err(|e| UnifiedMindError::Other(anyhow::anyhow!("OpenAI API request failed: {}", e)))?;
        
        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_else(|_| "Unknown error".to_string());
            return Err(UnifiedMindError::Other(anyhow::anyhow!("OpenAI API error: {}", error_text)));
        }
        
        let embedding_response: OpenAIEmbeddingResponse = response
            .json()
            .await
            .map_err(|e| UnifiedMindError::Other(anyhow::anyhow!("Failed to parse OpenAI response: {}", e)))?;
        
        let embedding = embedding_response.data.into_iter().next()
            .ok_or_else(|| UnifiedMindError::Other(anyhow::anyhow!("No embeddings returned")))?
            .embedding;
        
        // Cache the embedding for 7 days
        if let Err(e) = self.redis_client.set_cached_embedding(text, &embedding, 86400 * 7).await {
            warn!("Failed to cache embedding: {}", e);
        }
        
        Ok(embedding)
    }
    
    async fn generate_groq_embedding(&self, text: &str) -> Result<Vec<f32>> {
        // Groq doesn't provide embeddings - they focus on fast LLM inference
        // For now, we'll use the same OpenAI embeddings for both modes
        // TODO: Implement a local/fast embedding model for default search
        warn!("Groq doesn't provide embeddings API - falling back to OpenAI");
        self.generate_openai_embedding(text).await
    }
    
    pub async fn recall(&self, params: UmRecallParams) -> Result<UmRecallResult> {
        let start_time = Instant::now();
        info!("Processing recall query: {}", params.query);
        
        // Generate query hash for caching
        let query_hash = format!("{:x}", md5::compute(&params.query));
        
        // Check cache first
        if let Ok(Some(cached)) = self.redis_client.get_cached_result(&query_hash).await {
            return Ok(UmRecallResult {
                thoughts: cached.result.thoughts,
                total_count: cached.result.total_count,
                metadata: SearchMetadata {
                    query: params.query.clone(),
                    execution_time_ms: start_time.elapsed().as_millis() as u64,
                    cache_hit: true,
                    search_type: if params.search_all_instances {
                        SearchType::Federated
                    } else {
                        SearchType::InstanceSpecific
                    },
                    instance_id: self.instance_id.clone(),
                    timestamp: Utc::now(),
                },
                synthesis: cached.result.synthesis,
            });
        }
        
        // Always use semantic search with OpenAI embeddings
        // TODO: Implement local embedding model for faster/cheaper default search
        info!("Cache miss, performing semantic search");
        let thoughts = self.search_thoughts_semantic(params.clone()).await?;
        info!("Search returned {} thoughts", thoughts.len());
        
        let total_count = thoughts.len();
        
        // Synthesize answer with Groq if we have results
        let synthesis = if !thoughts.is_empty() && !self.groq_api_key.is_empty() {
            info!("Attempting Groq synthesis for {} thoughts", thoughts.len());
            match self.synthesize_with_groq(&params.query, &thoughts).await {
                Ok(result) => {
                    info!("Groq synthesis successful - {} chars", result.len());
                    Some(result)
                },
                Err(e) => {
                    warn!("Groq synthesis failed: {}", e);
                    None
                }
            }
        } else {
            if thoughts.is_empty() {
                info!("No synthesis: no thoughts found");
            } else if self.groq_api_key.is_empty() {
                warn!("No synthesis: Groq API key is empty - set GROQ_API_KEY environment variable to enable synthesis");
            }
            None
        };
        
        let result = UmRecallResult {
            thoughts,
            total_count,
            metadata: SearchMetadata {
                query: params.query.clone(),
                execution_time_ms: start_time.elapsed().as_millis() as u64,
                cache_hit: false,
                search_type: if params.search_all_instances {
                    SearchType::Federated
                } else {
                    SearchType::InstanceSpecific
                },
                instance_id: self.instance_id.clone(),
                timestamp: Utc::now(),
            },
            synthesis,
        };
        
        // Cache the result
        let cached_result = CachedResult {
            result: result.clone(),
            cached_at: Utc::now(),
        };
        
        if let Err(e) = self.redis_client.set_cached_result(&query_hash, &cached_result, 3600).await {
            warn!("Failed to cache result: {}", e);
        }
        
        Ok(result)
    }
    
    
    async fn search_thoughts(
        &self,
        params: UmRecallParams,
    ) -> Result<Vec<Thought>> {
        // Determine collections to search
        let collections = if params.search_all_instances {
            // Get all instance collections
            vec!["CC_thoughts", "DT_thoughts", "CCS_thoughts", "CCB_thoughts"]
                .into_iter()
                .map(|s| s.to_string())
                .collect()
        } else if let Some(instances) = params.instance_filter {
            instances.iter()
                .map(|inst| format!("{}_thoughts", inst))
                .collect()
        } else {
            vec![format!("{}_thoughts", self.instance_id)]
        };
        
        let mut all_thoughts = Vec::new();
        
        for collection in collections {
            // Skip if collection doesn't exist
            if !self.qdrant_client.collection_exists(&collection).await? {
                info!("Collection {} does not exist, skipping", collection);
                continue;
            }
            
            info!("Searching collection: {}", collection);
            
            // Build filter
            let mut filter = vec![];
            
            if let Some(category) = &params.category_filter {
                filter.push(Condition::matches("category", category.clone()));
            }
            
            if let Some(tags) = &params.tags_filter {
                for tag in tags {
                    filter.push(Condition::matches("tags", tag.clone()));
                }
            }
            
            // Use scroll to get all points, then filter by text
            let scroll_request = ScrollPoints {
                collection_name: collection.clone(),
                filter: if filter.is_empty() {
                    None
                } else {
                    Some(Filter {
                        must: filter,
                        ..Default::default()
                    })
                },
                limit: Some(1000), // Get up to 1000 at a time
                offset: None,
                with_payload: Some(WithPayloadSelector {
                    selector_options: Some(SelectorOptions::Enable(true)),
                }),
                with_vectors: Some(false.into()),
                order_by: None,
                read_consistency: None,
                shard_key_selector: None,
                timeout: None,
            };
            
            match self.qdrant_client.scroll(scroll_request).await {
                Ok(results) => {
                    for point in results.result {
                        let payload = point.payload;
                        // Text-based filtering
                        let matches_query = if let Some(content) = payload.get("content")
                            .and_then(|v| get_string_from_value(v)) {
                            content.to_lowercase().contains(&params.query.to_lowercase())
                        } else {
                            false
                        };
                        
                        if matches_query {
                            match self.point_to_thought(point.id.unwrap(), payload) {
                                Ok(mut thought) => {
                                    // Calculate weighted scores
                                    self.calculate_weighted_scores(&mut thought).await;
                                    all_thoughts.push(thought);
                                }
                                Err(e) => {
                                    error!("Failed to parse thought: {}", e);
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    error!("Failed to search collection {}: {}", collection, e);
                }
            }
        }
        
        // Sort by combined score
        all_thoughts.sort_by(|a, b| {
            b.combined_score.unwrap_or(0.0)
                .partial_cmp(&a.combined_score.unwrap_or(0.0))
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        
        // Limit results
        all_thoughts.truncate(params.limit);
        
        // Update usage counts
        for thought in &all_thoughts {
            if let Err(e) = self.redis_client.increment_usage_count(&thought.id).await {
                warn!("Failed to increment usage count: {}", e);
            }
        }
        
        Ok(all_thoughts)
    }
    
    async fn enhance_query_with_groq(&self, query: &str) -> Result<String> {
        info!("Enhancing query with Groq: {}", query);
        
        // Use Groq to expand the query with related terms
        let prompt = format!(
            "Expand this search query with synonyms and related concepts. \
             Return ONLY the expanded terms as a comma-separated list, nothing else.\n\
             Query: {}\n\
             Expanded terms:",
            query
        );
        
        let groq_request = serde_json::json!({
            "model": "llama-3.3-70b-versatile",
            "messages": [{
                "role": "user",
                "content": prompt
            }],
            "temperature": 0.3,
            "max_tokens": 100
        });
        
        let response = self.http_client
            .post("https://api.groq.com/openai/v1/chat/completions")
            .header("Authorization", format!("Bearer {}", self.groq_api_key))
            .json(&groq_request)
            .send()
            .await
            .map_err(|e| UnifiedMindError::Other(anyhow::anyhow!("Groq API request failed: {}", e)))?;
        
        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_else(|_| "Unknown error".to_string());
            warn!("Groq query enhancement failed: {}", error_text);
            // Fall back to original query
            return Ok(query.to_string());
        }
        
        let groq_response: serde_json::Value = response.json().await
            .map_err(|e| UnifiedMindError::Other(anyhow::anyhow!("Failed to parse Groq response: {}", e)))?;
        
        let enhanced = groq_response["choices"][0]["message"]["content"]
            .as_str()
            .unwrap_or(query)
            .to_string();
        
        info!("Enhanced query: {}", enhanced);
        Ok(enhanced)
    }
    
    async fn synthesize_with_groq(&self, query: &str, thoughts: &[Thought]) -> Result<String> {
        info!("Synthesizing answer with Groq for query: {}", query);
        
        // Build context from retrieved thoughts
        let context = thoughts.iter()
            .take(5) // Limit to top 5 to stay within token limits
            .map(|t| format!("- {}", t.content))
            .collect::<Vec<_>>()
            .join("\n");
        
        let prompt = format!(
            "Based on the following retrieved information, provide a comprehensive answer to the query.\n\n\
             Query: {}\n\n\
             Retrieved Information:\n{}\n\n\
             Synthesized Answer:",
            query, context
        );
        
        let groq_request = serde_json::json!({
            "model": "llama-3.3-70b-versatile",
            "messages": [{
                "role": "system",
                "content": "You are a helpful assistant that synthesizes information from retrieved documents to answer queries accurately and comprehensively."
            }, {
                "role": "user",
                "content": prompt
            }],
            "temperature": 0.7,
            "max_tokens": 500
        });
        
        let response = self.http_client
            .post("https://api.groq.com/openai/v1/chat/completions")
            .header("Authorization", format!("Bearer {}", self.groq_api_key))
            .json(&groq_request)
            .send()
            .await
            .map_err(|e| UnifiedMindError::Other(anyhow::anyhow!("Groq synthesis request failed: {}", e)))?;
        
        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_else(|_| "Unknown error".to_string());
            return Err(UnifiedMindError::Other(anyhow::anyhow!("Groq synthesis failed: {}", error_text)));
        }
        
        let groq_response: serde_json::Value = response.json().await
            .map_err(|e| UnifiedMindError::Other(anyhow::anyhow!("Failed to parse Groq synthesis response: {}", e)))?;
        
        let synthesis = groq_response["choices"][0]["message"]["content"]
            .as_str()
            .ok_or_else(|| UnifiedMindError::Other(anyhow::anyhow!("No synthesis content in response")))?
            .to_string();
        
        info!("Synthesis complete, length: {} chars", synthesis.len());
        Ok(synthesis)
    }
    
    async fn search_thoughts_semantic(
        &self,
        params: UmRecallParams,
    ) -> Result<Vec<Thought>> {
        // First, enhance the query with Groq
        let enhanced_query = if self.groq_api_key.is_empty() {
            params.query.clone()
        } else {
            self.enhance_query_with_groq(&params.query).await.unwrap_or(params.query.clone())
        };
        
        // Generate embedding for the enhanced query using OpenAI
        let query_embedding = self.generate_openai_embedding(&enhanced_query).await?;
        info!("Generated embedding with {} dimensions", query_embedding.len());
        
        // Determine collections to search  
        let collections = if params.search_all_instances {
            // Search identity collections too for federation
            let mut cols = vec!["CC_thoughts", "DT_thoughts", "CCS_thoughts", "CCB_thoughts"];
            cols.extend(&["CC_identity", "DT_identity", "CCS_identity", "CCB_identity"]);
            cols.into_iter().map(|s| s.to_string()).collect()
        } else if let Some(instances) = params.instance_filter {
            let mut cols = Vec::new();
            for inst in &instances {
                cols.push(format!("{}_thoughts", inst));
                cols.push(format!("{}_identity", inst));
            }
            cols
        } else {
            vec![
                format!("{}_thoughts", self.instance_id),
                format!("{}_identity", self.instance_id)
            ]
        };
        
        let mut all_thoughts = Vec::new();
        
        for collection in collections {
            // Skip if collection doesn't exist
            if !self.qdrant_client.collection_exists(&collection).await? {
                info!("Collection {} does not exist, skipping", collection);
                continue;
            }
            
            info!("Searching collection: {}", collection);
            
            // Build filter
            let mut filter = vec![];
            
            if let Some(category) = &params.category_filter {
                filter.push(Condition::matches("category", category.clone()));
            }
            
            if let Some(tags) = &params.tags_filter {
                for tag in tags {
                    filter.push(Condition::matches("tags", tag.clone()));
                }
            }
            
            info!("Searching with vector of dimension {} in collection {}", query_embedding.len(), collection);
            
            // Use vector search
            let search_request = SearchPoints {
                collection_name: collection.clone(),
                vector: query_embedding.clone(),
                filter: if filter.is_empty() {
                    None
                } else {
                    Some(Filter {
                        must: filter,
                        ..Default::default()
                    })
                },
                limit: params.limit as u64,
                with_payload: Some(WithPayloadSelector {
                    selector_options: Some(SelectorOptions::Enable(true)),
                }),
                with_vectors: Some(false.into()),
                params: None,
                score_threshold: Some(params.threshold),
                offset: None,
                vector_name: None,
                read_consistency: None,
                timeout: None,
                shard_key_selector: None,
                sparse_indices: None,
            };
            
            match self.qdrant_client.search_points(search_request).await {
                Ok(results) => {
                    info!("Search returned {} results from {}", results.result.len(), collection);
                    for scored_point in results.result {
                        let point_id = scored_point.id.ok_or_else(|| 
                            UnifiedMindError::Other(anyhow::anyhow!("Missing point ID")))?;
                        
                        match self.point_to_thought(point_id, scored_point.payload) {
                            Ok(mut thought) => {
                                // Set semantic score from Qdrant
                                thought.semantic_score = Some(scored_point.score);
                                // Calculate other weighted scores
                                self.calculate_weighted_scores(&mut thought).await;
                                all_thoughts.push(thought);
                            }
                            Err(e) => {
                                error!("Failed to parse thought: {}", e);
                            }
                        }
                    }
                }
                Err(e) => {
                    error!("Failed to search collection {}: {}", collection, e);
                }
            }
        }
        
        // Sort by combined score
        all_thoughts.sort_by(|a, b| {
            b.combined_score.unwrap_or(0.0)
                .partial_cmp(&a.combined_score.unwrap_or(0.0))
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        
        // Limit results
        all_thoughts.truncate(params.limit);
        
        // Update usage counts
        for thought in &all_thoughts {
            if let Err(e) = self.redis_client.increment_usage_count(&thought.id).await {
                warn!("Failed to increment usage count: {}", e);
            }
        }
        
        Ok(all_thoughts)
    }
    
    async fn search_thoughts_semantic_groq(
        &self,
        params: UmRecallParams,
    ) -> Result<Vec<Thought>> {
        // Generate embedding for the query using Groq
        let query_embedding = self.generate_groq_embedding(&params.query).await?;
        
        // Determine collections to search  
        let collections = if params.search_all_instances {
            // Search identity collections too for federation
            let mut cols = vec!["CC_thoughts", "DT_thoughts", "CCS_thoughts", "CCB_thoughts"];
            cols.extend(&["CC_identity", "DT_identity", "CCS_identity", "CCB_identity"]);
            cols.into_iter().map(|s| s.to_string()).collect()
        } else if let Some(instances) = params.instance_filter {
            let mut cols = Vec::new();
            for inst in &instances {
                cols.push(format!("{}_thoughts", inst));
                cols.push(format!("{}_identity", inst));
            }
            cols
        } else {
            vec![
                format!("{}_thoughts", self.instance_id),
                format!("{}_identity", self.instance_id)
            ]
        };
        
        let mut all_thoughts = Vec::new();
        
        for collection in collections {
            // Skip if collection doesn't exist
            if !self.qdrant_client.collection_exists(&collection).await? {
                info!("Collection {} does not exist, skipping", collection);
                continue;
            }
            
            info!("Searching collection: {}", collection);
            
            // Build filter
            let mut filter = vec![];
            
            if let Some(category) = &params.category_filter {
                filter.push(Condition::matches("category", category.clone()));
            }
            
            if let Some(tags) = &params.tags_filter {
                for tag in tags {
                    filter.push(Condition::matches("tags", tag.clone()));
                }
            }
            
            info!("Searching with vector of dimension {} in collection {}", query_embedding.len(), collection);
            
            // Use vector search
            let search_request = SearchPoints {
                collection_name: collection.clone(),
                vector: query_embedding.clone(),
                filter: if filter.is_empty() {
                    None
                } else {
                    Some(Filter {
                        must: filter,
                        ..Default::default()
                    })
                },
                limit: params.limit as u64,
                with_payload: Some(WithPayloadSelector {
                    selector_options: Some(SelectorOptions::Enable(true)),
                }),
                with_vectors: Some(false.into()),
                params: None,
                score_threshold: Some(params.threshold),
                offset: None,
                vector_name: None,
                read_consistency: None,
                timeout: None,
                shard_key_selector: None,
                sparse_indices: None,
            };
            
            match self.qdrant_client.search_points(search_request).await {
                Ok(results) => {
                    info!("Search returned {} results from {}", results.result.len(), collection);
                    for scored_point in results.result {
                        let point_id = scored_point.id.ok_or_else(|| 
                            UnifiedMindError::Other(anyhow::anyhow!("Missing point ID")))?;
                        
                        match self.point_to_thought(point_id, scored_point.payload) {
                            Ok(mut thought) => {
                                // Set semantic score from Qdrant
                                thought.semantic_score = Some(scored_point.score);
                                // Calculate other weighted scores
                                self.calculate_weighted_scores(&mut thought).await;
                                all_thoughts.push(thought);
                            }
                            Err(e) => {
                                error!("Failed to parse thought: {}", e);
                            }
                        }
                    }
                }
                Err(e) => {
                    error!("Failed to search collection {}: {}", collection, e);
                }
            }
        }
        
        // Sort by combined score
        all_thoughts.sort_by(|a, b| {
            b.combined_score.unwrap_or(0.0)
                .partial_cmp(&a.combined_score.unwrap_or(0.0))
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        
        // Limit results
        all_thoughts.truncate(params.limit);
        
        // Update usage counts
        for thought in &all_thoughts {
            if let Err(e) = self.redis_client.increment_usage_count(&thought.id).await {
                warn!("Failed to increment usage count: {}", e);
            }
        }
        
        Ok(all_thoughts)
    }
    
    fn point_to_thought(
        &self,
        point_id: PointId,
        payload: HashMap<String, Value>,
    ) -> Result<Thought> {
        // Convert qdrant Value to serde_json::Value
        let mut json_payload = serde_json::Map::new();
        for (key, value) in payload {
            json_payload.insert(key, convert_qdrant_value_to_json(value));
        }
        let json_payload = serde_json::Value::Object(json_payload);
        let id = match point_id.point_id_options {
            Some(point_id::PointIdOptions::Uuid(uuid)) => {
                Uuid::parse_str(&uuid)
                    .map_err(|e| UnifiedMindError::Other(anyhow::anyhow!("Invalid UUID: {}", e)))?
            }
            Some(point_id::PointIdOptions::Num(num)) => {
                // Handle numeric point IDs by using the thought_id from payload if available
                if let Some(thought_id_value) = json_payload.get("thought_id") {
                    if let Some(thought_id_str) = thought_id_value.as_str() {
                        Uuid::parse_str(thought_id_str)
                            .map_err(|e| UnifiedMindError::Other(anyhow::anyhow!("Invalid thought_id UUID: {}", e)))?
                    } else {
                        return Err(UnifiedMindError::Other(anyhow::anyhow!(
                            "thought_id in payload is not a string"
                        )))
                    }
                } else {
                    return Err(UnifiedMindError::Other(anyhow::anyhow!(
                        "Numeric point ID {} with no thought_id in payload", num
                    )))
                }
            }
            None => {
                return Err(UnifiedMindError::Other(anyhow::anyhow!(
                    "Missing point ID"
                )))
            }
        };
        
        Ok(Thought {
            id,
            content: json_payload.get("content")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            category: json_payload.get("category")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            tags: json_payload.get("tags")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter()
                    .filter_map(|v| v.as_str())
                    .map(|s| s.to_string())
                    .collect())
                .unwrap_or_default(),
            instance_id: json_payload.get("instance")
                .and_then(|v| v.as_str())
                .unwrap_or(&self.instance_id)
                .to_string(),
            created_at: json_payload.get("processed_at")
                .and_then(|v| v.as_str())
                .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
                .map(|dt| dt.with_timezone(&Utc))
                .unwrap_or_else(Utc::now),
            updated_at: json_payload.get("processed_at")
                .and_then(|v| v.as_str())
                .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
                .map(|dt| dt.with_timezone(&Utc))
                .unwrap_or_else(Utc::now),
            importance: json_payload.get("importance")
                .and_then(|v| v.as_i64())
                .unwrap_or(5) as i32,
            relevance: json_payload.get("relevance")
                .and_then(|v| v.as_i64())
                .unwrap_or(5) as i32,
            semantic_score: Some(0.8), // Default score for text matches
            temporal_score: None,
            usage_score: None,
            combined_score: None,
        })
    }
    
    async fn calculate_weighted_scores(&self, thought: &mut Thought) {
        // Temporal score (0-1, based on recency)
        let age_days = (Utc::now() - thought.updated_at).num_days() as f32;
        let temporal_score = (-age_days / 30.0).exp(); // Exponential decay over 30 days
        thought.temporal_score = Some(temporal_score);
        
        // Usage score (0-1, based on access frequency)
        let usage_score = if let Ok(Some(metadata)) = self.redis_client.get_thought_metadata(&thought.id).await {
            // Normalize usage count (assume 100 uses is very high)
            (metadata.usage_count as f32 / 100.0).min(1.0)
        } else {
            0.0
        };
        thought.usage_score = Some(usage_score);
        
        // Combined score with weights
        let semantic_weight = 0.5;
        let temporal_weight = 0.3;
        let usage_weight = 0.2;
        
        let combined_score = 
            thought.semantic_score.unwrap_or(0.0) * semantic_weight +
            temporal_score * temporal_weight +
            usage_score * usage_weight;
        
        thought.combined_score = Some(combined_score);
    }
    
    pub async fn submit_feedback(&self, params: FeedbackParams) -> Result<FeedbackResult> {
        let start = Instant::now();
        
        // Store feedback record
        let feedback_key = format!("um:feedback:{}:{}", params.search_id, params.thought_id);
        let mut feedback_data: HashMap<String, String> = HashMap::new();
        
        feedback_data.insert("search_id".to_string(), params.search_id.clone());
        feedback_data.insert("thought_id".to_string(), params.thought_id.to_string());
        feedback_data.insert("instance_id".to_string(), self.instance_id.clone());
        feedback_data.insert("timestamp".to_string(), Utc::now().to_rfc3339());
        
        if let Some(rating) = params.rating {
            feedback_data.insert("user_rating".to_string(), rating.to_string());
        }
        
        if let Some(relevance) = params.relevance {
            feedback_data.insert("relevance_score".to_string(), relevance.to_string());
        }
        
        if let Some(action) = &params.action {
            feedback_data.insert("action".to_string(), format!("{:?}", action));
            
            if let Some(value) = &params.value {
                feedback_data.insert("action_value".to_string(), value.to_string());
            }
        }
        
        // Store in Redis with 90-day TTL
        self.redis_client
            .hset_all(&feedback_key, feedback_data)
            .await?;
        self.redis_client
            .expire(&feedback_key, 90 * 24 * 60 * 60)
            .await?;
        
        // Add to feedback stream for real-time processing
        let mut stream_data: HashMap<String, String> = HashMap::new();
        stream_data.insert("event_type".to_string(), 
            if params.rating.is_some() || params.relevance.is_some() { 
                "explicit".to_string() 
            } else { 
                "implicit".to_string() 
            }
        );
        stream_data.insert("search_id".to_string(), params.search_id.clone());
        stream_data.insert("thought_id".to_string(), params.thought_id.to_string());
        stream_data.insert("instance_id".to_string(), self.instance_id.clone());
        
        if let Some(rating) = params.rating {
            stream_data.insert("rating".to_string(), rating.to_string());
        }
        
        if let Some(action) = &params.action {
            stream_data.insert("action".to_string(), format!("{:?}", action));
        }
        
        self.redis_client
            .xadd("um:feedback:stream", stream_data)
            .await?;
        
        // Update aggregated feedback score
        if let Some(rating) = params.rating {
            let score = match rating {
                1 => 1.0,
                -1 => -1.0,
                _ => 0.0,
            };
            
            let member = format!("{}:{}", params.search_id, Utc::now().timestamp());
            self.redis_client
                .zadd(&format!("um:thought:feedback:{}", params.thought_id), score, member)
                .await?;
        }
        
        let elapsed = start.elapsed();
        info!("Feedback submitted in {}ms", elapsed.as_millis());
        
        Ok(FeedbackResult {
            success: true,
            message: format!("Feedback recorded for thought {}", params.thought_id),
        })
    }
}

fn convert_qdrant_value_to_json(value: Value) -> serde_json::Value {
    match value.kind {
        Some(value::Kind::NullValue(_)) => serde_json::Value::Null,
        Some(value::Kind::DoubleValue(d)) => serde_json::Value::from(d),
        Some(value::Kind::IntegerValue(i)) => serde_json::Value::from(i),
        Some(value::Kind::StringValue(s)) => serde_json::Value::String(s),
        Some(value::Kind::BoolValue(b)) => serde_json::Value::Bool(b),
        Some(value::Kind::ListValue(list)) => {
            serde_json::Value::Array(
                list.values.into_iter()
                    .map(convert_qdrant_value_to_json)
                    .collect()
            )
        }
        Some(value::Kind::StructValue(s)) => {
            let mut map = serde_json::Map::new();
            for (k, v) in s.fields {
                map.insert(k, convert_qdrant_value_to_json(v));
            }
            serde_json::Value::Object(map)
        }
        None => serde_json::Value::Null,
    }
}

fn get_string_from_value(value: &Value) -> Option<&str> {
    match &value.kind {
        Some(value::Kind::StringValue(s)) => Some(s.as_str()),
        _ => None,
    }
}
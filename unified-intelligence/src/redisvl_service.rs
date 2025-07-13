/// RedisVL-based vector service using external Python script
/// This replaces the PyO3 implementation to avoid linking issues

use std::process::Command;
use std::sync::Arc;
use serde_json::Value;
use crate::error::{Result, UnifiedIntelligenceError};
use crate::models::ThoughtRecord;
use crate::redis::RedisManager;

pub struct RedisVLService {
    instance_id: String,
    script_path: String,
    redis_manager: Arc<RedisManager>,
}

impl RedisVLService {
    pub fn new(instance_id: String, redis_manager: Arc<RedisManager>) -> Self {
        let script_path = "/Users/samuelatagana/Projects/LegacyMind/unified-intelligence/simple_embeddings.py".to_string();
        Self {
            instance_id,
            script_path,
            redis_manager,
        }
    }
    
    /// Get the OpenAI API key from Redis or environment
    async fn get_openai_api_key(&self) -> Result<String> {
        // First try to get from Redis
        if let Ok(Some(api_key)) = self.redis_manager.get_api_key("openai_api_key").await {
            tracing::debug!("Retrieved OPENAI_API_KEY from Redis");
            return Ok(api_key);
        }
        
        // Fallback to environment variable
        if let Ok(api_key) = std::env::var("OPENAI_API_KEY") {
            if !api_key.is_empty() {
                tracing::debug!("Retrieved OPENAI_API_KEY from environment");
                return Ok(api_key);
            }
        }
        
        Err(UnifiedIntelligenceError::Configuration(
            "OPENAI_API_KEY not found in Redis or environment".to_string()
        ))
    }
    
    /// Store a thought with embedding
    pub async fn store_thought_embedding(
        &self, 
        thought_id: &str, 
        content: &str, 
        timestamp: i64
    ) -> Result<bool> {
        // Get API key from Redis or environment
        let api_key = self.get_openai_api_key().await?;
        
        let output = Command::new("python3")
            .arg(&self.script_path)
            .arg("store")
            .arg(thought_id)
            .arg(content)
            .arg(timestamp.to_string())
            .env("INSTANCE_ID", &self.instance_id)
            .env("REDIS_PASSWORD", "legacymind_redis_pass")
            .env("OPENAI_API_KEY", api_key)
            .output()
            .map_err(|e| UnifiedIntelligenceError::Python(format!("Failed to execute Python script: {}", e)))?;
        
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(UnifiedIntelligenceError::Python(format!("Python script failed: {}", stderr)));
        }
        
        let stdout = String::from_utf8_lossy(&output.stdout);
        let response: Value = serde_json::from_str(&stdout)
            .map_err(|e| UnifiedIntelligenceError::Python(format!("Failed to parse Python response: {}", e)))?;
        
        Ok(response["success"].as_bool().unwrap_or(false))
    }
    
    /// Perform semantic search
    pub async fn semantic_search(
        &self,
        query: &str,
        limit: usize,
        threshold: f32
    ) -> Result<Vec<ThoughtRecord>> {
        // Get API key from Redis or environment
        let api_key = self.get_openai_api_key().await?;
        
        tracing::debug!("RedisVL semantic_search - Using API key with {} chars", api_key.len());
        
        let output = Command::new("python3")
            .arg(&self.script_path)
            .arg("search")
            .arg(query)
            .arg(limit.to_string())
            .arg(threshold.to_string())
            .env("INSTANCE_ID", &self.instance_id)
            .env("REDIS_PASSWORD", "legacymind_redis_pass")
            .env("OPENAI_API_KEY", api_key)
            .output()
            .map_err(|e| UnifiedIntelligenceError::Python(format!("Failed to execute Python script: {}", e)))?;
        
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(UnifiedIntelligenceError::Python(format!("Python script failed: {}", stderr)));
        }
        
        let stdout = String::from_utf8_lossy(&output.stdout);
        let response: Value = serde_json::from_str(&stdout)
            .map_err(|e| UnifiedIntelligenceError::Python(format!("Failed to parse Python response: {}", e)))?;
        
        let results = response["results"].as_array()
            .ok_or_else(|| UnifiedIntelligenceError::Python("No results array in response".to_string()))?;
        
        let mut thoughts = Vec::new();
        for result in results {
            if let Some(thought_id) = result["thought_id"].as_str() {
                // Create a basic ThoughtRecord from the search result
                // In a real implementation, you might want to fetch the full record from Redis
                let content = result["content"].as_str().unwrap_or("").to_string();
                let thought = ThoughtRecord {
                    id: thought_id.to_string(),
                    instance: self.instance_id.clone(),
                    thought: content.clone(),
                    content,
                    timestamp: chrono::Utc::now().to_rfc3339(),
                    thought_number: 1,
                    total_thoughts: 1,
                    next_thought_needed: false,
                    chain_id: None,
                    similarity: result["similarity"].as_f64().map(|f| f as f32),
                };
                thoughts.push(thought);
            }
        }
        
        Ok(thoughts)
    }
}
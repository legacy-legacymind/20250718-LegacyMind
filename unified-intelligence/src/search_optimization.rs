use std::collections::HashMap;
use anyhow::Result;
use serde_json::Value;
use crate::models::ThoughtRecord;
use rmcp::model::ErrorData;
use tracing;

/// Optimized search implementation using batch operations
#[allow(dead_code)]
pub struct OptimizedSearch;

impl OptimizedSearch {
    /// Batch fetch multiple thoughts using MGET
    pub async fn batch_fetch_thoughts(
        conn: &mut deadpool_redis::Connection,
        keys: &[String],
    ) -> Result<Vec<(String, ThoughtRecord)>, ErrorData> {
        if keys.is_empty() {
            return Ok(Vec::new());
        }

        // Use pipeline for efficiency
        let mut pipe = redis::pipe();
        
        // Add all JSON.GET commands to pipeline
        for key in keys {
            pipe.cmd("JSON.GET")
                .arg(key)
                .arg("$");
        }
        
        // Execute pipeline
        let results: Vec<Option<String>> = pipe.query_async(&mut **conn)
            .await
            .map_err(|e| ErrorData::internal_error(
                format!("Pipeline execution failed: {}", e), 
                None
            ))?;
        
        // Process results
        let mut thoughts = Vec::new();
        for (idx, result) in results.into_iter().enumerate() {
            if let Some(json_str) = result {
                if let Ok(json_array) = serde_json::from_str::<Vec<Value>>(&json_str) {
                    if let Some(thought_value) = json_array.first() {
                        if let Ok(thought) = serde_json::from_value::<ThoughtRecord>(thought_value.clone()) {
                            thoughts.push((keys[idx].clone(), thought));
                        }
                    }
                }
            }
        }
        
        tracing::debug!("Batch fetch: processed {} keys, found {} thoughts", keys.len(), thoughts.len());
        
        Ok(thoughts)
    }
    
    /// Optimized search with batch operations and early termination
    #[allow(dead_code)]
    pub async fn search_with_batching(
        conn: &mut deadpool_redis::Connection,
        query: &str,
        instance_id: &str,
        limit: usize,
    ) -> Result<Vec<ThoughtRecord>, ErrorData> {
        let pattern = format!("thought:{}:*", instance_id);
        let query_lower = query.to_lowercase();
        let mut cursor = "0".to_string();
        let mut found_thoughts = Vec::new();
        
        // Batch size for SCAN and processing
        const SCAN_BATCH_SIZE: usize = 100;
        const FETCH_BATCH_SIZE: usize = 20;
        
        'scan_loop: loop {
            // SCAN for keys
            let (new_cursor, keys): (String, Vec<String>) = redis::cmd("SCAN")
                .arg(&cursor)
                .arg("MATCH").arg(&pattern)
                .arg("COUNT").arg(SCAN_BATCH_SIZE)
                .query_async(&mut **conn)
                .await
                .map_err(|e| ErrorData::internal_error(
                    format!("SCAN failed: {}", e), 
                    None
                ))?;
            
            tracing::debug!("SCAN iteration: found {} keys, cursor: {} -> {}", keys.len(), cursor, new_cursor);
            
            // Process keys in batches
            for chunk in keys.chunks(FETCH_BATCH_SIZE) {
                let batch_results = Self::batch_fetch_thoughts(conn, chunk).await?;
                
                // Filter matching thoughts
                for (_key, thought) in batch_results {
                    if thought.thought.to_lowercase().contains(&query_lower) {
                        found_thoughts.push(thought);
                        
                        // Early termination when limit reached
                        if found_thoughts.len() >= limit {
                            break 'scan_loop;
                        }
                    }
                }
            }
            
            cursor = new_cursor;
            if cursor == "0" {
                break;
            }
        }
        
        // Ensure we don't return more than requested
        found_thoughts.truncate(limit);
        Ok(found_thoughts)
    }
    
    /// Search with cursor state for pagination
    #[allow(dead_code)]
    pub async fn search_paginated(
        conn: &mut deadpool_redis::Connection,
        query: &str,
        instance_id: &str,
        page_size: usize,
        cursor_state: Option<String>,
    ) -> Result<(Vec<ThoughtRecord>, Option<String>), ErrorData> {
        let pattern = format!("thought:{}:*", instance_id);
        let query_lower = query.to_lowercase();
        let mut cursor = cursor_state.unwrap_or_else(|| "0".to_string());
        let mut found_thoughts = Vec::new();
        let mut next_cursor = None;
        
        // Continue from cursor position
        loop {
            let (new_cursor, keys): (String, Vec<String>) = redis::cmd("SCAN")
                .arg(&cursor)
                .arg("MATCH").arg(&pattern)
                .arg("COUNT").arg(100)
                .query_async(&mut **conn)
                .await
                .map_err(|e| ErrorData::internal_error(
                    format!("SCAN failed: {}", e), 
                    None
                ))?;
            
            // Batch fetch
            let batch_results = Self::batch_fetch_thoughts(conn, &keys).await?;
            
            // Filter and collect
            for (_key, thought) in batch_results {
                if thought.thought.to_lowercase().contains(&query_lower) {
                    found_thoughts.push(thought);
                    
                    if found_thoughts.len() >= page_size {
                        // Save cursor for next page
                        if new_cursor != "0" {
                            next_cursor = Some(new_cursor);
                        }
                        return Ok((found_thoughts, next_cursor));
                    }
                }
            }
            
            cursor = new_cursor;
            if cursor == "0" {
                break;
            }
        }
        
        Ok((found_thoughts, None))
    }
}

/// Cache for recent search results
pub struct SearchCache {
    cache: HashMap<String, (Vec<ThoughtRecord>, std::time::Instant)>,
    ttl: std::time::Duration,
}

impl SearchCache {
    pub fn new(ttl_seconds: u64) -> Self {
        Self {
            cache: HashMap::new(),
            ttl: std::time::Duration::from_secs(ttl_seconds),
        }
    }
    
    pub fn get(&self, key: &str) -> Option<&Vec<ThoughtRecord>> {
        self.cache.get(key).and_then(|(results, timestamp)| {
            if timestamp.elapsed() < self.ttl {
                Some(results)
            } else {
                None
            }
        })
    }
    
    pub fn insert(&mut self, key: String, results: Vec<ThoughtRecord>) {
        self.cache.insert(key, (results, std::time::Instant::now()));
        
        // Simple cache eviction - remove expired entries
        self.cache.retain(|_, (_, timestamp)| timestamp.elapsed() < self.ttl);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_search_cache() {
        let mut cache = SearchCache::new(60);
        let thoughts = vec![
            ThoughtRecord {
                id: "test-1".to_string(),
                instance: "test".to_string(),
                thought: "Test thought".to_string(),
                content: "Test thought".to_string(),
                thought_number: 1,
                total_thoughts: 1,
                timestamp: "2025-01-01T00:00:00Z".to_string(),
                chain_id: None,
                next_thought_needed: false,
                similarity: None,
            }
        ];
        
        cache.insert("test-query".to_string(), thoughts.clone());
        assert!(cache.get("test-query").is_some());
        assert_eq!(cache.get("test-query").unwrap().len(), 1);
    }
}